"""CSV data ingestion service."""
import pandas as pd
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from core.models import RawCSVData, NormalizedData
from schemas.data_schemas import CSVRecordSchema, NormalizedDataSchema, SourceType
from services.etl_utils import generate_source_id, safe_parse_datetime, safe_float, utc_now
from services.checkpoint_service import CheckpointService
from services.schema_drift_service import SchemaDriftDetector
from services.failure_injection_service import FailureInjector
from services.identity_resolution import IdentityResolver

logger = logging.getLogger(__name__)


class CSVIngestionService:
    """Service for ingesting CSV data."""
    
    def __init__(
        self, 
        db: Session, 
        checkpoint_service: CheckpointService,
        failure_injector: Optional[FailureInjector] = None
    ):
        self.db = db
        self.checkpoint_service = checkpoint_service
        self.source_type = SourceType.CSV.value
        
        # Initialize identity resolver
        self.identity_resolver = IdentityResolver(db)
        
        # Initialize schema drift detector
        self.drift_detector = SchemaDriftDetector(db, self.source_type)
        self._setup_expected_schema()
        
        # Initialize failure injector (P2.2)
        self.failure_injector = failure_injector or FailureInjector.from_env()
    
    def _setup_expected_schema(self):
        """Define expected CSV schema for drift detection."""
        expected_schema = {
            "id": str,
            "title": str,
            "description": str,
            "value": float,
            "category": str,
            "timestamp": str
        }
        self.drift_detector.set_expected_schema(expected_schema)
    
    def ingest(self, csv_path: str, batch_size: int = 1000) -> dict:
        """
        Ingest data from CSV file.
        
        Args:
            csv_path: Path to CSV file
            batch_size: Number of records to process per batch
            
        Returns:
            Statistics dictionary
        """
        logger.info(f"Starting CSV ingestion from {csv_path}")
        
        # Start ETL run
        run_id = self.checkpoint_service.start_run(
            self.source_type,
            metadata={"csv_path": csv_path}
        )
        
        stats = {
            "processed": 0,
            "inserted": 0,
            "updated": 0,
            "failed": 0,
            "errors": []
        }
        
        try:
            # Get last processed timestamp for incremental loading
            last_timestamp = self.checkpoint_service.get_last_successful_timestamp(
                self.source_type
            )
            
            # Read CSV file
            df = pd.read_csv(csv_path)
            logger.info(f"Loaded {len(df)} records from CSV")
            
            # Process in batches
            for i in range(0, len(df), batch_size):
                batch_df = df.iloc[i:i + batch_size]
                batch_stats = self._process_batch(batch_df, last_timestamp)
                
                stats["processed"] += batch_stats["processed"]
                stats["inserted"] += batch_stats["inserted"]
                stats["updated"] += batch_stats["updated"]
                stats["failed"] += batch_stats["failed"]
                stats["errors"].extend(batch_stats["errors"])
                
                # Update checkpoint after each batch
                if batch_stats["processed"] > 0:
                    self.checkpoint_service.update_checkpoint(
                        self.source_type,
                        "running",
                        records_processed=batch_stats["processed"]
                    )
            
            # Complete run successfully
            self.checkpoint_service.complete_run(
                run_id,
                self.source_type,
                "success",
                records_processed=stats["processed"],
                records_inserted=stats["inserted"],
                records_updated=stats["updated"],
                records_failed=stats["failed"]
            )
            
            logger.info(f"CSV ingestion completed: {stats}")
            
        except Exception as e:
            logger.error(f"CSV ingestion failed: {e}")
            stats["errors"].append(str(e))
            
            # Mark run as failed
            self.checkpoint_service.complete_run(
                run_id,
                self.source_type,
                "failure",
                error_message=str(e)
            )
            raise
        
        return stats
    
    def _process_batch(
        self,
        batch_df: pd.DataFrame,
        last_timestamp: Optional[datetime]
    ) -> dict:
        """
        Process a batch of CSV records.
        
        Args:
            batch_df: Batch dataframe
            last_timestamp: Last processed timestamp for incremental loading
            
        Returns:
            Batch statistics
        """
        stats = {
            "processed": 0,
            "inserted": 0,
            "updated": 0,
            "failed": 0,
            "errors": []
        }
        
        for _, row in batch_df.iterrows():
            # P2.2: Check for failure injection BEFORE try-except
            self.failure_injector.check_and_fail()
            
            try:
                # Convert row to dictionary
                raw_data = row.to_dict()
                
                # Detect schema drift
                source_id = generate_source_id(self.source_type, raw_data)
                drift_result = self.drift_detector.detect_drift(raw_data, source_id)
                
                # Validate with Pydantic
                record = CSVRecordSchema(
                    id=raw_data.get('id', source_id),
                    title=raw_data.get('title', ''),
                    description=raw_data.get('description'),
                    value=safe_float(raw_data.get('value')),
                    category=raw_data.get('category'),
                    timestamp=safe_parse_datetime(raw_data.get('timestamp'))
                )
                
                # Check if should process (incremental)
                if last_timestamp and record.timestamp:
                    if record.timestamp <= last_timestamp:
                        continue  # Skip already processed
                
                # Store raw data (idempotent - upsert)
                self._upsert_raw_data(source_id, raw_data)
                
                # Normalize and store
                normalized = self._normalize_record(source_id, record, raw_data)
                is_new = self._upsert_normalized_data(normalized)
                
                if is_new:
                    stats["inserted"] += 1
                else:
                    stats["updated"] += 1
                
                stats["processed"] += 1
                
            except Exception as e:
                logger.warning(f"Failed to process CSV record: {e}")
                stats["failed"] += 1
                stats["errors"].append(str(e))
        
        self.db.commit()
        return stats
    
    def _upsert_raw_data(self, source_id: str, raw_data: dict):
        """Store or update raw CSV data."""
        existing = self.db.query(RawCSVData).filter(
            RawCSVData.source_id == source_id
        ).first()
        
        if existing:
            existing.raw_data = raw_data
        else:
            raw_record = RawCSVData(
                source_id=source_id,
                raw_data=raw_data
            )
            self.db.add(raw_record)
    
    def _normalize_record(
        self,
        source_id: str,
        record: CSVRecordSchema,
        raw_data: dict
    ) -> NormalizedDataSchema:
        """Normalize CSV record to unified schema with canonical ID."""
        # Resolve canonical identity
        canonical_id = self.identity_resolver.resolve_canonical_id(
            source_type=self.source_type,
            title=record.title,
            data=raw_data
        )
        
        return NormalizedDataSchema(
            source_type=SourceType.CSV,
            source_id=source_id,
            canonical_id=canonical_id,
            title=record.title,
            description=record.description,
            value=record.value,
            category=record.category,
            tags=None,
            source_timestamp=record.timestamp,
            extra_metadata={"original_id": record.id}
        )
    
    def _upsert_normalized_data(self, normalized: NormalizedDataSchema) -> bool:
        """
        Store or update normalized data with canonical ID support.
        
        Returns:
            True if inserted, False if updated
        """
        existing = self.db.query(NormalizedData).filter(
            NormalizedData.source_id == normalized.source_id
        ).first()
        
        if existing:
            # Update existing record
            existing.canonical_id = normalized.canonical_id
            existing.title = normalized.title
            existing.description = normalized.description
            existing.value = normalized.value
            existing.category = normalized.category
            existing.tags = normalized.tags
            existing.source_timestamp = normalized.source_timestamp
            existing.extra_metadata = normalized.extra_metadata
            existing.updated_at = utc_now()
            return False
        else:
            # Insert new record
            new_record = NormalizedData(
                source_type=normalized.source_type.value,
                source_id=normalized.source_id,
                canonical_id=normalized.canonical
            existing.source_timestamp = normalized.source_timestamp
            existing.extra_metadata = normalized.extra_metadata
            existing.updated_at = utc_now()
            return False
        else:
            # Insert new record
            new_record = NormalizedData(
                source_type=normalized.source_type.value,
                source_id=normalized.source_id,
                title=normalized.title,
                description=normalized.description,
                value=normalized.value,
                category=normalized.category,
                tags=normalized.tags,
                source_timestamp=normalized.source_timestamp,
                extra_metadata=normalized.extra_metadata
            )
            self.db.add(new_record)
            return True
