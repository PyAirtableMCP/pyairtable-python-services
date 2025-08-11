"""Configuration for MCP Server"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Service configuration"""
    # Service info
    service_name: str = "mcp-server"
    service_version: str = "1.0.0"
    
    # Server config
    host: str = "0.0.0.0"
    port: int = 8092
    
    # MCP config
    mcp_mode: str = "http"  # http or stdio
    
    # Service URLs
    airtable_gateway_url: str = "http://airtable-gateway:8093"
    llm_orchestrator_url: str = "http://llm-orchestrator:8091"
    
    # Database config
    database_url: str = "postgresql://admin:changeme@localhost:5432/pyairtable?sslmode=require"
    
    # Redis config
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 300  # 5 minutes
    
    # Airtable
    airtable_token: str = ""
    
    # Logging
    log_level: str = "INFO"
    
    # CORS
    cors_origins: list[str] = ["*"]
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()