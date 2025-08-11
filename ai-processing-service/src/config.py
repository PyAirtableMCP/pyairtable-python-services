"""Configuration for AI Processing Service (Consolidated MCP + LLM Orchestrator)"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Service configuration"""
    # Service info
    service_name: str = "ai-processing-service"
    service_version: str = "1.0.0"
    
    # Server config
    host: str = "0.0.0.0"
    port: int = 8001  # Use MCP server's original port
    
    # Gemini config (from LLM Orchestrator)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-exp"
    thinking_budget: int = 5
    temperature: float = 0.7
    max_tokens: int = 8192
    
    # MCP config (from MCP Server)
    mcp_mode: str = "http"  # http or stdio
    
    # Database config
    database_url: str = "postgresql://admin:changeme@localhost:5432/pyairtable?sslmode=require"
    
    # Redis config
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""
    session_ttl: int = 3600  # 1 hour for sessions
    cache_ttl: int = 300  # 5 minutes for cache
    
    # Service URLs
    airtable_gateway_url: str = "http://airtable-gateway:8002"
    
    # Airtable config
    airtable_token: str = ""
    airtable_base: str = ""
    
    # Logging
    log_level: str = "INFO"
    
    # CORS
    cors_origins: list[str] = ["*"]
    
    # API Security
    api_key: str = ""
    require_api_key: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()