"""
Table analysis API endpoints
"""
import asyncio
import json
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
import logging

from services.table_analysis import TableAnalysisService, AnalysisCategory, TableMetadata, AnalysisResult
from dependencies import get_redis_client
from config import get_settings
from models.chat import Message, MessageRole, ChatRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analysis", tags=["table-analysis"])


class TableAnalysisRequest(BaseModel):
    """Request for table analysis"""
    base_id: str = Field(..., description="Airtable base ID")
    table_id: str = Field(..., description="Airtable table ID")
    table_name: str = Field(..., description="Table name")
    fields: List[Dict[str, Any]] = Field(..., description="Table fields metadata")
    categories: Optional[List[AnalysisCategory]] = Field(default=None, description="Analysis categories to run")
    record_count: Optional[int] = Field(default=None, description="Number of records in table")
    relationships: Optional[List[Dict[str, Any]]] = Field(default=None, description="Table relationships")
    views: Optional[List[Dict[str, Any]]] = Field(default=None, description="Table views")


class BatchAnalysisRequest(BaseModel):
    """Request for batch table analysis"""
    tables: List[TableAnalysisRequest] = Field(..., description="Tables to analyze")
    batch_size: int = Field(default=5, description="Batch size for processing")
    max_concurrent: int = Field(default=3, description="Maximum concurrent analyses")
    categories: Optional[List[AnalysisCategory]] = Field(default=None, description="Analysis categories for all tables")


class AnalysisJobStatus(BaseModel):
    """Status of analysis job"""
    job_id: str
    status: str  # pending, running, completed, failed
    progress: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
    cost_summary: Optional[Dict[str, Any]] = None


class TableAnalysisResponse(BaseModel):
    """Response for table analysis"""
    table_id: str
    table_name: str
    analysis_results: Dict[str, List[Dict[str, Any]]]
    cost_summary: Dict[str, Any]
    analysis_duration_seconds: float
    timestamp: str


class BatchAnalysisResponse(BaseModel):
    """Response for batch analysis"""
    job_id: str
    total_tables: int
    completed_tables: int
    results: Dict[str, TableAnalysisResponse]
    cost_summary: Dict[str, Any]
    duration_seconds: float
    timestamp: str


# In-memory storage for job status (in production, use Redis or database)
analysis_jobs: Dict[str, AnalysisJobStatus] = {}


@router.post("/table", response_model=TableAnalysisResponse)
async def analyze_single_table(
    request: TableAnalysisRequest,
    background_tasks: BackgroundTasks
) -> TableAnalysisResponse:
    """
    Analyze a single table for optimization opportunities
    """
    try:
        import time
        start_time = time.time()
        
        # Create analysis service
        analysis_service = TableAnalysisService()
        
        # Convert request to TableMetadata
        table_data = TableMetadata(
            base_id=request.base_id,
            table_id=request.table_id,
            table_name=request.table_name,
            fields=request.fields,
            record_count=request.record_count,
            relationships=request.relationships,
            views=request.views
        )
        
        # Perform analysis
        results = await analysis_service.analyze_table_comprehensive(
            table_data=table_data,
            categories=request.categories or list(AnalysisCategory)
        )
        
        # Convert results to dict format
        dict_results = {}
        for category, analysis_list in results.items():
            dict_results[category] = [result.to_dict() for result in analysis_list]
        
        duration = time.time() - start_time
        cost_summary = analysis_service.get_cost_summary()
        
        return TableAnalysisResponse(
            table_id=request.table_id,
            table_name=request.table_name,
            analysis_results=dict_results,
            cost_summary=cost_summary,
            analysis_duration_seconds=duration,
            timestamp=time.time()
        )
        
    except Exception as e:
        logger.error(f"Error analyzing table {request.table_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/batch", response_model=Dict[str, str])
async def start_batch_analysis(
    request: BatchAnalysisRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Start batch analysis of multiple tables (async)
    """
    try:
        import uuid
        from datetime import datetime
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Create job status
        job_status = AnalysisJobStatus(
            job_id=job_id,
            status="pending",
            progress={"completed": 0, "total": len(request.tables)},
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        
        analysis_jobs[job_id] = job_status
        
        # Start background task
        background_tasks.add_task(
            _run_batch_analysis,
            job_id,
            request
        )
        
        return {"job_id": job_id, "status": "started"}
        
    except Exception as e:
        logger.error(f"Error starting batch analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start batch analysis: {str(e)}")


@router.get("/batch/{job_id}/status", response_model=AnalysisJobStatus)
async def get_batch_status(job_id: str) -> AnalysisJobStatus:
    """
    Get status of batch analysis job
    """
    if job_id not in analysis_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return analysis_jobs[job_id]


@router.get("/batch/{job_id}/results")
async def get_batch_results(job_id: str) -> Dict[str, Any]:
    """
    Get results of completed batch analysis
    """
    if job_id not in analysis_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = analysis_jobs[job_id]
    
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job not completed. Status: {job.status}")
    
    return job.results or {}


@router.get("/estimate-cost")
async def estimate_analysis_cost(
    table_count: int = Query(..., description="Number of tables to analyze"),
    categories: Optional[List[AnalysisCategory]] = Query(default=None, description="Analysis categories")
) -> Dict[str, Any]:
    """
    Estimate cost for table analysis
    """
    try:
        analysis_service = TableAnalysisService()
        estimate = analysis_service.estimate_batch_cost(
            table_count=table_count,
            categories=categories or list(AnalysisCategory)
        )
        return estimate
        
    except Exception as e:
        logger.error(f"Error estimating cost: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cost estimation failed: {str(e)}")


@router.get("/categories")
async def get_analysis_categories() -> Dict[str, Any]:
    """
    Get available analysis categories
    """
    categories = {}
    for category in AnalysisCategory:
        categories[category.value] = {
            "name": category.value,
            "description": _get_category_description(category)
        }
    
    return {
        "categories": categories,
        "total_count": len(AnalysisCategory)
    }


@router.post("/custom-prompt", response_model=Dict[str, Any])
async def analyze_with_custom_prompt(
    request: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Analyze table with custom prompt for specialized analysis
    """
    try:
        # Validate required fields
        required_fields = ["table_data", "custom_prompt"]
        for field in required_fields:
            if field not in request:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Create analysis service
        analysis_service = TableAnalysisService()
        
        # Create chat request with custom prompt
        messages = [
            Message(role=MessageRole.SYSTEM, content="You are an expert Airtable optimization consultant."),
            Message(role=MessageRole.USER, content=request["custom_prompt"])
        ]
        
        chat_request = ChatRequest(
            messages=messages,
            model=request.get("model", analysis_service.settings.gemini_model),
            temperature=request.get("temperature", 0.1),
            max_tokens=request.get("max_tokens", 4000)
        )
        
        # Get LLM response
        response = await analysis_service.gemini_service.complete(chat_request)
        
        return {
            "response": response.choices[0]["message"]["content"],
            "usage": response.usage,
            "model": response.model,
            "timestamp": response.created
        }
        
    except Exception as e:
        logger.error(f"Error with custom prompt analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Custom analysis failed: {str(e)}")


@router.get("/health")
async def analysis_health() -> Dict[str, Any]:
    """
    Health check for analysis service
    """
    try:
        # Test Gemini service connection
        analysis_service = TableAnalysisService()
        
        # Simple test request
        test_request = ChatRequest(
            messages=[
                Message(role=MessageRole.USER, content="Hello, respond with 'OK' if you're working.")
            ],
            model=analysis_service.settings.gemini_model,
            max_tokens=10
        )
        
        response = await analysis_service.gemini_service.complete(test_request)
        
        return {
            "status": "healthy",
            "gemini_service": "connected",
            "model": response.model,
            "active_jobs": len([j for j in analysis_jobs.values() if j.status == "running"]),
            "total_jobs": len(analysis_jobs)
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "gemini_service": "disconnected"
        }


async def _run_batch_analysis(job_id: str, request: BatchAnalysisRequest):
    """
    Background task to run batch analysis
    """
    import time
    from datetime import datetime
    
    start_time = time.time()
    
    try:
        # Update job status
        analysis_jobs[job_id].status = "running"
        analysis_jobs[job_id].updated_at = datetime.utcnow().isoformat()
        
        # Create analysis service
        analysis_service = TableAnalysisService()
        
        # Convert requests to TableMetadata
        tables = []
        for table_request in request.tables:
            table_data = TableMetadata(
                base_id=table_request.base_id,
                table_id=table_request.table_id,
                table_name=table_request.table_name,
                fields=table_request.fields,
                record_count=table_request.record_count,
                relationships=table_request.relationships,
                views=table_request.views
            )
            tables.append(table_data)
        
        # Run batch analysis
        results = await analysis_service.analyze_tables_batch(
            tables=tables,
            batch_size=request.batch_size,
            max_concurrent=request.max_concurrent
        )
        
        # Convert results to response format
        response_results = {}
        for table_id, table_results in results.items():
            table_data = next(t for t in tables if t.table_id == table_id)
            
            dict_results = {}
            for category, analysis_list in table_results.items():
                dict_results[category] = [result.to_dict() for result in analysis_list]
            
            response_results[table_id] = TableAnalysisResponse(
                table_id=table_id,
                table_name=table_data.table_name,
                analysis_results=dict_results,
                cost_summary=analysis_service.get_cost_summary(),
                analysis_duration_seconds=time.time() - start_time,
                timestamp=time.time()
            ).dict()
        
        # Create final response
        batch_response = BatchAnalysisResponse(
            job_id=job_id,
            total_tables=len(request.tables),
            completed_tables=len(response_results),
            results=response_results,
            cost_summary=analysis_service.get_cost_summary(),
            duration_seconds=time.time() - start_time,
            timestamp=time.time()
        )
        
        # Update job with results
        analysis_jobs[job_id].status = "completed"
        analysis_jobs[job_id].results = batch_response.dict()
        analysis_jobs[job_id].cost_summary = analysis_service.get_cost_summary()
        analysis_jobs[job_id].updated_at = datetime.utcnow().isoformat()
        analysis_jobs[job_id].progress = {"completed": len(response_results), "total": len(request.tables)}
        
        logger.info(f"Batch analysis {job_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Batch analysis {job_id} failed: {str(e)}")
        analysis_jobs[job_id].status = "failed"
        analysis_jobs[job_id].error = str(e)
        analysis_jobs[job_id].updated_at = datetime.utcnow().isoformat()


def _get_category_description(category: AnalysisCategory) -> str:
    """Get description for analysis category"""
    descriptions = {
        AnalysisCategory.STRUCTURE: "Analyze table structure, field organization, and design patterns",
        AnalysisCategory.NORMALIZATION: "Identify normalization opportunities and data redundancy issues",
        AnalysisCategory.FIELD_TYPES: "Optimize field types, configurations, and validation rules",
        AnalysisCategory.RELATIONSHIPS: "Analyze table relationships and linking opportunities",
        AnalysisCategory.PERFORMANCE: "Identify performance bottlenecks and optimization opportunities",
        AnalysisCategory.DATA_QUALITY: "Assess data quality, consistency, and validation needs",
        AnalysisCategory.NAMING_CONVENTIONS: "Review naming conventions and standardization",
        AnalysisCategory.INDEXING: "Analyze indexing and query optimization opportunities"
    }
    return descriptions.get(category, "General analysis category")