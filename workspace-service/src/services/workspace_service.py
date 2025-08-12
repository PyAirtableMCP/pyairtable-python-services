"""Workspace service layer"""
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.future import select
from fastapi import HTTPException, status
import secrets
import uuid

from models.workspace import Workspace, WorkspaceMember, WorkspaceInvitation, WorkspaceRole
from models.schemas import (
    WorkspaceCreate, WorkspaceUpdate, 
    WorkspaceMemberCreate, WorkspaceMemberUpdate,
    WorkspaceInvitationCreate
)
from config import get_workspace_config


class WorkspaceService:
    """Service class for workspace operations"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.config = get_workspace_config()
    
    async def create_workspace(self, workspace_data: WorkspaceCreate, owner_id: str) -> Workspace:
        """Create a new workspace"""
        # Check if user has reached workspace limit (basic implementation)
        user_workspace_count = await self.db.scalar(
            select(func.count(Workspace.id)).where(Workspace.owner_id == owner_id)
        )
        
        if user_workspace_count >= self.config.max_workspaces_per_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum workspace limit reached"
            )
        
        # Create workspace
        workspace = Workspace(
            id=str(uuid.uuid4()),
            name=workspace_data.name,
            description=workspace_data.description,
            template=workspace_data.template,
            owner_id=owner_id,
            is_public=workspace_data.is_public,
            allow_member_invites=workspace_data.allow_member_invites,
            max_members=workspace_data.max_members
        )
        
        self.db.add(workspace)
        await self.db.flush()
        
        # Add owner as member
        owner_member = WorkspaceMember(
            id=str(uuid.uuid4()),
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceRole.OWNER,
            can_edit=True,
            can_delete=True,
            can_invite=True
        )
        
        self.db.add(owner_member)
        await self.db.commit()
        await self.db.refresh(workspace)
        
        return workspace
    
    async def get_workspace(self, workspace_id: str, user_id: str) -> Optional[Workspace]:
        """Get a workspace by ID if user has access"""
        result = await self.db.execute(
            select(Workspace)
            .options(selectinload(Workspace.members), selectinload(Workspace.invitations))
            .where(
                and_(
                    Workspace.id == workspace_id,
                    # User must be a member or workspace must be public
                    (
                        Workspace.members.any(WorkspaceMember.user_id == user_id) |
                        (Workspace.is_public == True)
                    )
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def get_user_workspaces(
        self, 
        user_id: str, 
        skip: int = 0, 
        limit: int = 20
    ) -> Tuple[List[Workspace], int]:
        """Get all workspaces for a user with pagination"""
        # Count total workspaces
        total_count = await self.db.scalar(
            select(func.count(Workspace.id))
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user_id)
        )
        
        # Get workspaces with pagination
        result = await self.db.execute(
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == user_id)
            .order_by(Workspace.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        
        workspaces = result.scalars().all()
        return list(workspaces), total_count or 0
    
    async def update_workspace(
        self, 
        workspace_id: str, 
        workspace_data: WorkspaceUpdate, 
        user_id: str
    ) -> Optional[Workspace]:
        """Update a workspace"""
        # Check if user has permission to update
        workspace = await self._check_workspace_permission(
            workspace_id, user_id, required_permissions=["can_edit"]
        )
        
        # Update fields
        update_data = workspace_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(workspace, field, value)
        
        workspace.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(workspace)
        
        return workspace
    
    async def delete_workspace(self, workspace_id: str, user_id: str) -> bool:
        """Delete a workspace"""
        # Only owner can delete workspace
        workspace = await self.db.scalar(
            select(Workspace).where(
                and_(
                    Workspace.id == workspace_id,
                    Workspace.owner_id == user_id
                )
            )
        )
        
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found or insufficient permissions"
            )
        
        await self.db.delete(workspace)
        await self.db.commit()
        
        return True
    
    async def add_member(
        self, 
        workspace_id: str, 
        member_data: WorkspaceMemberCreate, 
        user_id: str
    ) -> WorkspaceMember:
        """Add a member to workspace"""
        # Check if user has permission to invite
        workspace = await self._check_workspace_permission(
            workspace_id, user_id, required_permissions=["can_invite"]
        )
        
        # Check if member already exists
        existing_member = await self.db.scalar(
            select(WorkspaceMember).where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == member_data.user_id
                )
            )
        )
        
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User is already a member of this workspace"
            )
        
        # Check member limit
        member_count = await self.db.scalar(
            select(func.count(WorkspaceMember.id)).where(
                WorkspaceMember.workspace_id == workspace_id
            )
        )
        
        if member_count >= self.config.max_members_per_workspace:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workspace member limit reached"
            )
        
        # Create member
        member = WorkspaceMember(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            user_id=member_data.user_id,
            role=member_data.role,
            can_edit=member_data.can_edit,
            can_delete=member_data.can_delete,
            can_invite=member_data.can_invite
        )
        
        self.db.add(member)
        await self.db.commit()
        await self.db.refresh(member)
        
        return member
    
    async def update_member(
        self,
        workspace_id: str,
        member_user_id: str,
        member_data: WorkspaceMemberUpdate,
        user_id: str
    ) -> Optional[WorkspaceMember]:
        """Update a workspace member"""
        # Check permissions
        await self._check_workspace_permission(
            workspace_id, user_id, required_permissions=["can_invite"]
        )
        
        # Get member
        member = await self.db.scalar(
            select(WorkspaceMember).where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == member_user_id
                )
            )
        )
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )
        
        # Prevent changing owner role
        if member.role == WorkspaceRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot modify workspace owner"
            )
        
        # Update fields
        update_data = member_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(member, field, value)
        
        await self.db.commit()
        await self.db.refresh(member)
        
        return member
    
    async def remove_member(
        self, 
        workspace_id: str, 
        member_user_id: str, 
        user_id: str
    ) -> bool:
        """Remove a member from workspace"""
        # Check permissions
        await self._check_workspace_permission(
            workspace_id, user_id, required_permissions=["can_invite"]
        )
        
        # Get member
        member = await self.db.scalar(
            select(WorkspaceMember).where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == member_user_id
                )
            )
        )
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Member not found"
            )
        
        # Cannot remove owner
        if member.role == WorkspaceRole.OWNER:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot remove workspace owner"
            )
        
        await self.db.delete(member)
        await self.db.commit()
        
        return True
    
    async def create_invitation(
        self,
        workspace_id: str,
        invitation_data: WorkspaceInvitationCreate,
        user_id: str
    ) -> WorkspaceInvitation:
        """Create a workspace invitation"""
        # Check permissions
        workspace = await self._check_workspace_permission(
            workspace_id, user_id, required_permissions=["can_invite"]
        )
        
        # Check if invitation already exists
        existing_invitation = await self.db.scalar(
            select(WorkspaceInvitation).where(
                and_(
                    WorkspaceInvitation.workspace_id == workspace_id,
                    WorkspaceInvitation.email == invitation_data.email,
                    WorkspaceInvitation.is_accepted == False,
                    WorkspaceInvitation.is_expired == False
                )
            )
        )
        
        if existing_invitation:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invitation already exists for this email"
            )
        
        # Create invitation
        invitation = WorkspaceInvitation(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            email=invitation_data.email,
            role=invitation_data.role,
            invited_by_user_id=user_id,
            invitation_token=secrets.token_urlsafe(self.config.invitation_token_length),
            message=invitation_data.message,
            expires_at=datetime.utcnow() + timedelta(days=self.config.invitation_expiry_days)
        )
        
        self.db.add(invitation)
        await self.db.commit()
        await self.db.refresh(invitation)
        
        return invitation
    
    async def _check_workspace_permission(
        self,
        workspace_id: str,
        user_id: str,
        required_permissions: List[str] = None
    ) -> Workspace:
        """Check if user has permission to perform action on workspace"""
        # Get workspace and member info
        result = await self.db.execute(
            select(Workspace, WorkspaceMember)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                and_(
                    Workspace.id == workspace_id,
                    WorkspaceMember.user_id == user_id
                )
            )
        )
        
        workspace_member = result.first()
        if not workspace_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace not found or access denied"
            )
        
        workspace, member = workspace_member
        
        # Check specific permissions
        if required_permissions:
            for permission in required_permissions:
                if permission == "can_edit" and not member.can_edit:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions to edit"
                    )
                elif permission == "can_delete" and not member.can_delete:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions to delete"
                    )
                elif permission == "can_invite" and not member.can_invite:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Insufficient permissions to invite members"
                    )
        
        return workspace