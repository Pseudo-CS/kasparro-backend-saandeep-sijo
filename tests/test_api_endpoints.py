"""Tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.models import NormalizedData
from core.database import get_db_session


client = TestClient(app)


def test_root_endpoint():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert "status" in data


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database_connected" in data
    assert "timestamp" in data


def test_data_endpoint_empty():
    """Test data endpoint with no data."""
    response = client.get("/data")
    assert response.status_code == 200
    data = response.json()
    
    assert "data" in data
    assert "metadata" in data
    assert isinstance(data["data"], list)
    
    metadata = data["metadata"]
    assert "request_id" in metadata
    assert "api_latency_ms" in metadata
    assert "pagination" in metadata


def test_data_endpoint_pagination():
    """Test data endpoint pagination."""
    response = client.get("/data?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    
    pagination = data["metadata"]["pagination"]
    assert pagination["page"] == 1
    assert pagination["page_size"] == 10
    assert "total_records" in pagination
    assert "total_pages" in pagination


def test_data_endpoint_filtering():
    """Test data endpoint with filters."""
    response = client.get("/data?source_type=csv&category=electronics")
    assert response.status_code == 200
    data = response.json()
    
    filters_applied = data["metadata"].get("filters_applied")
    if filters_applied:
        assert filters_applied.get("source_type") == "csv"
        assert filters_applied.get("category") == "electronics"


def test_data_endpoint_search():
    """Test data endpoint with search."""
    response = client.get("/data?search=test")
    assert response.status_code == 200
    data = response.json()
    
    assert "data" in data
    assert isinstance(data["data"], list)


def test_data_endpoint_invalid_page():
    """Test data endpoint with invalid page number."""
    response = client.get("/data?page=0")
    assert response.status_code == 422  # Validation error


def test_stats_endpoint():
    """Test stats endpoint."""
    response = client.get("/stats")
    assert response.status_code == 200
    data = response.json()
    
    assert "checkpoints" in data
    assert "recent_runs" in data
    assert "summary" in data
    
    summary = data["summary"]
    assert "total_records_normalized" in summary
    assert "total_records_processed" in summary
    assert "successful_sources" in summary
    assert "failed_sources" in summary


def test_stats_endpoint_with_limit():
    """Test stats endpoint with custom limit."""
    response = client.get("/stats?limit=5")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["recent_runs"]) <= 5


def test_api_latency_measurement():
    """Test that API latency is measured."""
    response = client.get("/data")
    assert response.status_code == 200
    data = response.json()
    
    latency_ms = data["metadata"]["api_latency_ms"]
    assert isinstance(latency_ms, (int, float))
    assert latency_ms >= 0


def test_request_id_generation():
    """Test that each request gets a unique request ID."""
    response1 = client.get("/data")
    response2 = client.get("/data")
    
    request_id1 = response1.json()["metadata"]["request_id"]
    request_id2 = response2.json()["metadata"]["request_id"]
    
    assert request_id1 != request_id2
