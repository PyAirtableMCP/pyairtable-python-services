"""Configuration for Analytics service"""
import os
from typing import List, Union
from pydantic import Field
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Service configuration"""
    # Service info
    service_name: str = "analytics-service"
    service_version: str = "1.0.0"
    
    # Server config
    host: str = "0.0.0.0"
    port: int = 8007  # Platform services port as defined in docker-compose
    
    # Database config
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/pyairtable"
    
    # Redis config
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""
    
    # Logging
    log_level: str = "INFO"
    environment: str = "development"
    
    # CORS - Accept string and convert to list
    cors_origins: str = "*"
    
    # Security
    api_key: str = ""
    require_api_key: bool = True
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expires_in: str = "24h"
    
    # Auth Settings
    password_min_length: int = 8
    password_hash_rounds: int = 12
    
    # Analytics Settings
    analytics_retention_days: int = 90
    metrics_batch_size: int = 100
    
    def get_cors_origins_list(self) -> List[str]:
        """Convert CORS origins string to list"""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def get_async_database_url(self) -> str:
        """Get database URL with asyncpg driver"""
        url = self.database_url
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://")
        return url
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()