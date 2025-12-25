"""Utilities for ETL services."""
import hashlib
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.
    
    Returns:
        Current UTC datetime with timezone info
    """
    return datetime.now(timezone.utc)


def ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime is timezone-aware (assumes UTC if naive).
    Useful for handling SQLite datetime fields which lose timezone info.
    
    Args:
        dt: Datetime that may be naive or aware
        
    Returns:
        Timezone-aware datetime in UTC or None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def generate_source_id(source_type: str, data: Dict[str, Any]) -> str:
    """
    Generate a unique source ID for deduplication.
    
    Args:
        source_type: Type of data source
        data: Raw data dictionary
        
    Returns:
        Unique source ID
    """
    # Try to use natural IDs from the data
    if 'id' in data:
        return f"{source_type}_{data['id']}"
    elif 'guid' in data:
        return f"{source_type}_{data['guid']}"
    elif 'link' in data:
        # Hash the link for RSS feeds
        link_hash = hashlib.md5(data['link'].encode()).hexdigest()[:16]
        return f"{source_type}_{link_hash}"
    else:
        # Generate hash from data content
        data_str = str(sorted(data.items()))
        content_hash = hashlib.md5(data_str.encode()).hexdigest()[:16]
        return f"{source_type}_{content_hash}"


def generate_run_id() -> str:
    """Generate a unique run ID."""
    return f"run_{utc_now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


class RateLimiter:
    """Simple rate limiter for API calls."""
    
    def __init__(self, calls_per_period: int, period_seconds: int):
        self.calls_per_period = calls_per_period
        self.period_seconds = period_seconds
        self.calls = []
    
    def wait_if_needed(self):
        """Wait if rate limit is exceeded."""
        import time
        
        now = time.time()
        # Remove old calls outside the window
        self.calls = [call_time for call_time in self.calls 
                      if now - call_time < self.period_seconds]
        
        if len(self.calls) >= self.calls_per_period:
            # Wait until the oldest call expires
            sleep_time = self.period_seconds - (now - self.calls[0]) + 0.1
            logger.info(f"Rate limit reached, sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
            self.calls = self.calls[1:]
        
        self.calls.append(now)


def safe_parse_datetime(value: Any) -> Optional[datetime]:
    """
    Safely parse various datetime formats.
    Returns timezone-aware datetime in UTC.
    
    Args:
        value: Value to parse
        
    Returns:
        Parsed datetime (timezone-aware UTC) or None
    """
    if value is None:
        return None
    
    if isinstance(value, datetime):
        # If naive, assume UTC
        if value.tzinfo is None:
            from datetime import timezone
            return value.replace(tzinfo=timezone.utc)
        return value
    
    if isinstance(value, str):
        from dateutil import parser
        from datetime import timezone
        try:
            dt = parser.parse(value)
            # If parsed datetime is naive, assume UTC
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception as e:
            logger.warning(f"Failed to parse datetime '{value}': {e}")
            return None
    
    return None


def safe_float(value: Any) -> Optional[float]:
    """
    Safely convert value to float.
    
    Args:
        value: Value to convert
        
    Returns:
        Float value or None
    """
    if value is None or value == '':
        return None
    
    try:
        return float(value)
    except (ValueError, TypeError) as e:
        logger.warning(f"Failed to convert to float: {value} - {e}")
        return None
