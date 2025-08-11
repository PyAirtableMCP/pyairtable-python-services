"""Configuration for LLM Orchestrator service"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Service configuration"""
    # Service info
    service_name: str = "llm-orchestrator"
    service_version: str = "1.0.0"
    
    # Server config
    host: str = "0.0.0.0"
    port: int = 8091
    
    # Gemini config
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash-exp"
    thinking_budget: int = 5
    temperature: float = 0.7
    max_tokens: int = 8192
    
    # Database config
    database_url: str = "postgresql://admin:changeme@localhost:5432/pyairtable?sslmode=require"
    
    # Redis config
    redis_url: str = "redis://localhost:6379/0"
    session_ttl: int = 3600  # 1 hour
    
    # Service URLs
    mcp_server_url: str = "http://mcp-server:8092"
    
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