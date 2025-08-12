"""Workspace management endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from dependencies import get_db
from middleware.auth import get_current_user_id, verify_api_key
from services.workspace_service import WorkspaceService
from models.schemas import (
    WorkspaceCreate, WorkspaceUpdate, Workspace, WorkspaceList,
    WorkspaceMemberCreate, WorkspaceMemberUpdate, WorkspaceMember,
    WorkspaceInvitationCreate, WorkspaceInvitation,
    WorkspaceResponse, WorkspaceListResponse, 
    WorkspaceMemberResponse, WorkspaceInvitationResponse,
    APIResponse, ErrorResponse
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1", dependencies=[Depends(verify_api_key)])


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Create a new workspace"""
    try:
        service = WorkspaceService(db)
        workspace = await service.create_workspace(workspace_data, current_user_id)
        
        logger.info("Workspace created", 
                   workspace_id=workspace.id, 
                   user_id=current_user_id,
                   workspace_name=workspace.name)
        
        return WorkspaceResponse(
            message="Workspace created successfully",
            data=workspace
        )
    except Exception as e:
        logger.error("Failed to create workspace", 
                    error=str(e), 
                    user_id=current_user_id)
        raise


@router.get("/workspaces", response_model=WorkspaceListResponse)
async def list_workspaces(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """List user's workspaces with pagination"""
    try:
        service = WorkspaceService(db)
        skip = (page - 1) * limit
        workspaces, total = await service.get_user_workspaces(
            current_user_id, skip=skip, limit=limit
        )
        
        has_next = (skip + limit) < total
        has_prev = page > 1
        
        workspace_list = WorkspaceList(
            workspaces=workspaces,
            total=total,
            page=page,
            limit=limit,
            has_next=has_next,
            has_prev=has_prev
        )
        
        return WorkspaceListResponse(
            message="Workspaces retrieved successfully",
            data=workspace_list
        )
    except Exception as e:
        logger.error("Failed to list workspaces", 
                    error=str(e), 
                    user_id=current_user_id)
        raise


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Get a specific workspace"""
    try:
        service = WorkspaceService(db)
        workspace = await service.get_workspace(workspace_id, current_user_id)
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found or access denied"
            )
        
        return WorkspaceResponse(
            message="Workspace retrieved successfully",
            data=workspace
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get workspace", 
                    workspace_id=workspace_id,
                    error=str(e), 
                    user_id=current_user_id)
        raise


@router.put("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    workspace_data: WorkspaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Update a workspace"""
    try:
        service = WorkspaceService(db)
        workspace = await service.update_workspace(
            workspace_id, workspace_data, current_user_id
        )
        
        logger.info("Workspace updated", 
                   workspace_id=workspace_id, 
                   user_id=current_user_id)
        
        return WorkspaceResponse(
            message="Workspace updated successfully",
            data=workspace
        )
    except Exception as e:
        logger.error("Failed to update workspace", 
                    workspace_id=workspace_id,
                    error=str(e), 
                    user_id=current_user_id)
        raise


@router.delete("/workspaces/{workspace_id}", response_model=APIResponse)
async def delete_workspace(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Delete a workspace"""
    try:
        service = WorkspaceService(db)
        await service.delete_workspace(workspace_id, current_user_id)
        
        logger.info("Workspace deleted", 
                   workspace_id=workspace_id, 
                   user_id=current_user_id)
        
        return APIResponse(message="Workspace deleted successfully")
    except Exception as e:
        logger.error("Failed to delete workspace", 
                    workspace_id=workspace_id,
                    error=str(e), 
                    user_id=current_user_id)
        raise


# Member management endpoints
@router.post("/workspaces/{workspace_id}/members", 
            response_model=WorkspaceMemberResponse, 
            status_code=status.HTTP_201_CREATED)
async def add_workspace_member(
    workspace_id: str,
    member_data: WorkspaceMemberCreate,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Add a member to workspace"""
    try:
        service = WorkspaceService(db)
        member = await service.add_member(workspace_id, member_data, current_user_id)
        
        logger.info("Member added to workspace", 
                   workspace_id=workspace_id,
                   member_user_id=member_data.user_id,
                   added_by=current_user_id)
        
        return WorkspaceMemberResponse(
            message="Member added successfully",
            data=member
        )
    except Exception as e:
        logger.error("Failed to add member", 
                    workspace_id=workspace_id,
                    member_user_id=member_data.user_id,
                    error=str(e), 
                    user_id=current_user_id)
        raise


@router.put("/workspaces/{workspace_id}/members/{member_user_id}", 
           response_model=WorkspaceMemberResponse)
async def update_workspace_member(
    workspace_id: str,
    member_user_id: str,
    member_data: WorkspaceMemberUpdate,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Update a workspace member"""
    try:
        service = WorkspaceService(db)
        member = await service.update_member(
            workspace_id, member_user_id, member_data, current_user_id
        )
        
        logger.info("Member updated", 
                   workspace_id=workspace_id,
                   member_user_id=member_user_id,
                   updated_by=current_user_id)
        
        return WorkspaceMemberResponse(
            message="Member updated successfully",
            data=member
        )
    except Exception as e:
        logger.error("Failed to update member", 
                    workspace_id=workspace_id,
                    member_user_id=member_user_id,
                    error=str(e), 
                    user_id=current_user_id)
        raise


@router.delete("/workspaces/{workspace_id}/members/{member_user_id}", 
              response_model=APIResponse)
async def remove_workspace_member(
    workspace_id: str,
    member_user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Remove a member from workspace"""
    try:
        service = WorkspaceService(db)
        await service.remove_member(workspace_id, member_user_id, current_user_id)
        
        logger.info("Member removed from workspace", 
                   workspace_id=workspace_id,
                   member_user_id=member_user_id,
                   removed_by=current_user_id)
        
        return APIResponse(message="Member removed successfully")
    except Exception as e:
        logger.error("Failed to remove member", 
                    workspace_id=workspace_id,
                    member_user_id=member_user_id,
                    error=str(e), 
                    user_id=current_user_id)
        raise


# Invitation endpoints
@router.post("/workspaces/{workspace_id}/invitations", 
            response_model=WorkspaceInvitationResponse, 
            status_code=status.HTTP_201_CREATED)
async def create_workspace_invitation(
    workspace_id: str,
    invitation_data: WorkspaceInvitationCreate,
    db: AsyncSession = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id)
):
    """Create a workspace invitation"""
    try:
        service = WorkspaceService(db)
        invitation = await service.create_invitation(
            workspace_id, invitation_data, current_user_id
        )
        
        logger.info("Workspace invitation created", 
                   workspace_id=workspace_id,
                   email=invitation_data.email,
                   invited_by=current_user_id)
        
        return WorkspaceInvitationResponse(
            message="Invitation created successfully",
            data=invitation
        )
    except Exception as e:
        logger.error("Failed to create invitation", 
                    workspace_id=workspace_id,
                    email=invitation_data.email,
                    error=str(e), 
                    user_id=current_user_id)
        raise