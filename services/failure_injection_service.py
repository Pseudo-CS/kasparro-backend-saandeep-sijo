"""Failure injection service for testing ETL recovery mechanisms."""
import logging
import random
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FailureInjector:
    """Service for injecting controlled failures in ETL pipeline."""
    
    def __init__(
        self, 
        enabled: bool = False,
        failure_rate: float = 0.0,
        failure_after_n_records: Optional[int] = None,
        failure_type: str = "exception"
    ):
        """
        Initialize failure injector.
        
        Args:
            enabled: Whether failure injection is enabled
            failure_rate: Probability (0-1) of failure per record
            failure_after_n_records: Fail after processing N records
            failure_type: Type of failure - "exception", "timeout", "data_corruption"
        """
        self.enabled = enabled
        self.failure_rate = failure_rate
        self.failure_after_n_records = failure_after_n_records
        self.failure_type = failure_type
        self.records_processed = 0
        self.failure_triggered = False
        
        if enabled:
            logger.warning(
                f"⚠️  FAILURE INJECTION ENABLED: "
                f"rate={failure_rate}, after_n={failure_after_n_records}, type={failure_type}"
            )
    
    def should_fail(self) -> bool:
        """
        Determine if a failure should occur at this point.
        
        Returns:
            True if failure should be triggered
        """
        if not self.enabled or self.failure_triggered:
            return False
        
        self.records_processed += 1
        
        # Check if we should fail after N records
        if self.failure_after_n_records is not None:
            if self.records_processed >= self.failure_after_n_records:
                logger.error(
                    f"🔴 INJECTED FAILURE: Triggered after {self.records_processed} records"
                )
                self.failure_triggered = True
                return True
        
        # Check probabilistic failure
        if self.failure_rate > 0 and random.random() < self.failure_rate:
            logger.error(
                f"🔴 INJECTED FAILURE: Probabilistic trigger at record {self.records_processed}"
            )
            self.failure_triggered = True
            return True
        
        return False
    
    def trigger_failure(self):
        """Trigger the configured type of failure."""
        if not self.enabled:
            return
        
        logger.error(
            f"💥 TRIGGERING {self.failure_type.upper()} FAILURE "
            f"(processed: {self.records_processed} records)"
        )
        
        if self.failure_type == "exception":
            raise FailureInjectionException(
                f"Simulated failure after {self.records_processed} records"
            )
        elif self.failure_type == "timeout":
            raise TimeoutError(
                f"Simulated timeout after {self.records_processed} records"
            )
        elif self.failure_type == "data_corruption":
            raise ValueError(
                f"Simulated data corruption at record {self.records_processed}"
            )
        else:
            raise Exception(
                f"Simulated {self.failure_type} failure at record {self.records_processed}"
            )
    
    def check_and_fail(self):
        """Check if should fail and trigger failure if needed."""
        if self.should_fail():
            self.trigger_failure()
    
    def reset(self):
        """Reset the injector state."""
        self.records_processed = 0
        self.failure_triggered = False
        logger.info("Failure injector reset")
    
    @staticmethod
    def from_env() -> "FailureInjector":
        """Create failure injector from environment variables."""
        import os
        
        enabled = os.getenv("ETL_INJECT_FAILURE", "false").lower() == "true"
        failure_rate = float(os.getenv("ETL_FAILURE_RATE", "0.0"))
        failure_after = os.getenv("ETL_FAIL_AFTER_N")
        failure_type = os.getenv("ETL_FAILURE_TYPE", "exception")
        
        if failure_after:
            failure_after = int(failure_after)
        
        return FailureInjector(
            enabled=enabled,
            failure_rate=failure_rate,
            failure_after_n_records=failure_after,
            failure_type=failure_type
        )


class FailureInjectionException(Exception):
    """Custom exception for injected failures."""
    pass
