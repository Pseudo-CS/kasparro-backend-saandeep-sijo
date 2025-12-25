"""Tests for ETL utilities."""
import pytest
from datetime import datetime

from services.etl_utils import (
    generate_source_id,
    generate_run_id,
    safe_parse_datetime,
    safe_float,
    RateLimiter
)


def test_generate_source_id_with_id():
    """Test source ID generation with natural ID."""
    data = {"id": "123", "name": "test"}
    source_id = generate_source_id("csv", data)
    assert source_id == "csv_123"


def test_generate_source_id_with_link():
    """Test source ID generation with link."""
    data = {"link": "https://example.com/item", "title": "test"}
    source_id = generate_source_id("rss", data)
    assert source_id.startswith("rss_")
    assert len(source_id) > 4


def test_generate_source_id_from_content():
    """Test source ID generation from content hash."""
    data = {"title": "test", "value": 123}
    source_id = generate_source_id("api", data)
    assert source_id.startswith("api_")


def test_generate_run_id():
    """Test run ID generation."""
    run_id1 = generate_run_id()
    run_id2 = generate_run_id()
    
    assert run_id1.startswith("run_")
    assert run_id2.startswith("run_")
    assert run_id1 != run_id2


def test_safe_parse_datetime_valid():
    """Test datetime parsing with valid input."""
    result = safe_parse_datetime("2024-01-15T10:30:00Z")
    assert isinstance(result, datetime)
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15


def test_safe_parse_datetime_invalid():
    """Test datetime parsing with invalid input."""
    result = safe_parse_datetime("invalid-date")
    assert result is None


def test_safe_parse_datetime_none():
    """Test datetime parsing with None."""
    result = safe_parse_datetime(None)
    assert result is None


def test_safe_float_valid():
    """Test float conversion with valid input."""
    assert safe_float("123.45") == 123.45
    assert safe_float(123) == 123.0
    assert safe_float(123.45) == 123.45


def test_safe_float_invalid():
    """Test float conversion with invalid input."""
    assert safe_float("invalid") is None
    assert safe_float("") is None
    assert safe_float(None) is None


def test_rate_limiter():
    """Test rate limiter functionality."""
    import time
    
    limiter = RateLimiter(calls_per_period=2, period_seconds=1)
    
    # First two calls should be immediate
    start = time.time()
    limiter.wait_if_needed()
    limiter.wait_if_needed()
    duration1 = time.time() - start
    
    assert duration1 < 0.5  # Should be fast
    
    # Third call should wait
    start = time.time()
    limiter.wait_if_needed()
    duration2 = time.time() - start
    
    assert duration2 >= 0.5  # Should wait at least half the period
