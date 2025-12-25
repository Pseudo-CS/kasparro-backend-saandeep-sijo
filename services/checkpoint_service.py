"""Checkpoint service for incremental ingestion and resume-on-failure."""
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from core.models import ETLCheckpoint, ETLRunHistory
from services.etl_utils import generate_run_id, utc_now, ensure_timezone_aware

logger = logging.getLogger(__name__)


class CheckpointService:
    """Service for managing ETL checkpoints."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_checkpoint(self, source_type: str) -> Optional[ETLCheckpoint]:
        """
        Get the current checkpoint for a source.
        
        Args:
            source_type: Type of data source
            
        Returns:
            Checkpoint record or None
        """
        return self.db.query(ETLCheckpoint).filter(
            ETLCheckpoint.source_type == source_type
        ).first()
    
    def update_checkpoint(
        self,
        source_type: str,
        status: str,
        records_processed: int = 0,
        last_processed_id: Optional[str] = None,
        last_processed_timestamp: Optional[datetime] = None,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Update or create checkpoint for a source.
        
        Args:
            source_type: Type of data source
            status: Current status (success, failure, running)
            records_processed: Number of records processed in this run
            last_processed_id: Last successfully processed record ID
            last_processed_timestamp: Last successfully processed timestamp
            error_message: Error message if failed
            metadata: Additional metadata
        """
        checkpoint = self.get_checkpoint(source_type)
        
        if checkpoint is None:
            checkpoint = ETLCheckpoint(
                source_type=source_type,
                status=status,
                records_processed=records_processed,
                last_processed_id=last_processed_id,
                last_processed_timestamp=last_processed_timestamp,
                metadata=metadata or {}
            )
            self.db.add(checkpoint)
        else:
            checkpoint.status = status
            checkpoint.records_processed += records_processed
            
            if last_processed_id:
                checkpoint.last_processed_id = last_processed_id
            if last_processed_timestamp:
                checkpoint.last_processed_timestamp = last_processed_timestamp
            if metadata:
                checkpoint.metadata = metadata
        
        # Update success/failure timestamps
        if status == "success":
            checkpoint.last_success_at = utc_now()
            checkpoint.error_message = None
        elif status == "failure":
            checkpoint.last_failure_at = utc_now()
            checkpoint.error_message = error_message
        
        self.db.commit()
        logger.info(f"Checkpoint updated for {source_type}: {status}")
    
    def start_run(self, source_type: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Start a new ETL run and return run ID.
        
        Args:
            source_type: Type of data source
            metadata: Additional metadata
            
        Returns:
            Run ID
        """
        run_id = generate_run_id()
        
        run_history = ETLRunHistory(
            run_id=run_id,
            source_type=source_type,
            status="running",
            started_at=datetime.utcnow(),
            metadata=metadata or {}
        )
        
        self.db.add(run_history)
        self.db.commit()
        
        # Update checkpoint to running status
        self.update_checkpoint(source_type, "running")
        
        logger.info(f"Started ETL run {run_id} for {source_type}")
        return run_id
    
    def complete_run(
        self,
        run_id: str,
        source_type: str,
        status: str,
        records_processed: int = 0,
        records_inserted: int = 0,
        records_updated: int = 0,
        records_failed: int = 0,
        error_message: Optional[str] = None
    ):
        """
        Complete an ETL run.
        
        Args:
            run_id: Run ID
            source_type: Type of data source
            status: Final status
            records_processed: Total records processed
            records_inserted: Records inserted
            records_updated: Records updated
            records_failed: Records failed
            error_message: Error message if failed
        """
        run_history = self.db.query(ETLRunHistory).filter(
            ETLRunHistory.run_id == run_id
        ).first()
        
        if run_history:
            run_history.completed_at = utc_now()
            # Ensure started_at is timezone-aware (SQLite loses timezone info)
            started_at = ensure_timezone_aware(run_history.started_at)
            run_history.duration_seconds = (
                run_history.completed_at - started_at
            ).total_seconds()
            run_history.status = status
            run_history.records_processed = records_processed
            run_history.records_inserted = records_inserted
            run_history.records_updated = records_updated
            run_history.records_failed = records_failed
            run_history.error_message = error_message
            
            self.db.commit()
        
        # Update checkpoint with final status
        self.update_checkpoint(
            source_type,
            status,
            records_processed=records_processed,
            error_message=error_message
        )
        
        logger.info(f"Completed ETL run {run_id}: {status}")
    
    def get_last_successful_timestamp(self, source_type: str) -> Optional[datetime]:
        """
        Get the last successful processing timestamp for incremental loading.
        Ensures timezone-awareness for SQLite compatibility.
        
        Args:
            source_type: Type of data source
            
        Returns:
            Last successful timestamp (timezone-aware) or None
        """
        checkpoint = self.get_checkpoint(source_type)
        if checkpoint and checkpoint.last_processed_timestamp:
            return ensure_timezone_aware(checkpoint.last_processed_timestamp)
        return None
    
    def should_resume(self, source_type: str) -> bool:
        """
        Check if ETL should resume from a failed state.
        
        Args:
            source_type: Type of data source
            
        Returns:
            True if should resume, False otherwise
        """
        checkpoint = self.get_checkpoint(source_type)
        if checkpoint and checkpoint.status in ["failure", "running"]:
            logger.info(f"Resuming ETL for {source_type} from last checkpoint")
            return True
        return False
