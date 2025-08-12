"""SQLAlchemy models for workspace management"""
from datetime import datetime
from enum import Enum
from typing import Optional
from sqlalchemy import String, Text, DateTime, Boolean, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid

from dependencies import Base


class WorkspaceRole(str, Enum):
    """Workspace member roles"""
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class WorkspaceTemplate(str, Enum):
    """Available workspace templates"""
    BLANK = "blank"
    PROJECT_MANAGEMENT = "project_management"
    CRM = "crm"
    CONTENT_CALENDAR = "content_calendar"
    INVENTORY_MANAGEMENT = "inventory_management"
    EVENT_PLANNING = "event_planning"


class Workspace(Base):
    """Workspace model"""
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    template: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default=WorkspaceTemplate.BLANK
    )
    
    # Owner information
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Settings
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_member_invites: Mapped[bool] = mapped_column(Boolean, default=True)
    max_members: Mapped[int] = mapped_column(Integer, default=100)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    # Relationships
    members: Mapped[list["WorkspaceMember"]] = relationship(
        "WorkspaceMember",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )
    invitations: Mapped[list["WorkspaceInvitation"]] = relationship(
        "WorkspaceInvitation",
        back_populates="workspace",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name={self.name})>"


class WorkspaceMember(Base):
    """Workspace member model"""
    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    workspace_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=WorkspaceRole.MEMBER
    )
    
    # Member settings
    can_edit: Mapped[bool] = mapped_column(Boolean, default=True)
    can_delete: Mapped[bool] = mapped_column(Boolean, default=False)
    can_invite: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    joined_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="members"
    )

    def __repr__(self) -> str:
        return f"<WorkspaceMember(workspace_id={self.workspace_id}, user_id={self.user_id}, role={self.role})>"


class WorkspaceInvitation(Base):
    """Workspace invitation model"""
    __tablename__ = "workspace_invitations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "email", name="uq_workspace_invitation_email"),
    )

    id: Mapped[str] = mapped_column(
        String,
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    workspace_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=WorkspaceRole.MEMBER
    )
    
    # Invitation details
    invited_by_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    invitation_token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Status
    is_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_expired: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship(
        "Workspace",
        back_populates="invitations"
    )

    def __repr__(self) -> str:
        return f"<WorkspaceInvitation(workspace_id={self.workspace_id}, email={self.email})>"