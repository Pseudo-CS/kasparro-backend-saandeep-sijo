"""Observability layer with metrics and structured logging."""
import time
import logging
import json
from datetime import datetime
from typing import Dict, Any, Optional
from collections import defaultdict
from fastapi import APIRouter
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, 
    CollectorRegistry, CONTENT_TYPE_LATEST
)
from fastapi.responses import Response
from sqlalchemy.orm import Session
from core.models import ETLRunHistory, ETLCheckpoint, NormalizedData, SchemaDriftLog
from services.etl_utils import utc_now
from core.database import get_db

logger = logging.getLogger(__name__)

# Prometheus metrics
registry = CollectorRegistry()

# ETL metrics
etl_records_processed = Counter(
    'etl_records_processed_total',
    'Total number of records processed',
    ['source_type'],
    registry=registry
)

etl_records_inserted = Counter(
    'etl_records_inserted_total',
    'Total number of records inserted',
    ['source_type'],
    registry=registry
)

etl_records_failed = Counter(
    'etl_records_failed_total',
    'Total number of records that failed',
    ['source_type'],
    registry=registry
)

etl_run_duration = Histogram(
    'etl_run_duration_seconds',
    'ETL run duration in seconds',
    ['source_type'],
    registry=registry
)

etl_runs_total = Counter(
    'etl_runs_total',
    'Total number of ETL runs',
    ['source_type', 'status'],
    registry=registry
)

schema_drift_detected = Counter(
    'schema_drift_detected_total',
    'Total number of schema drift detections',
    ['source_name'],
    registry=registry
)

# API metrics
api_requests_total = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

api_request_duration = Histogram(
    'api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint'],
    registry=registry
)

# Database metrics
db_records_total = Gauge(
    'db_records_total',
    'Total number of records in database',
    ['source_type'],
    registry=registry
)


class StructuredLogger:
    """Structured JSON logger for ETL operations."""
    
    def __init__(self, logger_name: str):
        self.logger = logging.getLogger(logger_name)
    
    def log_structured(
        self,
        level: str,
        event: str,
        **kwargs
    ):
        """Log a structured JSON message."""
        log_entry = {
            "timestamp": utc_now().isoformat(),
            "level": level.upper(),
            "event": event,
            **kwargs
        }
        
        log_message = json.dumps(log_entry)
        
        if level.upper() == "ERROR":
            self.logger.error(log_message)
        elif level.upper() == "WARNING":
            self.logger.warning(log_message)
        elif level.upper() == "INFO":
            self.logger.info(log_message)
        else:
            self.logger.debug(log_message)
    
    def log_etl_start(self, source_type: str, run_id: str, **metadata):
        """Log ETL run start."""
        self.log_structured(
            "info",
            "etl_run_started",
            source_type=source_type,
            run_id=run_id,
            **metadata
        )
    
    def log_etl_complete(
        self,
        source_type: str,
        run_id: str,
        duration: float,
        records_processed: int,
        status: str,
        **metadata
    ):
        """Log ETL run completion."""
        self.log_structured(
            "info",
            "etl_run_completed",
            source_type=source_type,
            run_id=run_id,
            duration_seconds=duration,
            records_processed=records_processed,
            status=status,
            **metadata
        )
    
    def log_etl_error(
        self,
        source_type: str,
        run_id: str,
        error: str,
        **metadata
    ):
        """Log ETL error."""
        self.log_structured(
            "error",
            "etl_run_failed",
            source_type=source_type,
            run_id=run_id,
            error=error,
            **metadata
        )
    
    def log_schema_drift(
        self,
        source_name: str,
        record_id: str,
        confidence: float,
        missing_fields: list,
        extra_fields: list,
        **metadata
    ):
        """Log schema drift detection."""
        self.log_structured(
            "warning",
            "schema_drift_detected",
            source_name=source_name,
            record_id=record_id,
            confidence_score=confidence,
            missing_fields=missing_fields,
            extra_fields=extra_fields,
            **metadata
        )


class MetricsCollector:
    """Collect and aggregate ETL metrics."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def collect_etl_metrics(self) -> Dict[str, Any]:
        """Collect ETL metrics from database."""
        metrics = {
            "timestamp": utc_now().isoformat(),
            "runs": {},
            "records": {},
            "schema_drift": {},
            "checkpoints": {}
        }
        
        # Run statistics
        runs = self.db.query(ETLRunHistory).all()
        run_stats = defaultdict(lambda: {"total": 0, "success": 0, "failure": 0})
        
        for run in runs:
            run_stats[run.source_type]["total"] += 1
            if run.status == "success":
                run_stats[run.source_type]["success"] += 1
            elif run.status == "failure":
                run_stats[run.source_type]["failure"] += 1
        
        metrics["runs"] = dict(run_stats)
        
        # Record counts by source
        from sqlalchemy import func
        record_counts = self.db.query(
            NormalizedData.source_type,
            func.count(NormalizedData.id)
        ).group_by(NormalizedData.source_type).all()
        
        metrics["records"] = {
            source_type: count for source_type, count in record_counts
        }
        
        # Schema drift statistics
        drift_counts = self.db.query(
            SchemaDriftLog.source_name,
            func.count(SchemaDriftLog.id)
        ).group_by(SchemaDriftLog.source_name).all()
        
        metrics["schema_drift"] = {
            source_name: count for source_name, count in drift_counts
        }
        
        # Checkpoint status
        checkpoints = self.db.query(ETLCheckpoint).all()
        metrics["checkpoints"] = {
            cp.source_type: {
                "status": cp.status,
                "last_success": cp.last_success_at.isoformat() if cp.last_success_at else None,
                "records_processed": cp.records_processed
            }
            for cp in checkpoints
        }
        
        return metrics
    
    def update_prometheus_metrics(self):
        """Update Prometheus gauge metrics from database."""
        from sqlalchemy import func
        
        # Update record counts
        record_counts = self.db.query(
            NormalizedData.source_type,
            func.count(NormalizedData.id)
        ).group_by(NormalizedData.source_type).all()
        
        for source_type, count in record_counts:
            db_records_total.labels(source_type=source_type).set(count)


# Create observability router
observability_router = APIRouter(prefix="/observability", tags=["observability"])


@observability_router.get("/metrics")
async def get_prometheus_metrics():
    """
    Get Prometheus metrics.
    
    Returns metrics in Prometheus exposition format.
    """
    # Update gauges with latest database values
    db = next(get_db())
    try:
        collector = MetricsCollector(db)
        collector.update_prometheus_metrics()
    finally:
        db.close()
    
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST
    )


@observability_router.get("/metrics/json")
async def get_json_metrics():
    """
    Get metrics in JSON format.
    
    Returns comprehensive ETL metrics.
    """
    db = next(get_db())
    try:
        collector = MetricsCollector(db)
        metrics = collector.collect_etl_metrics()
        
        # Add rate limiting stats
        from services.retry_service import global_rate_limiter
        metrics["rate_limiting"] = global_rate_limiter.get_stats()
        
        return metrics
    finally:
        db.close()


# Global structured logger
structured_logger = StructuredLogger("etl")
