"""Airtable API service with caching and rate limiting"""
import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import httpx
from redis import asyncio as aioredis
import hashlib

from ..config import get_settings


class AirtableService:
    """Service for interacting with Airtable API"""
    
    def __init__(self, redis_client: aioredis.Redis):
        self.settings = get_settings()
        self.redis = redis_client
        self.base_url = "https://api.airtable.com/v0"
        self.headers = {
            "Authorization": f"Bearer {self.settings.airtable_token}",
            "Content-Type": "application/json"
        }
        self._rate_limiter = asyncio.Semaphore(self.settings.airtable_rate_limit)
        
    def _cache_key(self, method: str, path: str, params: Optional[Dict] = None) -> str:
        """Generate cache key for request"""
        key_data = f"{method}:{path}:{json.dumps(params or {}, sort_keys=True)}"
        return f"airtable:{hashlib.md5(key_data.encode()).hexdigest()}"
    
    async def _get_from_cache(self, key: str) -> Optional[Dict]:
        """Get data from cache"""
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
        except Exception as e:
            print(f"Cache get error: {e}")
        return None
    
    async def _set_cache(self, key: str, data: Dict, ttl: Optional[int] = None):
        """Set data in cache"""
        try:
            ttl = ttl or self.settings.cache_ttl
            await self.redis.setex(key, ttl, json.dumps(data))
        except Exception as e:
            print(f"Cache set error: {e}")
    
    async def _make_request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        data: Optional[Dict] = None,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """Make request to Airtable API with rate limiting and caching"""
        
        # Check cache for GET requests
        cache_key = self._cache_key(method, path, params)
        if method == "GET" and use_cache:
            cached_data = await self._get_from_cache(cache_key)
            if cached_data:
                return cached_data
        
        # Rate limiting
        async with self._rate_limiter:
            async with httpx.AsyncClient(timeout=self.settings.airtable_timeout) as client:
                response = await client.request(
                    method=method,
                    url=f"{self.base_url}/{path}",
                    headers=self.headers,
                    params=params,
                    json=data
                )
                
                if response.status_code >= 400:
                    error_data = response.json()
                    raise Exception(f"Airtable API error: {error_data}")
                
                result = response.json()
                
                # Cache successful GET requests
                if method == "GET" and use_cache:
                    await self._set_cache(cache_key, result)
                
                return result
    
    async def list_bases(self) -> List[Dict[str, Any]]:
        """List all accessible bases"""
        result = await self._make_request("GET", "meta/bases")
        return result.get("bases", [])
    
    async def get_base_schema(self, base_id: str) -> Dict[str, Any]:
        """Get base schema"""
        return await self._make_request("GET", f"meta/bases/{base_id}/tables")
    
    async def list_records(
        self,
        base_id: str,
        table_id: str,
        view: Optional[str] = None,
        max_records: Optional[int] = None,
        page_size: Optional[int] = None,
        offset: Optional[str] = None,
        fields: Optional[List[str]] = None,
        filter_by_formula: Optional[str] = None,
        sort: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """List records from a table"""
        params = {}
        
        if view:
            params["view"] = view
        if max_records:
            params["maxRecords"] = max_records
        if page_size:
            params["pageSize"] = page_size
        if offset:
            params["offset"] = offset
        if fields:
            params["fields[]"] = fields
        if filter_by_formula:
            params["filterByFormula"] = filter_by_formula
        if sort:
            for i, s in enumerate(sort):
                params[f"sort[{i}][field]"] = s["field"]
                params[f"sort[{i}][direction]"] = s.get("direction", "asc")
        
        return await self._make_request("GET", f"{base_id}/{table_id}", params=params)
    
    async def get_record(self, base_id: str, table_id: str, record_id: str) -> Dict[str, Any]:
        """Get a single record"""
        return await self._make_request("GET", f"{base_id}/{table_id}/{record_id}")
    
    async def create_records(
        self,
        base_id: str,
        table_id: str,
        records: List[Dict[str, Any]],
        typecast: bool = False
    ) -> Dict[str, Any]:
        """Create multiple records"""
        data = {
            "records": records,
            "typecast": typecast
        }
        return await self._make_request("POST", f"{base_id}/{table_id}", data=data, use_cache=False)
    
    async def update_records(
        self,
        base_id: str,
        table_id: str,
        records: List[Dict[str, Any]],
        typecast: bool = False,
        replace: bool = False
    ) -> Dict[str, Any]:
        """Update multiple records"""
        method = "PUT" if replace else "PATCH"
        data = {
            "records": records,
            "typecast": typecast
        }
        return await self._make_request(method, f"{base_id}/{table_id}", data=data, use_cache=False)
    
    async def delete_records(
        self,
        base_id: str,
        table_id: str,
        record_ids: List[str]
    ) -> Dict[str, Any]:
        """Delete multiple records"""
        params = {"records[]": record_ids}
        return await self._make_request("DELETE", f"{base_id}/{table_id}", params=params, use_cache=False)
    
    async def invalidate_cache(self, pattern: Optional[str] = None):
        """Invalidate cache entries"""
        if pattern:
            # Delete specific pattern
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor, match=f"airtable:{pattern}*")
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break
        else:
            # Delete all airtable cache
            cursor = 0
            while True:
                cursor, keys = await self.redis.scan(cursor, match="airtable:*")
                if keys:
                    await self.redis.delete(*keys)
                if cursor == 0:
                    break