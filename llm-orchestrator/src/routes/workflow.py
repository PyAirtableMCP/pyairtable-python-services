"""
Workflow orchestration API endpoints
"""
import asyncio
import os
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, Field
import logging

from services.workflow_orchestrator import WorkflowOrchestrator, WorkflowConfig
from services.table_analysis import AnalysisCategory
from config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/workflow", tags=["workflow"])


class CompleteWorkflowRequest(BaseModel):
    """Request for complete analysis workflow"""
    mcp_server_url: str = Field(default="http://mcp-server:8001", description="MCP server URL")
    airtable_base_id: str = Field(default_factory=lambda: os.getenv("AIRTABLE_BASE", ""), description="Base ID containing metadata table (defaults to AIRTABLE_BASE env var)")
    metadata_table_id: str = Field(..., description="Table ID for storing analysis results")
    target_base_ids: Optional[List[str]] = Field(default=None, description="Specific bases to analyze")
    batch_size: int = Field(default=5, description="Batch size for processing")
    max_concurrent: int = Field(default=3, description="Maximum concurrent analyses")
    categories: Optional[List[AnalysisCategory]] = Field(default=None, description="Analysis categories")
    auto_update_airtable: bool = Field(default=True, description="Auto-update Airtable with results")
    quality_threshold: float = Field(default=0.7, description="Quality threshold for recommendations")


class WorkflowStatusResponse(BaseModel):
    """Response for workflow status"""
    workflow_id: str
    status: str
    progress: Dict[str, Any]
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: str
    updated_at: str


# In-memory storage for workflow status
workflow_jobs: Dict[str, Dict[str, Any]] = {}


@router.post("/start-complete-analysis")
async def start_complete_workflow(
    request: CompleteWorkflowRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, str]:
    """
    Start complete table analysis workflow
    
    This endpoint orchestrates the entire process:
    1. Discover all tables in specified bases
    2. Run comprehensive analysis on each table
    3. Process and quality-check results
    4. Update Airtable metadata with recommendations
    """
    try:
        import uuid
        from datetime import datetime
        
        # Generate workflow ID
        workflow_id = str(uuid.uuid4())
        
        # Create workflow status
        workflow_jobs[workflow_id] = {
            "workflow_id": workflow_id,
            "status": "pending",
            "progress": {"phase": "initializing", "completed": 0, "total": 0},
            "started_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "request": request.dict()
        }
        
        # Start background task
        background_tasks.add_task(
            _run_complete_workflow,
            workflow_id,
            request
        )
        
        return {
            "workflow_id": workflow_id,
            "status": "started",
            "message": "Complete analysis workflow started"
        }
        
    except Exception as e:
        logger.error(f"Error starting complete workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start workflow: {str(e)}")


@router.get("/status/{workflow_id}")
async def get_workflow_status(workflow_id: str) -> WorkflowStatusResponse:
    """Get status of running workflow"""
    if workflow_id not in workflow_jobs:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    job = workflow_jobs[workflow_id]
    
    return WorkflowStatusResponse(
        workflow_id=job["workflow_id"],
        status=job["status"],
        progress=job["progress"],
        results=job.get("results"),
        error=job.get("error"),
        started_at=job["started_at"],
        updated_at=job["updated_at"]
    )


@router.get("/results/{workflow_id}")
async def get_workflow_results(workflow_id: str) -> Dict[str, Any]:
    """Get detailed results of completed workflow"""
    if workflow_id not in workflow_jobs:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    job = workflow_jobs[workflow_id]
    
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400, 
            detail=f"Workflow not completed. Status: {job['status']}"
        )
    
    return job.get("results", {})


@router.get("/active-workflows")
async def get_active_workflows() -> Dict[str, Any]:
    """Get list of active workflows"""
    active = []
    completed = []
    failed = []
    
    for workflow_id, job in workflow_jobs.items():
        job_info = {
            "workflow_id": workflow_id,
            "status": job["status"],
            "started_at": job["started_at"],
            "progress": job["progress"]
        }
        
        if job["status"] in ["pending", "running"]:
            active.append(job_info)
        elif job["status"] == "completed":
            completed.append(job_info)
        else:
            failed.append(job_info)
    
    return {
        "active_workflows": active,
        "completed_workflows": completed,
        "failed_workflows": failed,
        "total_workflows": len(workflow_jobs)
    }


@router.delete("/workflow/{workflow_id}")
async def cancel_workflow(workflow_id: str) -> Dict[str, str]:
    """Cancel a running workflow (best effort)"""
    if workflow_id not in workflow_jobs:
        raise HTTPException(status_code=404, detail="Workflow not found")
    
    job = workflow_jobs[workflow_id]
    
    if job["status"] in ["pending", "running"]:
        job["status"] = "cancelled"
        job["updated_at"] = datetime.utcnow().isoformat()
        return {"message": "Workflow cancellation requested"}
    else:
        return {"message": f"Workflow is {job['status']} and cannot be cancelled"}


@router.post("/estimate-workflow-cost")
async def estimate_workflow_cost(
    request: CompleteWorkflowRequest
) -> Dict[str, Any]:
    """
    Estimate cost and time for complete workflow
    """
    try:
        # Create temporary orchestrator to estimate
        config = WorkflowConfig(
            mcp_server_url=request.mcp_server_url,
            airtable_base_id=request.airtable_base_id,
            metadata_table_id=request.metadata_table_id,
            batch_size=request.batch_size,
            max_concurrent=request.max_concurrent,
            categories=request.categories,
            auto_update_airtable=request.auto_update_airtable,
            quality_threshold=request.quality_threshold
        )
        
        # Estimate table count (simplified)
        # In practice, you'd call the MCP server to get actual counts
        estimated_table_count = 35  # Based on the requirement
        
        # Use analysis service for cost estimation
        from services.table_analysis import TableAnalysisService
        analysis_service = TableAnalysisService()
        
        estimate = analysis_service.estimate_batch_cost(
            table_count=estimated_table_count,
            categories=request.categories or list(AnalysisCategory)
        )
        
        # Add workflow overhead estimates
        estimate["workflow_overhead"] = {
            "table_discovery_time_minutes": 2,
            "result_processing_time_minutes": 3,
            "airtable_updates_time_minutes": 5,
            "total_overhead_minutes": 10
        }
        
        estimate["total_estimated_time_minutes"] = (
            estimate["estimated_time_minutes"] + 
            estimate["workflow_overhead"]["total_overhead_minutes"]
        )
        
        return estimate
        
    except Exception as e:
        logger.error(f"Error estimating workflow cost: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Cost estimation failed: {str(e)}")


@router.get("/workflow-health")
async def workflow_health() -> Dict[str, Any]:
    """Health check for workflow orchestration"""
    try:
        settings = get_settings()
        
        # Test MCP server connection
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                # Default MCP server URL
                mcp_url = "http://mcp-server:8001"
                response = await client.get(f"{mcp_url}/health")
                mcp_status = "connected" if response.status_code == 200 else "error"
            except:
                mcp_status = "unreachable"
        
        return {
            "status": "healthy",
            "mcp_server_status": mcp_status,
            "active_workflows": len([j for j in workflow_jobs.values() if j["status"] == "running"]),
            "total_workflows": len(workflow_jobs),
            "service_features": [
                "Complete workflow orchestration",
                "Table discovery",
                "Batch analysis",
                "Quality filtering",
                "Airtable integration",
                "Cost estimation",
                "Progress tracking"
            ]
        }
        
    except Exception as e:
        logger.error(f"Workflow health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }


async def _run_complete_workflow(workflow_id: str, request: CompleteWorkflowRequest):
    """Background task to run complete workflow"""
    from datetime import datetime
    
    try:
        # Update status
        workflow_jobs[workflow_id]["status"] = "running"
        workflow_jobs[workflow_id]["progress"] = {"phase": "starting", "completed": 0, "total": 1}
        workflow_jobs[workflow_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # Create workflow configuration
        config = WorkflowConfig(
            mcp_server_url=request.mcp_server_url,
            airtable_base_id=request.airtable_base_id,
            metadata_table_id=request.metadata_table_id,
            batch_size=request.batch_size,
            max_concurrent=request.max_concurrent,
            categories=request.categories,
            auto_update_airtable=request.auto_update_airtable,
            quality_threshold=request.quality_threshold
        )
        
        # Run workflow
        async with WorkflowOrchestrator(config) as orchestrator:
            # Update progress callback
            async def update_progress(phase: str, completed: int, total: int):
                if workflow_id in workflow_jobs:
                    workflow_jobs[workflow_id]["progress"] = {
                        "phase": phase,
                        "completed": completed,
                        "total": total
                    }
                    workflow_jobs[workflow_id]["updated_at"] = datetime.utcnow().isoformat()
            
            # Run the complete workflow
            results = await orchestrator.run_complete_workflow(
                base_ids=request.target_base_ids
            )
            
            # Update final status
            workflow_jobs[workflow_id]["status"] = "completed"
            workflow_jobs[workflow_id]["results"] = results
            workflow_jobs[workflow_id]["progress"] = {
                "phase": "completed",
                "completed": results.get("tables_analyzed", 0),
                "total": results.get("tables_discovered", 0)
            }
            workflow_jobs[workflow_id]["updated_at"] = datetime.utcnow().isoformat()
            
            logger.info(f"Workflow {workflow_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Workflow {workflow_id} failed: {str(e)}")
        workflow_jobs[workflow_id]["status"] = "failed"
        workflow_jobs[workflow_id]["error"] = str(e)
        workflow_jobs[workflow_id]["updated_at"] = datetime.utcnow().isoformat()