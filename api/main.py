"""FastAPI application with data endpoints."""
from fastapi import FastAPI, Query, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_
from typing import Optional, List
import uuid
from datetime import datetime
import time
import logging

from core.database import get_db_session, test_connection
from core.config import settings
from core.models import NormalizedData, ETLCheckpoint, ETLRunHistory
from services.etl_utils import utc_now
from schemas.data_schemas import (
    DataResponse,
    DataResponseMetadata,
    PaginationMetadata,
    NormalizedDataSchema,
    HealthStatus,
    StatsResponse,
    ETLStatistics,
    ETLRunSummary,
    ErrorResponse
)
from services.observability import observability_router, api_requests_total, api_request_duration

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-grade ETL Backend Service"
)

# Include observability router (P2.4)
app.include_router(observability_router)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Middleware to track API request metrics."""
    start_time = time.time()
    
    response = await call_next(request)
    
    duration = time.time() - start_time
    
    # Track metrics
    api_requests_total.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    api_request_duration.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get(
    "/data",
    response_model=DataResponse,
    tags=["Data"],
    summary="Get normalized data with pagination and filtering"
)
async def get_data(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=1000, description="Items per page"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    category: Optional[str] = Query(None, description="Filter by category"),
    canonical_id: Optional[str] = Query(None, description="Filter by canonical identity"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    db: Session = Depends(get_db_session)
):
    """
    Get normalized data with pagination and filtering.
    
    - **page**: Page number (starts at 1)
    - **page_size**: Number of items per page (max 1000)
    - **source_type**: Filter by source type (csv, api1, api2, rss)
    - **category**: Filter by category
    - **canonical_id**: Filter by canonical identity (unified entity ID across sources)
    - **search**: Search term for title and description
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Build query
    query = db.query(NormalizedData)
    
    # Apply filters
    filters_applied = {}
    if source_type:
        query = query.filter(NormalizedData.source_type == source_type)
        filters_applied["source_type"] = source_type
    
    if category:
        query = query.filter(NormalizedData.category == category)
        filters_applied["category"] = category
    
    if canonical_id:
        query = query.filter(NormalizedData.canonical_id == canonical_id)
        filters_applied["canonical_id"] = canonical_id
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            (NormalizedData.title.ilike(search_filter)) |
            (NormalizedData.description.ilike(search_filter))
        )
        filters_applied["search"] = search
    
    # Get total count
    total_records = query.count()
    total_pages = (total_records + page_size - 1) // page_size
    
    # Apply pagination
    offset = (page - 1) * page_size
    records = query.order_by(desc(NormalizedData.created_at)).offset(offset).limit(page_size).all()
    
    # Convert to schemas
    data = [NormalizedDataSchema.model_validate(record) for record in records]
    
    # Calculate latency
    latency_ms = (time.time() - start_time) * 1000
    
    # Build response
    response = DataResponse(
        data=data,
        metadata=DataResponseMetadata(
            request_id=request_id,
            api_latency_ms=round(latency_ms, 2),
            pagination=PaginationMetadata(
                page=page,
                page_size=page_size,
                total_records=total_records,
                total_pages=total_pages
            ),
            filters_applied=filters_applied if filters_applied else None
        )
    )
    
    logger.info(
        f"GET /data - request_id={request_id}, "
        f"page={page}, records={len(data)}, latency={latency_ms:.2f}ms"
    )
    
    return response


@app.get(
    "/entities/{canonical_id}",
    response_model=DataResponse,
    tags=["Data"],
    summary="Get all source records for a unified entity"
)
async def get_entity_sources(
    canonical_id: str,
    db: Session = Depends(get_db_session)
):
    """
    Get all source records for a canonical entity.
    
    Returns all records from different data sources that refer to the same
    real-world entity (e.g., Bitcoin from CSV, API, and RSS sources).
    
    - **canonical_id**: The canonical identity (e.g., "bitcoin", "ethereum")
    """
    start_time = time.time()
    request_id = str(uuid.uuid4())
    
    # Query all records with this canonical ID
    records = db.query(NormalizedData).filter(
        NormalizedData.canonical_id == canonical_id
    ).order_by(NormalizedData.source_type, desc(NormalizedData.created_at)).all()
    
    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"No records found for canonical_id: {canonical_id}"
        )
    
    # Convert to schemas
    data = [NormalizedDataSchema.model_validate(record) for record in records]
    
    # Calculate latency
    latency_ms = (time.time() - start_time) * 1000
    
    # Build response
    response = DataResponse(
        data=data,
        metadata=DataResponseMetadata(
            request_id=request_id,
            api_latency_ms=round(latency_ms, 2),
            pagination=PaginationMetadata(
                page=1,
                page_size=len(data),
                total_records=len(data),
                total_pages=1
            ),
            filters_applied={"canonical_id": canonical_id}
        )
    )
    
    logger.info(
        f"GET /entities/{canonical_id} - request_id={request_id}, "
        f"sources={len(data)}, latency={latency_ms:.2f}ms"
    )
    
    return response


@app.get(
    "/health",
    response_model=HealthStatus,
    tags=["Health"],
    summary="Health check endpoint"
)
async def health_check(db: Session = Depends(get_db_session)):
    """
    Health check endpoint.
    
    Returns service health status including:
    - Database connectivity
    - Last ETL run status and timestamp
    """
    # Check database connectivity
    db_connected = test_connection()
    
    # Get latest ETL status
    latest_checkpoint = db.query(ETLCheckpoint).order_by(
        desc(ETLCheckpoint.last_success_at)
    ).first()
    
    etl_last_run = None
    etl_status = "unknown"
    
    if latest_checkpoint:
        etl_last_run = latest_checkpoint.last_success_at
        etl_status = latest_checkpoint.status
    
    status = "healthy" if db_connected else "unhealthy"
    
    return HealthStatus(
        status=status,
        database_connected=db_connected,
        etl_last_run=etl_last_run,
        etl_status=etl_status,
        timestamp=utc_now()
    )


@app.get(
    "/stats",
    response_model=StatsResponse,
    tags=["Stats"],
    summary="Get ETL statistics and summaries"
)
async def get_stats(
    limit: int = Query(10, ge=1, le=100, description="Number of recent runs to return"),
    db: Session = Depends(get_db_session)
):
    """
    Get ETL statistics and summaries.
    
    Returns:
    - Checkpoint status for each source
    - Recent ETL run history
    - Summary statistics
    """
    # Get all checkpoints
    checkpoints = db.query(ETLCheckpoint).all()
    checkpoint_stats = []
    
    for checkpoint in checkpoints:
        checkpoint_stats.append(
            ETLStatistics(
                source_type=checkpoint.source_type,
                records_processed=checkpoint.records_processed,
                last_success_at=checkpoint.last_success_at,
                last_failure_at=checkpoint.last_failure_at,
                status=checkpoint.status,
                extra_metadata=checkpoint.extra_metadata
            )
        )
    
    # Get recent runs
    recent_runs_query = db.query(ETLRunHistory).order_by(
        desc(ETLRunHistory.started_at)
    ).limit(limit)
    
    recent_runs = [
        ETLRunSummary.model_validate(run)
        for run in recent_runs_query.all()
    ]
    
    # Calculate summary statistics
    total_processed = sum(c.records_processed for c in checkpoints)
    successful_sources = sum(1 for c in checkpoints if c.status == "success")
    failed_sources = sum(1 for c in checkpoints if c.status == "failure")
    
    # Get total records in normalized table
    total_records = db.query(NormalizedData).count()
    
    summary = {
        "total_records_normalized": total_records,
        "total_records_processed": total_processed,
        "successful_sources": successful_sources,
        "failed_sources": failed_sources,
        "total_sources": len(checkpoints)
    }
    
    return StatsResponse(
        checkpoints=checkpoint_stats,
        recent_runs=recent_runs,
        summary=summary
    )


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return ErrorResponse(
        error="Internal server error",
        detail=str(exc)
    )


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Test database connection
    if test_connection():
        logger.info("Database connection successful")
    else:
        logger.error("Database connection failed!")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down application")
