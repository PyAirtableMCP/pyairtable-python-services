"""Airtable API service with caching and rate limiting"""
import asyncio
import json
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta
import httpx
from redis import asyncio as aioredis
import hashlib

from config import get_settings


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
            try:
                async with httpx.AsyncClient(timeout=self.settings.airtable_timeout) as client:
                    response = await client.request(
                        method=method,
                        url=f"{self.base_url}/{path}",
                        headers=self.headers,
                        params=params,
                        json=data
                    )
                    
                    if response.status_code >= 400:
                        error_data = {}
                        try:
                            error_data = response.json()
                        except:
                            error_data = {"error": {"type": "UNKNOWN_ERROR", "message": response.text}}
                        
                        # Enhanced error handling with specific error types
                        if response.status_code == 401:
                            raise Exception(f"Authentication failed: Invalid API token")
                        elif response.status_code == 403:
                            raise Exception(f"Access denied: Insufficient permissions for {path}")
                        elif response.status_code == 404:
                            raise Exception(f"Resource not found: {path}")
                        elif response.status_code == 422:
                            error_msg = error_data.get('error', {}).get('message', 'Validation error')
                            raise Exception(f"Validation error: {error_msg}")
                        elif response.status_code == 429:
                            raise Exception(f"Rate limit exceeded. Please try again later.")
                        else:
                            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
                            raise Exception(f"Airtable API error ({response.status_code}): {error_msg}")
                    
                    result = response.json()
                    
                    # Transform and normalize the response
                    normalized_result = self._normalize_response(result)
                    
                    # Cache successful GET requests
                    if method == "GET" and use_cache:
                        await self._set_cache(cache_key, normalized_result)
                    
                    return normalized_result
            except httpx.TimeoutException:
                raise Exception(f"Request timeout: Airtable API is not responding")
            except httpx.RequestError as e:
                raise Exception(f"Network error: Unable to connect to Airtable API - {str(e)}")
    
    async def list_bases(self) -> List[Dict[str, Any]]:
        """List all accessible bases"""
        try:
            result = await self._make_request("GET", "meta/bases")
            return result.get("bases", [])
        except Exception as e:
            if self.settings.use_mock_data:
                print(f"API failed, using mock data: {e}")
                return self._get_mock_bases()
            raise
    
    async def get_base_schema(self, base_id: str) -> Dict[str, Any]:
        """Get base schema"""
        try:
            return await self._make_request("GET", f"meta/bases/{base_id}/tables")
        except Exception as e:
            if self.settings.use_mock_data:
                print(f"API failed, using mock data: {e}")
                return self._get_mock_base_schema(base_id)
            raise
    
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
        
        try:
            return await self._make_request("GET", f"{base_id}/{table_id}", params=params)
        except Exception as e:
            if self.settings.use_mock_data:
                print(f"API failed, using mock data: {e}")
                return self._get_mock_records(base_id, table_id)
            raise
    
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
    
    def _normalize_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Airtable API responses for consistent structure"""
        if not isinstance(data, dict):
            return data
            
        # Handle different response types
        if 'records' in data:
            # List records response
            return {
                'records': [self._normalize_record(record) for record in data.get('records', [])],
                'offset': data.get('offset'),
                'total': len(data.get('records', [])),
                'hasMore': bool(data.get('offset'))
            }
        elif 'bases' in data:
            # List bases response
            return {
                'bases': [self._normalize_base(base) for base in data.get('bases', [])],
                'total': len(data.get('bases', []))
            }
        elif 'tables' in data:
            # Base schema response
            return {
                'tables': [self._normalize_table(table) for table in data.get('tables', [])],
                'total': len(data.get('tables', []))
            }
        elif 'id' in data and 'fields' in data:
            # Single record response
            return self._normalize_record(data)
        else:
            # Pass through other responses
            return data
    
    def _normalize_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a single record"""
        return {
            'id': record.get('id'),
            'fields': record.get('fields', {}),
            'createdTime': record.get('createdTime'),
            'lastModified': record.get('createdTime')  # Airtable doesn't provide lastModified
        }
    
    def _normalize_base(self, base: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a base object"""
        return {
            'id': base.get('id'),
            'name': base.get('name'),
            'permissionLevel': base.get('permissionLevel', 'read')
        }
    
    def _normalize_table(self, table: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a table object"""
        return {
            'id': table.get('id'),
            'name': table.get('name'),
            'primaryFieldId': table.get('primaryFieldId'),
            'fields': [self._normalize_field(field) for field in table.get('fields', [])],
            'views': [self._normalize_view(view) for view in table.get('views', [])],
            'description': table.get('description')
        }
    
    def _normalize_field(self, field: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a field object"""
        return {
            'id': field.get('id'),
            'name': field.get('name'),
            'type': field.get('type'),
            'options': field.get('options', {}),
            'description': field.get('description')
        }
    
    def _normalize_view(self, view: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a view object"""
        return {
            'id': view.get('id'),
            'name': view.get('name'),
            'type': view.get('type'),
            'visibleFieldIds': view.get('visibleFieldIds', [])
        }
    
    def _get_mock_bases(self) -> List[Dict[str, Any]]:
        """Return mock bases for development"""
        return [
            {
                'id': 'appMockBase001',
                'name': 'Demo Workspace',
                'permissionLevel': 'read'
            },
            {
                'id': 'appMockBase002',
                'name': 'Sample Database',
                'permissionLevel': 'edit'
            }
        ]
    
    def _get_mock_base_schema(self, base_id: str) -> Dict[str, Any]:
        """Return mock base schema"""
        return {
            'tables': [
                {
                    'id': 'tblMockTable001',
                    'name': 'Contacts',
                    'primaryFieldId': 'fldMockField001',
                    'fields': [
                        {
                            'id': 'fldMockField001',
                            'name': 'Name',
                            'type': 'singleLineText',
                            'options': {}
                        },
                        {
                            'id': 'fldMockField002',
                            'name': 'Email',
                            'type': 'email',
                            'options': {}
                        },
                        {
                            'id': 'fldMockField003',
                            'name': 'Phone',
                            'type': 'phoneNumber',
                            'options': {}
                        }
                    ],
                    'views': [
                        {
                            'id': 'viwMockView001',
                            'name': 'Grid view',
                            'type': 'grid',
                            'visibleFieldIds': ['fldMockField001', 'fldMockField002', 'fldMockField003']
                        }
                    ]
                },
                {
                    'id': 'tblMockTable002',
                    'name': 'Companies',
                    'primaryFieldId': 'fldMockField004',
                    'fields': [
                        {
                            'id': 'fldMockField004',
                            'name': 'Company Name',
                            'type': 'singleLineText',
                            'options': {}
                        },
                        {
                            'id': 'fldMockField005',
                            'name': 'Industry',
                            'type': 'singleSelect',
                            'options': {
                                'choices': [
                                    {'id': 'selTech', 'name': 'Technology'},
                                    {'id': 'selFinance', 'name': 'Finance'}
                                ]
                            }
                        }
                    ],
                    'views': [
                        {
                            'id': 'viwMockView002',
                            'name': 'Grid view',
                            'type': 'grid',
                            'visibleFieldIds': ['fldMockField004', 'fldMockField005']
                        }
                    ]
                }
            ],
            'total': 2
        }
    
    def _get_mock_records(self, base_id: str, table_id: str) -> Dict[str, Any]:
        """Return mock records"""
        if table_id == 'tblMockTable001':  # Contacts
            records = [
                {
                    'id': 'recMockRecord001',
                    'fields': {
                        'Name': 'John Doe',
                        'Email': 'john@example.com',
                        'Phone': '+1-555-0123'
                    },
                    'createdTime': '2024-01-01T10:00:00.000Z'
                },
                {
                    'id': 'recMockRecord002',
                    'fields': {
                        'Name': 'Jane Smith',
                        'Email': 'jane@example.com',
                        'Phone': '+1-555-0456'
                    },
                    'createdTime': '2024-01-02T10:00:00.000Z'
                }
            ]
        else:  # Companies
            records = [
                {
                    'id': 'recMockRecord003',
                    'fields': {
                        'Company Name': 'Acme Corp',
                        'Industry': 'Technology'
                    },
                    'createdTime': '2024-01-01T12:00:00.000Z'
                },
                {
                    'id': 'recMockRecord004',
                    'fields': {
                        'Company Name': 'Example Ltd',
                        'Industry': 'Finance'
                    },
                    'createdTime': '2024-01-02T12:00:00.000Z'
                }
            ]
        
        return {
            'records': [self._normalize_record(record) for record in records],
            'total': len(records),
            'hasMore': False
        }
