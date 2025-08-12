"""Configuration for Workspace service using centralized config management"""
import os
from typing import List
from pydantic import Field
from functools import lru_cache
import sys
from pathlib import Path

# Add shared config to path
sys.path.append(str(Path(__file__).parent.parent.parent / "shared"))

from config.config_manager import BaseAppConfig, get_config_manager


class WorkspaceConfig(BaseAppConfig):
    """Workspace service configuration with centralized management"""
    
    # Override base service settings
    service_name: str = Field(default="workspace-service", env="SERVICE_NAME")
    port: int = Field(default=8003, env="PORT")
    
    # Workspace-specific settings
    max_workspaces_per_user: int = Field(default=50, env="MAX_WORKSPACES")
    max_members_per_workspace: int = Field(default=100, env="MAX_MEMBERS")
    default_workspace_template: str = Field(default="blank", env="DEFAULT_WORKSPACE_TEMPLATE")
    
    # Invitation settings
    invitation_expiry_days: int = Field(default=7, env="INVITATION_EXPIRY")
    invitation_token_length: int = Field(default=32, env="INVITATION_TOKEN_LENGTH")
    
    # Workspace validation rules
    workspace_min_name_length: int = Field(default=3, env="WORKSPACE_MIN_NAME")
    workspace_max_name_length: int = Field(default=100, env="WORKSPACE_MAX_NAME")
    workspace_max_description_length: int = Field(default=500, env="WORKSPACE_MAX_DESC")
    
    # Default member permissions
    default_member_can_edit: bool = Field(default=True, env="DEFAULT_MEMBER_EDIT")
    default_member_can_delete: bool = Field(default=False, env="DEFAULT_MEMBER_DELETE")
    default_member_can_invite: bool = Field(default=False, env="DEFAULT_MEMBER_INVITE")
    
    # Rate limiting
    workspace_creation_per_hour: int = Field(default=10, env="WORKSPACE_CREATION_LIMIT")
    invitation_sends_per_hour: int = Field(default=50, env="INVITATION_LIMIT")
    
    @classmethod
    def load(cls) -> "WorkspaceConfig":
        """Load configuration with file-based overrides"""
        config_manager = get_config_manager()
        file_config = config_manager.load_config("workspace-service")
        
        # Flatten nested configuration for Pydantic
        flat_config = cls._flatten_config(file_config)
        
        # Create instance with merged configuration
        return cls(**flat_config)
    
    @classmethod
    def _flatten_config(cls, config: dict, prefix: str = '') -> dict:
        """Flatten nested config for Pydantic field mapping"""
        flattened = {}
        
        for key, value in config.items():
            new_key = f"{prefix}_{key}" if prefix else key
            
            if isinstance(value, dict):
                flattened.update(cls._flatten_config(value, new_key))
            else:
                # Map config keys to field names
                field_mappings = {
                    'workspace_max_workspaces_per_user': 'max_workspaces_per_user',
                    'workspace_max_members_per_workspace': 'max_members_per_workspace', 
                    'workspace_default_template': 'default_workspace_template',
                    'workspace_invitation_expiry_days': 'invitation_expiry_days',
                    'workspace_invitation_token_length': 'invitation_token_length',
                    'workspace_min_name_length': 'workspace_min_name_length',
                    'workspace_max_name_length': 'workspace_max_name_length',
                    'workspace_max_description_length': 'workspace_max_description_length',
                    'permissions_default_member_can_edit': 'default_member_can_edit',
                    'permissions_default_member_can_delete': 'default_member_can_delete',
                    'permissions_default_member_can_invite': 'default_member_can_invite',
                    'rate_limits_workspace_creation_per_hour': 'workspace_creation_per_hour',
                    'rate_limits_invitation_sends_per_hour': 'invitation_sends_per_hour',
                }
                
                final_key = field_mappings.get(new_key, new_key)
                flattened[final_key] = value
                
        return flattened
    
    def get_cors_origins_list(self) -> List[str]:
        """Convert CORS origins string to list"""
        cors_str = getattr(self, 'cors_origins', '*')
        if cors_str == "*":
            return ["*"]
        return [origin.strip() for origin in cors_str.split(",")]
    
    def get_async_database_url(self) -> str:
        """Get database URL with asyncpg driver"""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://")
        return url


# Backward compatibility alias for existing code
Settings = WorkspaceConfig


@lru_cache()
def get_workspace_config() -> WorkspaceConfig:
    """Get cached workspace configuration instance"""
    return WorkspaceConfig.load()


@lru_cache() 
def get_settings() -> WorkspaceConfig:
    """Backward compatibility function - returns WorkspaceConfig"""
    return get_workspace_config()