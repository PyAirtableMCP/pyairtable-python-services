"""Configuration for Airtable Gateway service"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Service configuration"""
    # Service info
    service_name: str = "airtable-gateway"
    service_version: str = "1.0.0"
    
    # Server config
    host: str = "0.0.0.0"
    port: int = 8002
    
    # Airtable config
    airtable_token: str = ""
    airtable_rate_limit: int = 5  # requests per second
    airtable_timeout: int = 30  # seconds
    use_mock_data: bool = True  # Fallback to mock data when API fails
    
    # Redis config
    redis_url: str = "redis://localhost:6379/0"
    cache_ttl: int = 3600  # 1 hour default
    
    # Logging
    log_level: str = "INFO"
    
    # CORS
    cors_origins: list[str] = ["*"]
    
    # Security
    internal_api_key: str = ""
    jwt_secret: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()