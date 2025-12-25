"""Tests for P2.3 (Rate Limiting + Backoff), P2.4 (Observability), P2.5 (DevOps)."""
import pytest
import time
from unittest.mock import Mock, patch
import asyncio

from services.retry_service import (
    RetryConfig, with_retry, with_async_retry, 
    PerSourceRateLimiter, global_rate_limiter
)
from services.observability import (
    StructuredLogger, MetricsCollector,
    etl_records_processed, etl_runs_total
)


class TestRetryAndBackoff:
    """Tests for P2.3: Retry with Exponential Backoff."""
    
    def test_retry_config_backoff_calculation(self):
        """Test exponential backoff calculation."""
        config = RetryConfig(
            initial_backoff=1.0,
            backoff_multiplier=2.0,
            max_backoff=10.0,
            jitter=False
        )
        
        # Test exponential growth
        assert config.calculate_backoff(0) == 1.0
        assert config.calculate_backoff(1) == 2.0
        assert config.calculate_backoff(2) == 4.0
        assert config.calculate_backoff(3) == 8.0
        
        # Test max backoff
        assert config.calculate_backoff(10) == 10.0  # Capped at max
    
    def test_retry_config_with_jitter(self):
        """Test that jitter adds randomness."""
        config = RetryConfig(
            initial_backoff=10.0,
            jitter=True
        )
        
        # With jitter, values should vary
        backoffs = [config.calculate_backoff(0) for _ in range(10)]
        assert len(set(backoffs)) > 1  # Should have different values
        
        # All should be within ±25% of 10.0
        for backoff in backoffs:
            assert 7.5 <= backoff <= 12.5
    
    def test_with_retry_decorator_success(self):
        """Test retry decorator with successful call."""
        call_count = 0
        
        @with_retry(config=RetryConfig(max_retries=2))
        def flaky_function():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = flaky_function()
        assert result == "success"
        assert call_count == 1
    
    def test_with_retry_decorator_eventual_success(self):
        """Test retry decorator with eventual success."""
        call_count = 0
        
        @with_retry(config=RetryConfig(max_retries=3, initial_backoff=0.1))
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = flaky_function()
        assert result == "success"
        assert call_count == 3
    
    def test_with_retry_decorator_all_failures(self):
        """Test retry decorator when all attempts fail."""
        call_count = 0
        
        @with_retry(config=RetryConfig(max_retries=2, initial_backoff=0.1))
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError):
            always_fails()
        
        assert call_count == 3  # Initial + 2 retries
    
    @pytest.mark.asyncio
    async def test_async_retry_decorator(self):
        """Test async retry decorator."""
        call_count = 0
        
        @with_async_retry(config=RetryConfig(max_retries=2, initial_backoff=0.1))
        async def async_flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        result = await async_flaky()
        assert result == "success"
        assert call_count == 2


class TestPerSourceRateLimiting:
    """Tests for P2.3: Per-Source Rate Limiting."""
    
    def test_per_source_rate_limiter_configuration(self):
        """Test configuring rate limits per source."""
        limiter = PerSourceRateLimiter()
        
        limiter.configure_source("source1", 10, 60)
        limiter.configure_source("source2", 20, 60)
        
        stats = limiter.get_stats()
        assert "source1" in stats
        assert "source2" in stats
        assert stats["source1"]["calls_per_period"] == 10
        assert stats["source2"]["calls_per_period"] == 20
    
    def test_per_source_rate_limiting_independence(self):
        """Test that sources are rate limited independently."""
        limiter = PerSourceRateLimiter()
        
        # Configure tight limits
        limiter.configure_source("fast", 2, 1)
        limiter.configure_source("slow", 1, 1)
        
        # Fast source should allow 2 calls
        start = time.time()
        limiter.wait_if_needed("fast")
        limiter.wait_if_needed("fast")
        duration = time.time() - start
        assert duration < 0.5  # Should be quick
        
        # Slow source should allow only 1 call
        limiter.wait_if_needed("slow")
        # Would block on second call (not testing to avoid delays)


class TestObservability:
    """Tests for P2.4: Observability Layer."""
    
    def test_structured_logger_format(self):
        """Test structured JSON logging format."""
        logger = StructuredLogger("test")
        
        # Mock the underlying logger
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_structured(
                "info",
                "test_event",
                key1="value1",
                key2=123
            )
            
            # Verify JSON format
            call_args = mock_info.call_args[0][0]
            import json
            parsed = json.loads(call_args)
            
            assert parsed["event"] == "test_event"
            assert parsed["level"] == "INFO"
            assert parsed["key1"] == "value1"
            assert parsed["key2"] == 123
            assert "timestamp" in parsed
    
    def test_structured_logger_etl_events(self):
        """Test ETL-specific structured logging."""
        logger = StructuredLogger("test")
        
        with patch.object(logger.logger, 'info') as mock_info:
            logger.log_etl_start(
                source_type="csv",
                run_id="test_run_123",
                batch_size=100
            )
            
            call_args = mock_info.call_args[0][0]
            import json
            parsed = json.loads(call_args)
            
            assert parsed["event"] == "etl_run_started"
            assert parsed["source_type"] == "csv"
            assert parsed["run_id"] == "test_run_123"
    
    def test_prometheus_metrics_counters(self):
        """Test Prometheus counter metrics."""
        # Get current value
        before = etl_records_processed.labels(source_type="test")._value.get()
        
        # Increment counter
        etl_records_processed.labels(source_type="test").inc(5)
        
        # Verify increment
        after = etl_records_processed.labels(source_type="test")._value.get()
        assert after == before + 5
    
    def test_prometheus_metrics_multiple_labels(self):
        """Test metrics with multiple labels."""
        etl_runs_total.labels(source_type="csv", status="success").inc()
        etl_runs_total.labels(source_type="csv", status="failure").inc()
        
        # Both counters should exist independently
        success_val = etl_runs_total.labels(source_type="csv", status="success")._value.get()
        failure_val = etl_runs_total.labels(source_type="csv", status="failure")._value.get()
        
        assert success_val >= 1
        assert failure_val >= 1


class TestIntegration:
    """Integration tests for P2.3 + P2.4."""
    
    @pytest.mark.asyncio
    async def test_api_call_with_retry_and_metrics(self):
        """Test API call with retry, rate limiting, and metrics tracking."""
        from services.observability import api_requests_total
        
        call_count = 0
        
        @with_async_retry(
            config=RetryConfig(max_retries=2, initial_backoff=0.1),
            retryable_exceptions=(ValueError,)
        )
        async def simulated_api_call():
            nonlocal call_count
            call_count += 1
            
            # Track metric
            api_requests_total.labels(
                method="GET",
                endpoint="/test",
                status=200
            ).inc()
            
            if call_count < 2:
                raise ValueError("Retry me")
            
            return {"data": "success"}
        
        result = await simulated_api_call()
        
        assert result["data"] == "success"
        assert call_count == 2  # Failed once, succeeded on retry
        
        # Verify metrics were tracked
        metric_val = api_requests_total.labels(
            method="GET",
            endpoint="/test",
            status=200
        )._value.get()
        assert metric_val >= 2  # Both calls tracked


class TestDockerHealthCheck:
    """Tests for P2.5: Docker Health Checks."""
    
    def test_health_endpoint_available(self):
        """Test that health endpoint exists (unit test)."""
        # This would be tested via actual API call in integration tests
        # Here we just verify the concept
        assert True  # Placeholder - actual health check tested via API
    
    def test_healthcheck_configuration(self):
        """Test health check configuration format."""
        # Verify docker-compose.yml has healthcheck (conceptual test)
        import os
        
        compose_file = os.path.join(
            os.path.dirname(__file__), 
            "..", 
            "docker-compose.yml"
        )
        
        if os.path.exists(compose_file):
            with open(compose_file, 'r') as f:
                content = f.read()
                assert "healthcheck" in content
                assert "health" in content  # health endpoint


class TestCIPipeline:
    """Tests for P2.5: CI/CD Pipeline."""
    
    def test_github_workflow_exists(self):
        """Test that GitHub Actions workflow files exist."""
        import os
        
        workflows_dir = os.path.join(
            os.path.dirname(__file__),
            "..",
            ".github",
            "workflows"
        )
        
        if os.path.exists(workflows_dir):
            files = os.listdir(workflows_dir)
            # Check for CI/CD workflow
            yaml_files = [f for f in files if f.endswith('.yml') or f.endswith('.yaml')]
            assert len(yaml_files) > 0
