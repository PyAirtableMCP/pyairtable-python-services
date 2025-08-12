"""
Centralized configuration management for pyairtable services.
Provides a three-tier configuration system: env vars -> config files -> runtime overrides.
"""
from typing import Dict, Any, Optional, Union
from pathlib import Path
import yaml
import os
import re
from pydantic import BaseSettings, Field, validator
from functools import lru_cache


class BaseAppConfig(BaseSettings):
    """Base configuration with common settings across all services"""
    
    # Application
    service_name: str = Field(..., env="SERVICE_NAME")
    service_version: str = Field(default="1.0.0", env="SERVICE_VERSION") 
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    server_timeout: int = Field(default=30, env="SERVER_TIMEOUT")
    
    # Database  
    database_url: str = Field(..., env="DATABASE_URL")
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    db_timeout: int = Field(default=30, env="DB_TIMEOUT")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    redis_timeout: int = Field(default=5, env="REDIS_TIMEOUT")
    session_ttl: int = Field(default=3600, env="SESSION_TTL")
    
    # Pagination
    pagination_default: int = Field(default=20, env="PAGINATION_DEFAULT")
    pagination_max: int = Field(default=100, env="PAGINATION_MAX")
    
    # Batch Processing
    batch_size: int = Field(default=5, env="BATCH_SIZE") 
    batch_max_size: int = Field(default=50, env="BATCH_MAX_SIZE")
    
    # HTTP Client
    http_timeout: float = Field(default=5.0, env="HTTP_TIMEOUT")
    http_retry_attempts: int = Field(default=3, env="HTTP_RETRY_ATTEMPTS")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Security
    api_key_required: bool = Field(default=True, env="API_KEY_REQUIRED")
    jwt_secret: str = Field(default="changeme", env="JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", env="JWT_ALGORITHM")
    jwt_expiry: str = Field(default="24h", env="JWT_EXPIRY")
    
    @validator('environment')
    def validate_environment(cls, v):
        valid_envs = ['development', 'staging', 'production', 'test']
        if v not in valid_envs:
            raise ValueError(f'Environment must be one of: {valid_envs}')
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False


class ConfigManager:
    """Centralized configuration management with multi-tier loading"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path("config")
        self._config_cache: Dict[str, Any] = {}
    
    def load_config(self, service_name: str) -> Dict[str, Any]:
        """Load configuration with proper precedence: base -> env -> service -> env vars"""
        cache_key = f"{service_name}_{os.getenv('ENVIRONMENT', 'development')}"
        
        if cache_key in self._config_cache:
            return self._config_cache[cache_key]
            
        # 1. Load base configuration
        config = self._load_yaml(self.config_dir / "base.yaml") or {}
        
        # 2. Load environment-specific overrides
        env = os.getenv("ENVIRONMENT", "development")
        env_config = self._load_yaml(self.config_dir / "environments" / f"{env}.yaml")
        if env_config:
            config = self._deep_merge(config, env_config)
        
        # 3. Load service-specific configuration
        service_config = self._load_yaml(self.config_dir / "services" / f"{service_name}.yaml")
        if service_config:
            config = self._deep_merge(config, service_config)
        
        # 4. Apply environment variable interpolation
        config = self._interpolate_env_vars(config)
        
        self._config_cache[cache_key] = config
        return config
    
    def _load_yaml(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load YAML file safely with error handling"""
        try:
            if path.exists():
                with open(path, 'r') as f:
                    content = yaml.safe_load(f)
                    return content if content is not None else {}
        except yaml.YAMLError as e:
            print(f"Error parsing YAML file {path}: {e}")
        except Exception as e:
            print(f"Warning: Failed to load {path}: {e}")
        return None
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries with override taking precedence"""
        result = base.copy()
        
        for key, value in override.items():
            if (key in result and 
                isinstance(result[key], dict) and 
                isinstance(value, dict)):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _interpolate_env_vars(self, config: Any) -> Any:
        """Recursively interpolate environment variables in config values"""
        if isinstance(config, dict):
            return {key: self._interpolate_env_vars(value) for key, value in config.items()}
        elif isinstance(config, list):
            return [self._interpolate_env_vars(item) for item in config]
        elif isinstance(config, str):
            return self._interpolate_string(config)
        else:
            return config
    
    def _interpolate_string(self, value: str) -> Union[str, int, float, bool]:
        """Interpolate environment variables in a string value"""
        # Pattern: ${VAR_NAME:default_value} or ${VAR_NAME}
        pattern = r'\$\{([^}]+)\}'
        
        def replace_env_var(match):
            var_spec = match.group(1)
            if ':' in var_spec:
                var_name, default = var_spec.split(':', 1)
                env_value = os.getenv(var_name.strip(), default.strip())
            else:
                env_value = os.getenv(var_spec.strip(), '')
            
            return env_value
        
        result = re.sub(pattern, replace_env_var, value)
        
        # Try to convert to appropriate type
        return self._convert_type(result)
    
    def _convert_type(self, value: str) -> Union[str, int, float, bool]:
        """Convert string value to appropriate Python type"""
        if value.lower() in ('true', 'false'):
            return value.lower() == 'true'
        
        try:
            # Try integer first
            if '.' not in value:
                return int(value)
            # Then float
            return float(value)
        except ValueError:
            # Return as string if conversion fails
            return value
    
    def clear_cache(self):
        """Clear configuration cache - useful for testing"""
        self._config_cache.clear()


@lru_cache()
def get_config_manager() -> ConfigManager:
    """Get cached configuration manager instance"""
    return ConfigManager()


def create_service_config_class(service_name: str, additional_fields: Dict[str, Any] = None):
    """Factory function to create service-specific configuration classes"""
    
    class ServiceConfig(BaseAppConfig):
        """Dynamic service configuration class"""
        pass
    
    # Add additional fields if provided
    if additional_fields:
        for field_name, field_definition in additional_fields.items():
            setattr(ServiceConfig, field_name, field_definition)
    
    # Add class method to load configuration
    @classmethod
    def load_config(cls):
        """Load configuration with file-based overrides"""
        config_manager = get_config_manager()
        file_config = config_manager.load_config(service_name)
        
        # Flatten nested config for Pydantic
        flat_config = cls._flatten_config(file_config)
        
        # Create instance with file config as defaults
        return cls(**flat_config)
    
    @classmethod 
    def _flatten_config(cls, config: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
        """Flatten nested config dictionary for Pydantic consumption"""
        flattened = {}
        
        for key, value in config.items():
            new_key = f"{prefix}_{key}" if prefix else key
            
            if isinstance(value, dict):
                # Recursively flatten nested dictionaries
                flattened.update(cls._flatten_config(value, new_key))
            else:
                flattened[new_key] = value
                
        return flattened
    
    ServiceConfig.load_config = load_config
    ServiceConfig._flatten_config = _flatten_config
    ServiceConfig.__name__ = f"{service_name.title().replace('-', '')}Config"
    
    return ServiceConfig