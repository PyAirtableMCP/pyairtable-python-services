"""Airtable API routes"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from redis import asyncio as aioredis

from ..services.airtable import AirtableService
from ..dependencies import get_redis_client

router = APIRouter(prefix="/api/v1/airtable", tags=["airtable"])


async def get_airtable_service(redis: aioredis.Redis = Depends(get_redis_client)) -> AirtableService:
    """Get Airtable service instance"""
    return AirtableService(redis)


@router.get("/bases")
async def list_bases(
    service: AirtableService = Depends(get_airtable_service)
) -> List[Dict[str, Any]]:
    """List all accessible Airtable bases"""
    try:
        return await service.list_bases()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bases/{base_id}/schema")
async def get_base_schema(
    base_id: str,
    service: AirtableService = Depends(get_airtable_service)
) -> Dict[str, Any]:
    """Get schema for a specific base"""
    try:
        return await service.get_base_schema(base_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bases/{base_id}/tables/{table_id}/records")
async def list_records(
    base_id: str,
    table_id: str,
    view: Optional[str] = Query(None),
    max_records: Optional[int] = Query(None, ge=1, le=100),
    page_size: Optional[int] = Query(None, ge=1, le=100),
    offset: Optional[str] = Query(None),
    fields: Optional[List[str]] = Query(None),
    filter_by_formula: Optional[str] = Query(None),
    sort_field: Optional[str] = Query(None),
    sort_direction: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    service: AirtableService = Depends(get_airtable_service)
) -> Dict[str, Any]:
    """List records from a table"""
    try:
        sort = None
        if sort_field:
            sort = [{"field": sort_field, "direction": sort_direction}]
        
        return await service.list_records(
            base_id=base_id,
            table_id=table_id,
            view=view,
            max_records=max_records,
            page_size=page_size,
            offset=offset,
            fields=fields,
            filter_by_formula=filter_by_formula,
            sort=sort
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bases/{base_id}/tables/{table_id}/records/{record_id}")
async def get_record(
    base_id: str,
    table_id: str,
    record_id: str,
    service: AirtableService = Depends(get_airtable_service)
) -> Dict[str, Any]:
    """Get a single record"""
    try:
        return await service.get_record(base_id, table_id, record_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bases/{base_id}/tables/{table_id}/records")
async def create_records(
    base_id: str,
    table_id: str,
    records: List[Dict[str, Any]] = Body(..., description="Records to create"),
    typecast: bool = Query(False, description="Enable automatic type casting"),
    service: AirtableService = Depends(get_airtable_service)
) -> Dict[str, Any]:
    """Create new records"""
    try:
        # Format records for Airtable API
        formatted_records = [{"fields": record} for record in records]
        return await service.create_records(base_id, table_id, formatted_records, typecast)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/bases/{base_id}/tables/{table_id}/records")
async def update_records(
    base_id: str,
    table_id: str,
    records: List[Dict[str, Any]] = Body(..., description="Records to update"),
    typecast: bool = Query(False, description="Enable automatic type casting"),
    service: AirtableService = Depends(get_airtable_service)
) -> Dict[str, Any]:
    """Update existing records (partial update)"""
    try:
        # Ensure records have id and fields
        formatted_records = []
        for record in records:
            if "id" not in record:
                raise HTTPException(status_code=400, detail="Each record must have an 'id' field")
            formatted_records.append({
                "id": record["id"],
                "fields": {k: v for k, v in record.items() if k != "id"}
            })
        
        return await service.update_records(base_id, table_id, formatted_records, typecast, replace=False)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/bases/{base_id}/tables/{table_id}/records")
async def replace_records(
    base_id: str,
    table_id: str,
    records: List[Dict[str, Any]] = Body(..., description="Records to replace"),
    typecast: bool = Query(False, description="Enable automatic type casting"),
    service: AirtableService = Depends(get_airtable_service)
) -> Dict[str, Any]:
    """Replace existing records (full update)"""
    try:
        # Ensure records have id and fields
        formatted_records = []
        for record in records:
            if "id" not in record:
                raise HTTPException(status_code=400, detail="Each record must have an 'id' field")
            formatted_records.append({
                "id": record["id"],
                "fields": {k: v for k, v in record.items() if k != "id"}
            })
        
        return await service.update_records(base_id, table_id, formatted_records, typecast, replace=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/bases/{base_id}/tables/{table_id}/records")
async def delete_records(
    base_id: str,
    table_id: str,
    record_ids: List[str] = Query(..., description="Record IDs to delete"),
    service: AirtableService = Depends(get_airtable_service)
) -> Dict[str, Any]:
    """Delete records"""
    try:
        return await service.delete_records(base_id, table_id, record_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cache/invalidate")
async def invalidate_cache(
    pattern: Optional[str] = Query(None, description="Cache key pattern to invalidate"),
    service: AirtableService = Depends(get_airtable_service)
) -> Dict[str, str]:
    """Invalidate cache entries"""
    try:
        await service.invalidate_cache(pattern)
        return {"status": "success", "message": f"Cache invalidated for pattern: {pattern or 'all'}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))