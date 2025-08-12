"""Pydantic schemas for workspace API"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, validator

from models.workspace import WorkspaceRole, WorkspaceTemplate


# Base schemas
class WorkspaceBase(BaseModel):
    """Base workspace schema"""
    name: str = Field(..., min_length=1, max_length=255, description="Workspace name")
    description: Optional[str] = Field(None, max_length=2000, description="Workspace description")
    template: WorkspaceTemplate = Field(WorkspaceTemplate.BLANK, description="Workspace template")
    is_public: bool = Field(False, description="Whether workspace is publicly visible")
    allow_member_invites: bool = Field(True, description="Whether members can invite others")
    max_members: int = Field(100, ge=1, le=1000, description="Maximum number of members")


class WorkspaceCreate(WorkspaceBase):
    """Schema for creating a workspace"""
    pass


class WorkspaceUpdate(BaseModel):
    """Schema for updating a workspace"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, max_length=2000)
    is_public: Optional[bool] = None
    allow_member_invites: Optional[bool] = None
    max_members: Optional[int] = Field(None, ge=1, le=1000)


class WorkspaceMemberBase(BaseModel):
    """Base workspace member schema"""
    role: WorkspaceRole = Field(WorkspaceRole.MEMBER, description="Member role")
    can_edit: bool = Field(True, description="Whether member can edit workspace")
    can_delete: bool = Field(False, description="Whether member can delete items")
    can_invite: bool = Field(False, description="Whether member can invite others")


class WorkspaceMemberCreate(WorkspaceMemberBase):
    """Schema for adding a workspace member"""
    user_id: str = Field(..., description="User ID to add as member")


class WorkspaceMemberUpdate(BaseModel):
    """Schema for updating a workspace member"""
    role: Optional[WorkspaceRole] = None
    can_edit: Optional[bool] = None
    can_delete: Optional[bool] = None
    can_invite: Optional[bool] = None


class WorkspaceMember(WorkspaceMemberBase):
    """Schema for workspace member response"""
    id: str
    workspace_id: str
    user_id: str
    joined_at: datetime
    last_activity_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class WorkspaceInvitationBase(BaseModel):
    """Base workspace invitation schema"""
    email: EmailStr = Field(..., description="Email address to invite")
    role: WorkspaceRole = Field(WorkspaceRole.MEMBER, description="Role for invited user")
    message: Optional[str] = Field(None, max_length=500, description="Optional invitation message")


class WorkspaceInvitationCreate(WorkspaceInvitationBase):
    """Schema for creating a workspace invitation"""
    pass


class WorkspaceInvitation(WorkspaceInvitationBase):
    """Schema for workspace invitation response"""
    id: str
    workspace_id: str
    invited_by_user_id: str
    invitation_token: str
    is_accepted: bool
    is_expired: bool
    created_at: datetime
    expires_at: datetime
    accepted_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class Workspace(WorkspaceBase):
    """Schema for workspace response"""
    id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WorkspaceWithMembers(Workspace):
    """Schema for workspace response with members"""
    members: List[WorkspaceMember] = []
    invitations: List[WorkspaceInvitation] = []


class WorkspaceList(BaseModel):
    """Schema for workspace list response"""
    workspaces: List[Workspace]
    total: int
    page: int = 1
    limit: int = 20
    has_next: bool = False
    has_prev: bool = False


# API Response schemas
class APIResponse(BaseModel):
    """Base API response schema"""
    success: bool = True
    message: str = "Success"
    data: Optional[dict] = None


class WorkspaceResponse(APIResponse):
    """Workspace API response"""
    data: Optional[Workspace] = None


class WorkspaceListResponse(APIResponse):
    """Workspace list API response"""
    data: Optional[WorkspaceList] = None


class WorkspaceMemberResponse(APIResponse):
    """Workspace member API response"""
    data: Optional[WorkspaceMember] = None


class WorkspaceInvitationResponse(APIResponse):
    """Workspace invitation API response"""
    data: Optional[WorkspaceInvitation] = None


# Error schemas
class ErrorResponse(BaseModel):
    """Error response schema"""
    success: bool = False
    message: str
    error_code: Optional[str] = None
    details: Optional[dict] = None