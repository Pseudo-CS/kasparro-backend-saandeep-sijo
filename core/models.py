"""SQLAlchemy database models."""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, Index
from sqlalchemy.sql import func
from datetime import datetime

from core.database import Base


class RawCSVData(Base):
    """Raw CSV data storage."""
    __tablename__ = "raw_csv_data"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(255), unique=True, nullable=False, index=True)  # Unique identifier from source
    raw_data = Column(JSON, nullable=False)  # Store entire row as JSON
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        Index('idx_raw_csv_ingested_at', 'ingested_at'),
    )


class RawAPIData(Base):
    """Raw API data storage."""
    __tablename__ = "raw_api_data"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(255), unique=True, nullable=False, index=True)
    source_name = Column(String(50), nullable=False, index=True)  # API1, API2, etc.
    raw_data = Column(JSON, nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        Index('idx_raw_api_source_ingested', 'source_name', 'ingested_at'),
    )


class RawRSSData(Base):
    """Raw RSS feed data storage."""
    __tablename__ = "raw_rss_data"
    
    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(String(500), unique=True, nullable=False, index=True)  # RSS entry ID or link (URLs can be long)
    raw_data = Column(JSON, nullable=False)
    ingested_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        Index('idx_raw_rss_ingested_at', 'ingested_at'),
    )


class NormalizedData(Base):
    """Unified normalized data across all sources."""
    __tablename__ = "normalized_data"
    
    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(50), nullable=False, index=True)  # csv, api1, api2, rss
    source_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Identity unification field
    canonical_id = Column(String(255), index=True, nullable=True)  # Unified identity across sources
    
    # Common fields across all sources
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    value = Column(Float, nullable=True)
    category = Column(String(100), nullable=True)
    tags = Column(JSON, nullable=True)
    
    # Timestamps
    source_timestamp = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    
    # Additional metadata
    extra_metadata = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('idx_normalized_source_type', 'source_type'),
        Index('idx_normalized_created_at', 'created_at'),
        Index('idx_normalized_category', 'category'),
        Index('idx_normalized_canonical_id', 'canonical_id'),
        Index('idx_normalized_source_canonical', 'source_type', 'canonical_id'),  # Composite for entity queries
        Index('idx_normalized_timestamp', 'source_timestamp'),  # For time-series queries
    )


class ETLCheckpoint(Base):
    """ETL checkpoint tracking for incremental ingestion."""
    __tablename__ = "etl_checkpoints"
    
    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String(50), unique=True, nullable=False, index=True)  # csv, api1, api2, rss
    last_processed_id = Column(String(255), nullable=True)
    last_processed_timestamp = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    records_processed = Column(Integer, nullable=False, default=0)
    status = Column(String(20), nullable=False)  # success, failure, running
    error_message = Column(Text, nullable=True)
    extra_metadata = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('idx_checkpoint_source_type', 'source_type'),
        Index('idx_checkpoint_status', 'status'),
    )


class ETLRunHistory(Base):
    """ETL run history for monitoring and statistics."""
    __tablename__ = "etl_run_history"
    
    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    source_type = Column(String(50), nullable=False, index=True)
    
    # Run details
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Statistics
    records_processed = Column(Integer, nullable=False, default=0)
    records_inserted = Column(Integer, nullable=False, default=0)
    records_updated = Column(Integer, nullable=False, default=0)
    records_failed = Column(Integer, nullable=False, default=0)
    
    # Status
    status = Column(String(20), nullable=False)  # running, success, failure, partial
    error_message = Column(Text, nullable=True)
    
    # Additional metadata
    extra_metadata = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('idx_run_history_started_at', 'started_at'),
        Index('idx_run_history_status', 'status'),
        Index('idx_run_history_source_started', 'source_type', 'started_at'),  # Composite for source-specific queries
    )


class SchemaDriftLog(Base):
    """Schema drift detection log."""
    __tablename__ = "schema_drift_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    source_name = Column(String(50), nullable=False, index=True)
    record_id = Column(String(255), nullable=False, index=True)
    confidence_score = Column(Float, nullable=False)  # 0-1 confidence of drift
    
    # Drift details
    missing_fields = Column(JSON, nullable=True)  # Fields missing from actual data
    extra_fields = Column(JSON, nullable=True)  # Unexpected fields in actual data
    type_mismatches = Column(JSON, nullable=True)  # Type inconsistencies
    fuzzy_suggestions = Column(JSON, nullable=True)  # Fuzzy match suggestions
    
    detected_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    __table_args__ = (
        Index('idx_drift_detected_at', 'detected_at'),
        Index('idx_drift_source_name', 'source_name'),
        Index('idx_drift_source_detected', 'source_name', 'detected_at'),  # Composite for time-series drift analysis
    )
