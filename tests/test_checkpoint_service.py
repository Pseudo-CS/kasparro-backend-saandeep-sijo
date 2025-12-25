"""Tests for checkpoint service."""
import pytest
from datetime import datetime

from services.checkpoint_service import CheckpointService
from services.etl_utils import utc_now
from core.models import ETLCheckpoint, ETLRunHistory


def test_create_checkpoint(db_session):
    """Test checkpoint creation."""
    checkpoint_service = CheckpointService(db_session)
    
    checkpoint_service.update_checkpoint(
        source_type="test_source",
        status="success",
        records_processed=100
    )
    
    checkpoint = checkpoint_service.get_checkpoint("test_source")
    assert checkpoint is not None
    assert checkpoint.source_type == "test_source"
    assert checkpoint.status == "success"
    assert checkpoint.records_processed == 100


def test_update_checkpoint(db_session):
    """Test checkpoint update."""
    checkpoint_service = CheckpointService(db_session)
    
    # Create initial checkpoint
    checkpoint_service.update_checkpoint(
        source_type="test_source",
        status="running",
        records_processed=50
    )
    
    # Update checkpoint
    checkpoint_service.update_checkpoint(
        source_type="test_source",
        status="success",
        records_processed=50,
        last_processed_id="record_100"
    )
    
    checkpoint = checkpoint_service.get_checkpoint("test_source")
    assert checkpoint.status == "success"
    assert checkpoint.records_processed == 100  # 50 + 50
    assert checkpoint.last_processed_id == "record_100"
    assert checkpoint.last_success_at is not None


def test_start_run(db_session):
    """Test starting an ETL run."""
    checkpoint_service = CheckpointService(db_session)
    
    run_id = checkpoint_service.start_run(
        source_type="test_source",
        metadata={"test": "data"}
    )
    
    assert run_id.startswith("run_")
    
    # Verify run history was created
    run = db_session.query(ETLRunHistory).filter(
        ETLRunHistory.run_id == run_id
    ).first()
    
    assert run is not None
    assert run.status == "running"
    assert run.source_type == "test_source"


def test_complete_run(db_session):
    """Test completing an ETL run."""
    checkpoint_service = CheckpointService(db_session)
    
    run_id = checkpoint_service.start_run("test_source")
    
    checkpoint_service.complete_run(
        run_id=run_id,
        source_type="test_source",
        status="success",
        records_processed=100,
        records_inserted=80,
        records_updated=20,
        records_failed=0
    )
    
    run = db_session.query(ETLRunHistory).filter(
        ETLRunHistory.run_id == run_id
    ).first()
    
    assert run.status == "success"
    assert run.records_processed == 100
    assert run.records_inserted == 80
    assert run.records_updated == 20
    assert run.completed_at is not None
    assert run.duration_seconds is not None


def test_resume_on_failure(db_session):
    """Test resume-on-failure logic."""
    checkpoint_service = CheckpointService(db_session)
    
    # Create a failed checkpoint
    checkpoint_service.update_checkpoint(
        source_type="test_source",
        status="failure",
        error_message="Test error"
    )
    
    # Check if should resume
    should_resume = checkpoint_service.should_resume("test_source")
    assert should_resume is True
    
    # Update to success
    checkpoint_service.update_checkpoint(
        source_type="test_source",
        status="success"
    )
    
    # Should not resume after success
    should_resume = checkpoint_service.should_resume("test_source")
    assert should_resume is False


def test_incremental_loading(db_session):
    """Test incremental loading timestamp tracking."""
    checkpoint_service = CheckpointService(db_session)
    
    timestamp = datetime(2024, 1, 15, 10, 30, 0)
    
    checkpoint_service.update_checkpoint(
        source_type="test_source",
        status="success",
        last_processed_timestamp=timestamp
    )
    
    last_timestamp = checkpoint_service.get_last_successful_timestamp("test_source")
    assert last_timestamp == timestamp


def test_checkpoint_failure_tracking(db_session):
    """Test failure tracking in checkpoints."""
    checkpoint_service = CheckpointService(db_session)
    
    # Create successful checkpoint
    checkpoint_service.update_checkpoint(
        source_type="test_source",
        status="success"
    )
    
    checkpoint = checkpoint_service.get_checkpoint("test_source")
    assert checkpoint.last_success_at is not None
    assert checkpoint.last_failure_at is None
    
    # Update with failure
    checkpoint_service.update_checkpoint(
        source_type="test_source",
        status="failure",
        error_message="Test error"
    )
    
    checkpoint = checkpoint_service.get_checkpoint("test_source")
    assert checkpoint.last_failure_at is not None
    assert checkpoint.error_message == "Test error"
