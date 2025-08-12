"""Authentication and authorization middleware"""
from typing import Optional
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import structlog

from config import get_settings

logger = structlog.get_logger()
settings = get_settings()
security = HTTPBearer()


async def verify_api_key(request: Request) -> bool:
    """Verify API key from request headers"""
    if not settings.require_api_key:
        return True
    
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required"
        )
    
    if api_key != settings.api_key:
        logger.warning("Invalid API key attempt", 
                      client_ip=request.client.host if request.client else "unknown")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return True


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """Extract user information from JWT token"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm]
        )
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Extract additional user info if available
        user_data = {
            "id": user_id,
            "email": payload.get("email"),
            "name": payload.get("name"),
            "role": payload.get("role", "user"),
            "permissions": payload.get("permissions", [])
        }
        
        return user_data
        
    except JWTError as e:
        logger.warning("JWT validation failed", error=str(e))
        raise credentials_exception


async def get_current_user_id(
    user: dict = Depends(get_current_user)
) -> str:
    """Get current user ID"""
    return user["id"]


class RequirePermissions:
    """Dependency to require specific permissions"""
    
    def __init__(self, *permissions: str):
        self.permissions = permissions
    
    def __call__(self, user: dict = Depends(get_current_user)) -> dict:
        user_permissions = user.get("permissions", [])
        
        for permission in self.permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permission: {permission}"
                )
        
        return user


class RequireRole:
    """Dependency to require specific role"""
    
    def __init__(self, *roles: str):
        self.roles = roles
    
    def __call__(self, user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role")
        
        if user_role not in self.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient role. Required: {', '.join(self.roles)}"
            )
        
        return user


# Convenience dependencies for common roles
require_admin = RequireRole("admin", "super_admin")
require_user = RequireRole("user", "admin", "super_admin")

# Common permission requirements
require_workspace_create = RequirePermissions("workspace:create")
require_workspace_manage = RequirePermissions("workspace:manage")
require_workspace_delete = RequirePermissions("workspace:delete")