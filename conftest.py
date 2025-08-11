"""
Global pytest configuration for Python microservices.
Provides shared fixtures, test environment setup, and common utilities.
"""

import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Dict, Any
from unittest.mock import AsyncMock, MagicMock
import httpx
import asyncpg
import redis.asyncio as redis
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from testcontainers.compose import DockerCompose
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test environment configuration
TEST_ENV = os.getenv("TEST_ENV", "unit")
CI = os.getenv("CI", "false").lower() == "true"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture(scope="session")
def postgres_container():
    """Provide PostgreSQL container for integration tests."""
    if TEST_ENV == "unit":
        yield None
        return
    
    with PostgresContainer(
        "postgres:16-alpine",
        username="test",
        password="test",
        dbname="test_db"
    ) as postgres:
        # Wait for container to be ready
        postgres.get_connection_url()
        yield postgres

@pytest.fixture(scope="session")
def redis_container():
    """Provide Redis container for integration tests."""
    if TEST_ENV == "unit":
        yield None
        return
    
    with RedisContainer("redis:7-alpine") as redis_c:
        yield redis_c

@pytest.fixture(scope="session")
async def test_database_url(postgres_container):
    """Provide database URL for tests."""
    if postgres_container is None:
        return "sqlite:///:memory:"
    
    return postgres_container.get_connection_url().replace("postgresql://", "postgresql+asyncpg://")

@pytest.fixture(scope="session")
def test_redis_url(redis_container):
    """Provide Redis URL for tests."""
    if redis_container is None:
        return None
    
    return redis_container.get_connection_url()

@pytest.fixture
async def db_connection(test_database_url: str) -> AsyncGenerator[asyncpg.Connection, None]:
    """Provide a database connection for tests."""
    if "sqlite" in test_database_url:
        yield None
        return
    
    # Extract connection params from URL
    import urllib.parse
    parsed = urllib.parse.urlparse(test_database_url)
    
    conn = await asyncpg.connect(
        host=parsed.hostname,
        port=parsed.port,
        user=parsed.username,
        password=parsed.password,
        database=parsed.path.lstrip('/')
    )
    
    try:
        yield conn
    finally:
        await conn.close()

@pytest.fixture
async def redis_client(test_redis_url: str) -> AsyncGenerator[redis.Redis, None]:
    """Provide a Redis client for tests."""
    if test_redis_url is None:
        yield None
        return
    
    client = redis.Redis.from_url(test_redis_url)
    
    try:
        await client.ping()
        yield client
    finally:
        await client.aclose()

@pytest.fixture
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Provide an HTTP client for API testing."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client

@pytest.fixture
def mock_airtable_api():
    """Provide mock for Airtable API."""
    mock = AsyncMock()
    
    # Default responses
    mock.get_base.return_value = {
        "id": "appTest123",
        "name": "Test Base",
        "permissionLevel": "create"
    }
    
    mock.list_tables.return_value = {
        "tables": [
            {
                "id": "tblTest123",
                "name": "Test Table",
                "primaryFieldId": "fldTest123",
                "fields": [
                    {
                        "id": "fldTest123",
                        "name": "Name",
                        "type": "singleLineText"
                    }
                ]
            }
        ]
    }
    
    mock.list_records.return_value = {
        "records": [
            {
                "id": "recTest123",
                "fields": {
                    "Name": "Test Record"
                },
                "createdTime": "2024-01-01T00:00:00.000Z"
            }
        ]
    }
    
    return mock

@pytest.fixture
def mock_llm_client():
    """Provide mock for LLM clients (OpenAI, Anthropic, etc.)."""
    mock = AsyncMock()
    
    # Default chat completion response
    mock.chat.completions.create.return_value = MagicMock(
        choices=[
            MagicMock(
                message=MagicMock(
                    content="Mock AI response",
                    role="assistant"
                ),
                finish_reason="stop"
            )
        ],
        usage=MagicMock(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15
        )
    )
    
    return mock

@pytest.fixture
def mock_auth_service():
    """Provide mock for authentication service."""
    mock = AsyncMock()
    
    # Default user data
    test_user = {
        "id": "test-user-id",
        "email": "test@example.com",
        "name": "Test User",
        "role": "user",
        "tenant_id": "test-tenant-id"
    }
    
    mock.verify_token.return_value = test_user
    mock.get_user.return_value = test_user
    mock.create_user.return_value = test_user
    
    return mock

@pytest.fixture(autouse=True)
async def cleanup_database(db_connection):
    """Clean database before and after each test."""
    if db_connection is None:
        yield
        return
    
    # Get all table names
    tables_query = """
        SELECT tablename FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename NOT LIKE 'alembic_%'
    """
    
    try:
        # Clean before test
        await db_connection.execute("BEGIN")
        tables = await db_connection.fetch(tables_query)
        for table in tables:
            await db_connection.execute(f"TRUNCATE TABLE {table['tablename']} CASCADE")
        await db_connection.execute("COMMIT")
        
        yield
        
        # Clean after test
        await db_connection.execute("BEGIN")
        tables = await db_connection.fetch(tables_query)
        for table in tables:
            await db_connection.execute(f"TRUNCATE TABLE {table['tablename']} CASCADE")
        await db_connection.execute("COMMIT")
        
    except Exception as e:
        logger.warning(f"Database cleanup failed: {e}")
        await db_connection.execute("ROLLBACK")
        yield

@pytest.fixture(autouse=True)
async def cleanup_redis(redis_client):
    """Clean Redis before and after each test."""
    if redis_client is None:
        yield
        return
    
    try:
        # Clean before test
        await redis_client.flushdb()
        yield
        # Clean after test
        await redis_client.flushdb()
    except Exception as e:
        logger.warning(f"Redis cleanup failed: {e}")
        yield

@pytest.fixture
def test_settings():
    """Provide test-specific settings."""
    return {
        "DATABASE_URL": "sqlite:///:memory:",
        "REDIS_URL": "redis://localhost:6379/1",
        "SECRET_KEY": "test-secret-key",
        "JWT_SECRET": "test-jwt-secret",
        "ENVIRONMENT": "test",
        "LOG_LEVEL": "DEBUG",
        "RATE_LIMIT_ENABLED": False,
        "CACHE_TTL": 60,
        "API_TIMEOUT": 30,
    }

@pytest.fixture
def test_headers():
    """Provide common test headers."""
    return {
        "Authorization": "Bearer test-token",
        "Content-Type": "application/json",
        "User-Agent": "PyAirtable-Test/1.0",
        "X-Tenant-ID": "test-tenant-id",
    }

@pytest.fixture
def sample_user_data():
    """Provide sample user data for tests."""
    return {
        "id": "test-user-id",
        "email": "test@example.com",
        "name": "Test User",
        "role": "user",
        "tenant_id": "test-tenant-id",
        "is_active": True,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }

@pytest.fixture
def sample_workspace_data():
    """Provide sample workspace data for tests."""
    return {
        "id": "test-workspace-id",
        "name": "Test Workspace",
        "description": "A test workspace",
        "tenant_id": "test-tenant-id",
        "owner_id": "test-user-id",
        "is_active": True,
        "settings": {
            "auto_sync": True,
            "sync_interval": 300
        },
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    }

# Pytest markers for different test types
def pytest_configure(config):
    """Configure pytest with custom markers."""
    markers = [
        "unit: Unit tests",
        "integration: Integration tests", 
        "e2e: End-to-end tests",
        "slow: Slow tests (> 1s)",
        "external: Tests requiring external services",
        "database: Tests requiring database",
        "redis: Tests requiring Redis",
        "rabbitmq: Tests requiring RabbitMQ",
        "auth: Authentication tests",
        "api: API tests",
        "performance: Performance tests",
        "security: Security tests",
        "smoke: Smoke tests",
    ]
    
    for marker in markers:
        config.addinivalue_line("markers", marker)

def pytest_collection_modifyitems(config, items):
    """Modify test collection to add automatic markers."""
    for item in items:
        # Add markers based on test location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        
        # Add slow marker for tests that take > 1 second
        if hasattr(item, "function"):
            if getattr(item.function, "_slow", False):
                item.add_marker(pytest.mark.slow)

# Helper functions
def mark_slow(func):
    """Decorator to mark tests as slow."""
    func._slow = True
    return func

# Skip conditions
skip_if_no_docker = pytest.mark.skipif(
    not os.path.exists("/var/run/docker.sock"),
    reason="Docker not available"
)

skip_if_unit_test = pytest.mark.skipif(
    TEST_ENV == "unit",
    reason="Integration test environment not available"
)

skip_if_ci = pytest.mark.skipif(
    CI,
    reason="Skipped in CI environment"
)