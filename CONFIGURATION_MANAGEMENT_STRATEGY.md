# Configuration Management Strategy - SPIKE-802

## Current State Analysis

### Identified Hardcoded Values
- **Pagination limits**: Default 20, max 100 in workspace service
- **Batch sizes**: Default 5 in LLM orchestrator  
- **Timeout values**: 5.0 seconds for HTTP clients
- **Rate limits**: max_workspaces_per_user: 50, max_members_per_workspace: 100
- **Session TTL**: 3600 seconds (1 hour)
- **Token expiration**: 7 days for invitations
- **Field limits**: min_description_length: 20

### Current Configuration Patterns
- **Python Services**: Using Pydantic BaseSettings with .env support
- **Environment Variables**: Mixed approach with some hardcoded defaults
- **Service Discovery**: Hardcoded service URLs in some places

## Proposed Configuration Architecture

### 1. Three-Tier Configuration System

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Environment    │    │   Service        │    │   Runtime       │
│  Variables      │────│   Config Files   │────│   Overrides     │
│  (.env files)   │    │   (YAML/JSON)    │    │   (API/DB)      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### 2. Configuration Schema Design

#### Base Configuration Schema
```yaml
# config/base.yaml
application:
  name: "${SERVICE_NAME}"
  version: "1.0.0"
  environment: "${ENVIRONMENT:development}"

server:
  host: "${HOST:0.0.0.0}"
  port: "${PORT:8000}"
  timeout: "${SERVER_TIMEOUT:30}"

database:
  url: "${DATABASE_URL}"
  pool_size: "${DB_POOL_SIZE:10}"
  timeout: "${DB_TIMEOUT:30}"

redis:
  url: "${REDIS_URL}"
  timeout: "${REDIS_TIMEOUT:5}"

pagination:
  default_limit: "${PAGINATION_DEFAULT:20}"
  max_limit: "${PAGINATION_MAX:100}"
  
batch_processing:
  default_size: "${BATCH_SIZE:5}"
  max_size: "${BATCH_MAX_SIZE:50}"

security:
  api_key_required: "${API_KEY_REQUIRED:true}"
  jwt_expiry: "${JWT_EXPIRY:24h}"
  session_ttl: "${SESSION_TTL:3600}"

features:
  workspace_limit_per_user: "${MAX_WORKSPACES:50}"
  members_limit_per_workspace: "${MAX_MEMBERS:100}"
```

## File Structure Recommendations

```
project-root/
├── config/
│   ├── base.yaml                    # Base configuration
│   ├── environments/
│   │   ├── development.yaml        # Dev overrides
│   │   ├── staging.yaml            # Staging overrides
│   │   └── production.yaml         # Production overrides
│   └── services/
│       ├── workspace-service.yaml  # Service-specific config
│       ├── llm-orchestrator.yaml
│       └── airtable-gateway.yaml
├── shared/
│   └── config/
│       ├── __init__.py
│       ├── config_manager.py       # Configuration loader
│       ├── schemas.py              # Pydantic models
│       └── validation.py           # Config validation
└── .env.example                    # Template for local setup
```

## Environment Variable vs Config File Decision Matrix

| Use Case | Environment Variables | Config Files | 
|----------|---------------------|--------------|
| Secrets (API keys, passwords) | ✅ Yes | ❌ No |
| Service URLs | ✅ Yes | ✅ Yes (with env interpolation) |
| Feature flags | ✅ Yes | ✅ Yes |
| Business logic constants | ❌ No | ✅ Yes |
| Development overrides | ✅ Yes (.env.local) | ✅ Yes |
| Static application config | ❌ No | ✅ Yes |

## Migration Plan with Priorities

### Phase 1 (High Priority) - Foundation
1. Create shared configuration management library
2. Replace hardcoded pagination limits in workspace service
3. Centralize service URLs and timeouts
4. Implement config validation

### Phase 2 (Medium Priority) - Service Migration  
1. Migrate workspace-service to new config system
2. Update llm-orchestrator configuration
3. Standardize batch processing configurations
4. Implement environment-specific overrides

### Phase 3 (Low Priority) - Advanced Features
1. Add runtime configuration updates via API
2. Implement configuration change auditing
3. Add configuration hot-reloading
4. Create configuration management dashboard

## Example Implementation

### Shared Configuration Manager
```python
# shared/config/config_manager.py
from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import os
from pydantic import BaseSettings, Field
from functools import lru_cache

class BaseAppConfig(BaseSettings):
    """Base configuration with common settings"""
    
    # Application
    service_name: str = Field(..., env="SERVICE_NAME")
    service_version: str = "1.0.0" 
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Server
    host: str = Field(default="0.0.0.0", env="HOST")
    port: int = Field(default=8000, env="PORT")
    server_timeout: int = Field(default=30, env="SERVER_TIMEOUT")
    
    # Database  
    database_url: str = Field(..., env="DATABASE_URL")
    db_pool_size: int = Field(default=10, env="DB_POOL_SIZE")
    db_timeout: int = Field(default=30, env="DB_TIMEOUT")
    
    # Pagination
    pagination_default: int = Field(default=20, env="PAGINATION_DEFAULT")
    pagination_max: int = Field(default=100, env="PAGINATION_MAX")
    
    # Batch Processing
    batch_size: int = Field(default=5, env="BATCH_SIZE") 
    batch_max_size: int = Field(default=50, env="BATCH_MAX_SIZE")
    
    class Config:
        env_file = ".env"
        case_sensitive = False

class ConfigManager:
    """Centralized configuration management"""
    
    def __init__(self, config_dir: Path = Path("config")):
        self.config_dir = config_dir
        self._config_cache: Dict[str, Any] = {}
    
    def load_config(self, service_name: str) -> Dict[str, Any]:
        """Load configuration with proper precedence"""
        if service_name in self._config_cache:
            return self._config_cache[service_name]
            
        # 1. Load base config
        config = self._load_yaml(self.config_dir / "base.yaml")
        
        # 2. Load environment-specific overrides
        env = os.getenv("ENVIRONMENT", "development")
        env_config = self._load_yaml(
            self.config_dir / "environments" / f"{env}.yaml"
        )
        if env_config:
            config = self._deep_merge(config, env_config)
        
        # 3. Load service-specific config
        service_config = self._load_yaml(
            self.config_dir / "services" / f"{service_name}.yaml"
        )
        if service_config:
            config = self._deep_merge(config, service_config)
        
        # 4. Apply environment variable interpolation
        config = self._interpolate_env_vars(config)
        
        self._config_cache[service_name] = config
        return config
    
    def _load_yaml(self, path: Path) -> Optional[Dict[str, Any]]:
        """Load YAML file safely"""
        try:
            if path.exists():
                with open(path, 'r') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Failed to load {path}: {e}")
        return {}

@lru_cache()
def get_config_manager() -> ConfigManager:
    """Get cached configuration manager"""
    return ConfigManager()
```

### Service-Specific Configuration
```python
# workspace-service/src/config.py  
from shared.config.config_manager import BaseAppConfig, get_config_manager
from pydantic import Field

class WorkspaceConfig(BaseAppConfig):
    """Workspace service configuration"""
    
    # Workspace-specific settings
    max_workspaces_per_user: int = Field(default=50, env="MAX_WORKSPACES")
    max_members_per_workspace: int = Field(default=100, env="MAX_MEMBERS") 
    default_workspace_template: str = Field(default="blank", env="DEFAULT_TEMPLATE")
    invitation_expiry_days: int = Field(default=7, env="INVITATION_EXPIRY")
    
    @classmethod
    def load(cls) -> "WorkspaceConfig":
        """Load configuration with file-based overrides"""
        config_manager = get_config_manager()
        file_config = config_manager.load_config("workspace-service")
        
        # Create instance with file config as defaults
        return cls(**file_config)

@lru_cache()
def get_workspace_config() -> WorkspaceConfig:
    """Get cached workspace configuration"""
    return WorkspaceConfig.load()
```

## Benefits of This Approach

1. **Centralized Management**: Single source of truth for all configurations
2. **Environment Flexibility**: Easy switching between dev/staging/prod
3. **Type Safety**: Pydantic validation ensures configuration correctness  
4. **Security**: Clear separation of secrets vs non-sensitive config
5. **Maintainability**: Eliminates hardcoded values across services
6. **Scalability**: Supports complex multi-service configurations

## Implementation Timeline

- **Week 1**: Create shared configuration library and base schemas
- **Week 2**: Migrate workspace-service as proof of concept  
- **Week 3**: Update remaining Python services
- **Week 4**: Add environment-specific configurations and testing

Total estimated effort: ~20-25 development hours across 4 weeks.