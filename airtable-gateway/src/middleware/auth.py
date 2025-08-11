"""Authentication middleware for validating requests from API Gateway"""
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to validate requests from API Gateway"""
    
    def __init__(self, app, internal_api_key: Optional[str] = None):
        super().__init__(app)
        self.internal_api_key = internal_api_key
        self.public_paths = {
            "/",
            "/health",
            "/api/v1/health",
            "/api/v1/info",
            "/docs",
            "/openapi.json",
            "/redoc"
        }
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth for public paths
        if request.url.path in self.public_paths:
            return await call_next(request)
        
        # Check for internal API key (for service-to-service calls)
        api_key = request.headers.get("X-API-Key")
        if api_key and self.internal_api_key and api_key == self.internal_api_key:
            return await call_next(request)
        
        # Check for user context headers from API Gateway
        user_id = request.headers.get("X-User-ID")
        tenant_id = request.headers.get("X-Tenant-ID")
        
        if not user_id:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing user context"}
            )
        
        # Add user context to request state
        request.state.user_id = user_id
        request.state.tenant_id = tenant_id
        
        response = await call_next(request)
        return response


class JWTBearer(HTTPBearer):
    """JWT Bearer token validation"""
    
    def __init__(self, auto_error: bool = True):
        super(JWTBearer, self).__init__(auto_error=auto_error)
    
    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        credentials: HTTPAuthorizationCredentials = await super(JWTBearer, self).__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
            # In microservices architecture, the API Gateway validates the JWT
            # and passes user context in headers
            return credentials
        return None