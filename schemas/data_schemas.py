"""Pydantic schemas for data validation and API responses."""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Any, Dict
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    """Data source types."""
    CSV = "csv"
    API1 = "api1"
    API2 = "api2"
    RSS = "rss"


class ETLStatus(str, Enum):
    """ETL run status."""
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"


# === Data Validation Schemas ===

class RawDataBase(BaseModel):
    """Base schema for raw data."""
    source_id: str
    raw_data: Dict[str, Any]


class CSVRecordSchema(BaseModel):
    """Schema for CSV data validation."""
    id: str = Field(..., description="Unique identifier")
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    value: Optional[float] = None
    category: Optional[str] = None
    timestamp: Optional[datetime] = None
    
    @validator('value')
    def validate_value(cls, v):
        if v is not None and v < 0:
            raise ValueError('Value must be non-negative')
        return v


class APIRecordSchema(BaseModel):
    """Schema for API data validation."""
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    amount: Optional[float] = None
    type: Optional[str] = None
    created_at: Optional[datetime] = None
    tags: Optional[List[str]] = []


class RSSRecordSchema(BaseModel):
    """Schema for RSS feed data validation."""
    id: str = Field(..., description="Unique identifier (link or guid)")
    title: str
    summary: Optional[str] = None
    link: str
    published: Optional[datetime] = None
    categories: Optional[List[str]] = []


class NormalizedDataSchema(BaseModel):
    """Unified schema for normalized data."""
    source_type: SourceType
    source_id: str
    title: str
    description: Optional[str] = None
    value: Optional[float] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    source_timestamp: Optional[datetime] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True


# === API Response Schemas ===

class PaginationMetadata(BaseModel):
    """Pagination metadata."""
    page: int
    page_size: int
    total_records: int
    total_pages: int


class DataResponseMetadata(BaseModel):
    """Metadata for data endpoint responses."""
    request_id: str
    api_latency_ms: float
    pagination: PaginationMetadata
    filters_applied: Optional[Dict[str, Any]] = None


class DataResponse(BaseModel):
    """Response schema for GET /data endpoint."""
    data: List[NormalizedDataSchema]
    metadata: DataResponseMetadata


class HealthStatus(BaseModel):
    """Health check response."""
    status: str
    database_connected: bool
    etl_last_run: Optional[datetime] = None
    etl_status: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ETLStatistics(BaseModel):
    """ETL statistics for /stats endpoint."""
    source_type: str
    records_processed: int
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    status: str
    extra_metadata: Optional[Dict[str, Any]] = None


class ETLRunSummary(BaseModel):
    """Summary of a single ETL run."""
    run_id: str
    source_type: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    records_processed: int
    records_inserted: int
    records_updated: int
    records_failed: int
    status: str
    
    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    """Response schema for GET /stats endpoint."""
    checkpoints: List[ETLStatistics]
    recent_runs: List[ETLRunSummary]
    summary: Dict[str, Any]


# === Error Schemas ===

class ErrorResponse(BaseModel):
    """Error response schema."""
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
