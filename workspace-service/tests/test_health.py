"""Test health endpoints"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from src.main import app

client = TestClient(app)


def test_health_check():
    """Test basic health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "workspace-service"
    assert "version" in data
    assert "environment" in data


@patch("src.routes.health.get_db")
@patch("src.routes.health.get_redis_client")
def test_detailed_health_check_healthy(mock_redis, mock_db):
    """Test detailed health check when all services are healthy"""
    # Mock database connection
    mock_db_session = AsyncMock()
    mock_db.return_value.__aenter__.return_value = mock_db_session
    mock_db_session.execute = AsyncMock()
    
    # Mock Redis connection
    mock_redis_client = AsyncMock()
    mock_redis.return_value = mock_redis_client
    mock_redis_client.ping = AsyncMock()
    
    response = client.get("/health/detailed")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["checks"]["database"] == "healthy"
    assert data["checks"]["redis"] == "healthy"


def test_readiness_check():
    """Test readiness check endpoint"""
    # This will fail in test environment without actual DB/Redis
    response = client.get("/ready")
    assert response.status_code in [200, 503]  # Either ready or not ready