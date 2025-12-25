"""Enhanced rate limiting with retry logic and exponential backoff."""
import time
import logging
from typing import Optional, Callable, Any, TypeVar
from functools import wraps
import asyncio

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff: float = 1.0,
        max_backoff: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
            initial_backoff: Initial backoff time in seconds
            max_backoff: Maximum backoff time in seconds
            backoff_multiplier: Multiplier for exponential backoff
            jitter: Whether to add random jitter to backoff
        """
        self.max_retries = max_retries
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter
    
    def calculate_backoff(self, attempt: int) -> float:
        """Calculate backoff time for a given attempt."""
        backoff = min(
            self.initial_backoff * (self.backoff_multiplier ** attempt),
            self.max_backoff
        )
        
        if self.jitter:
            import random
            # Add ±25% jitter
            jitter_factor = 1.0 + (random.random() - 0.5) * 0.5
            backoff *= jitter_factor
        
        return backoff


def with_retry(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Decorator to add retry logic with exponential backoff to a function.
    
    Args:
        config: Retry configuration (uses defaults if None)
        retryable_exceptions: Tuple of exception types that should trigger retry
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_retries:
                        backoff = config.calculate_backoff(attempt)
                        logger.warning(
                            f"⚠️  Attempt {attempt + 1}/{config.max_retries + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {backoff:.2f}s..."
                        )
                        time.sleep(backoff)
                    else:
                        logger.error(
                            f"❌ All {config.max_retries + 1} attempts failed for {func.__name__}: {e}"
                        )
            
            # All retries exhausted
            raise last_exception
        
        return wrapper
    return decorator


def with_async_retry(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: tuple = (Exception,)
):
    """
    Async version of retry decorator.
    
    Args:
        config: Retry configuration (uses defaults if None)
        retryable_exceptions: Tuple of exception types that should trigger retry
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(config.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < config.max_retries:
                        backoff = config.calculate_backoff(attempt)
                        logger.warning(
                            f"⚠️  Attempt {attempt + 1}/{config.max_retries + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {backoff:.2f}s..."
                        )
                        await asyncio.sleep(backoff)
                    else:
                        logger.error(
                            f"❌ All {config.max_retries + 1} attempts failed for {func.__name__}: {e}"
                        )
            
            # All retries exhausted
            raise last_exception
        
        return wrapper
    return decorator


class PerSourceRateLimiter:
    """Rate limiter with per-source tracking."""
    
    def __init__(self):
        self.limiters = {}  # source_name -> RateLimiter
        self.configs = {}  # source_name -> (calls, period)
    
    def configure_source(self, source_name: str, calls_per_period: int, period_seconds: int):
        """Configure rate limit for a specific source."""
        from services.etl_utils import RateLimiter
        
        self.configs[source_name] = (calls_per_period, period_seconds)
        self.limiters[source_name] = RateLimiter(calls_per_period, period_seconds)
        
        logger.info(
            f"📊 Configured rate limit for {source_name}: "
            f"{calls_per_period} calls per {period_seconds}s"
        )
    
    def wait_if_needed(self, source_name: str):
        """Wait if rate limit is exceeded for a source."""
        if source_name not in self.limiters:
            # Use default if not configured
            logger.warning(f"No rate limit configured for {source_name}, using default")
            from services.etl_utils import RateLimiter
            self.limiters[source_name] = RateLimiter(100, 60)
        
        self.limiters[source_name].wait_if_needed()
    
    def get_stats(self) -> dict:
        """Get rate limiting statistics."""
        stats = {}
        for source_name, limiter in self.limiters.items():
            config = self.configs.get(source_name, (0, 0))
            stats[source_name] = {
                "calls_per_period": config[0],
                "period_seconds": config[1],
                "current_calls": len(limiter.calls)
            }
        return stats


# Global per-source rate limiter instance
global_rate_limiter = PerSourceRateLimiter()
