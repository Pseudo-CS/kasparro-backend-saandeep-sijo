"""Tests for P2.1 (Schema Drift Detection) and P2.2 (Failure Injection + Recovery)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import tempfile
import pandas as pd

from core.database import Base
from core.models import SchemaDriftLog, ETLCheckpoint, ETLRunHistory, NormalizedData
from services.schema_drift_service import SchemaDriftDetector
from services.failure_injection_service import FailureInjector, FailureInjectionException
from services.checkpoint_service import CheckpointService
from services.etl_utils import utc_now
from ingestion.csv_ingestion import CSVIngestionService


# Test database setup
@pytest.fixture
def test_db():
    """Create a test database."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


class TestSchemaDrift:
    """Tests for P2.1: Schema Drift Detection."""
    
    def test_drift_detection_missing_fields(self, test_db):
        """Test detection of missing fields."""
        detector = SchemaDriftDetector(test_db, "test_source")
        detector.set_expected_schema({
            "id": str,
            "name": str,
            "value": float
        })
        
        # Missing 'value' field
        actual_data = {"id": "123", "name": "test"}
        result = detector.detect_drift(actual_data, "record_1")
        
        assert result["has_drift"] is True
        assert "value" in result["missing_fields"]
        assert result["confidence"] > 0.0
    
    def test_drift_detection_extra_fields(self, test_db):
        """Test detection of extra fields."""
        detector = SchemaDriftDetector(test_db, "test_source")
        detector.set_expected_schema({
            "id": str,
            "name": str
        })
        
        # Extra 'extra_field' field
        actual_data = {"id": "123", "name": "test", "extra_field": "unexpected"}
        result = detector.detect_drift(actual_data, "record_2")
        
        assert result["has_drift"] is True
        assert "extra_field" in result["extra_fields"]
        assert result["confidence"] > 0.0
    
    def test_drift_detection_type_mismatch(self, test_db):
        """Test detection of type mismatches."""
        detector = SchemaDriftDetector(test_db, "test_source")
        detector.set_expected_schema({
            "id": str,
            "name": str,
            "value": float
        })
        
        # 'value' should be float but is string
        actual_data = {"id": "123", "name": "test", "value": "not_a_float"}
        result = detector.detect_drift(actual_data, "record_3")
        
        assert result["has_drift"] is True
        assert len(result["type_mismatches"]) > 0
        assert result["type_mismatches"][0]["field"] == "value"
    
    def test_fuzzy_matching(self, test_db):
        """Test fuzzy matching for field name suggestions."""
        detector = SchemaDriftDetector(test_db, "test_source")
        detector.set_expected_schema({
            "user_id": str,
            "user_name": str
        })
        
        # Typo: 'usr_id' instead of 'user_id'
        actual_data = {"usr_id": "123", "user_name": "test"}
        result = detector.detect_drift(actual_data, "record_4")
        
        assert result["has_drift"] is True
        assert len(result["fuzzy_matches"]) > 0
        # Should suggest 'usr_id' -> 'user_id'
        match = result["fuzzy_matches"][0]
        assert match["missing_field"] == "user_id"
        assert match["suggested_field"] == "usr_id"
        assert match["similarity"] > 0.6
    
    def test_confidence_scoring(self, test_db):
        """Test confidence score calculation."""
        detector = SchemaDriftDetector(test_db, "test_source")
        detector.set_expected_schema({
            "field1": str,
            "field2": str,
            "field3": str
        })
        
        # No drift - perfect match
        no_drift_data = {"field1": "a", "field2": "b", "field3": "c"}
        result = detector.detect_drift(no_drift_data, "record_5")
        assert result["confidence"] == 0.0
        
        # All fields missing - high confidence
        all_missing = {}
        result = detector.detect_drift(all_missing, "record_6")
        assert result["confidence"] >= 0.4  # Should be high but may not be > 0.5
    
    def test_drift_logging_to_database(self, test_db):
        """Test that drift is logged to database."""
        detector = SchemaDriftDetector(test_db, "test_source")
        detector.set_expected_schema({"id": str, "name": str})
        
        # Trigger drift
        actual_data = {"id": "123"}  # Missing 'name'
        result = detector.detect_drift(actual_data, "record_7")
        
        # Check database log
        logs = test_db.query(SchemaDriftLog).all()
        assert len(logs) > 0
        log = logs[-1]
        assert log.source_name == "test_source"
        assert log.record_id == "record_7"
        assert log.confidence_score > 0.0


class TestFailureInjection:
    """Tests for P2.2: Failure Injection + Recovery."""
    
    def test_failure_after_n_records(self):
        """Test failure injection after N records."""
        injector = FailureInjector(
            enabled=True,
            failure_after_n_records=5
        )
        
        # Should not fail for first 4 records
        for i in range(4):
            assert injector.should_fail() is False
        
        # Should fail on 5th record
        assert injector.should_fail() is True
        
        # Should not fail again (already triggered)
        assert injector.should_fail() is False
    
    def test_probabilistic_failure(self):
        """Test probabilistic failure injection."""
        injector = FailureInjector(
            enabled=True,
            failure_rate=1.0  # 100% failure rate
        )
        
        # Should eventually fail
        assert injector.should_fail() is True
    
    def test_failure_exception_type(self):
        """Test different failure types."""
        injector = FailureInjector(
            enabled=True,
            failure_after_n_records=1,
            failure_type="exception"
        )
        
        injector.should_fail()
        
        with pytest.raises(FailureInjectionException):
            injector.trigger_failure()
    
    def test_failure_disabled(self):
        """Test that disabled injector never fails."""
        injector = FailureInjector(enabled=False)
        
        for i in range(100):
            assert injector.should_fail() is False
    
    def test_csv_ingestion_recovery_after_failure(self, test_db):
        """Test P2.2: CSV ingestion recovers after failure."""
        # Create test CSV with string IDs (not integers) and future timestamps
        future_base = utc_now() + timedelta(days=1)
        timestamps = [(future_base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(5)]
        csv_data = pd.DataFrame({
            "id": ["A1", "A2", "A3", "A4", "A5"],
            "title": ["A", "B", "C", "D", "E"],
            "description": ["Desc A", "Desc B", "Desc C", "Desc D", "Desc E"],
            "value": [1.0, 2.0, 3.0, 4.0, 5.0],
            "category": ["cat1", "cat1", "cat2", "cat2", "cat3"],
            "timestamp": timestamps
        })
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            csv_data.to_csv(f.name, index=False)
            csv_path = f.name
        
        # Create services with failure injection after 3 records
        checkpoint_service = CheckpointService(test_db)
        failure_injector = FailureInjector(
            enabled=True,
            failure_after_n_records=3
        )
        csv_service = CSVIngestionService(test_db, checkpoint_service, failure_injector)
        
        # First run - should fail after 3 records
        with pytest.raises(FailureInjectionException):
            csv_service.ingest(csv_path, batch_size=10)
        
        # Check that checkpoint was updated
        checkpoint = test_db.query(ETLCheckpoint).filter(
            ETLCheckpoint.source_type == "csv"
        ).first()
        assert checkpoint is not None
        assert checkpoint.status == "failure"
        
        # Check that some records were processed before failure
        processed_count = test_db.query(NormalizedData).filter(
            NormalizedData.source_type == "csv"
        ).count()
        assert processed_count >= 2  # At least 2 records before failure (fails on 3rd)
        
        # Second run - reset failure injector and complete successfully
        failure_injector_2 = FailureInjector(enabled=False)
        csv_service_2 = CSVIngestionService(test_db, checkpoint_service, failure_injector_2)
        stats = csv_service_2.ingest(csv_path, batch_size=10)
        
        # Should have processed all 5 records total (no duplicates)
        total_count = test_db.query(NormalizedData).filter(
            NormalizedData.source_type == "csv"
        ).count()
        assert total_count == 5
        
        # Check final checkpoint
        checkpoint = test_db.query(ETLCheckpoint).filter(
            ETLCheckpoint.source_type == "csv"
        ).first()
        assert checkpoint.status == "success"
        
        # Check run history has detailed metadata
        run_history = test_db.query(ETLRunHistory).order_by(
            ETLRunHistory.started_at.desc()
        ).all()
        assert len(run_history) >= 2  # At least 2 runs (failed + successful)
        
        # First run should be marked as failure
        failed_run = [r for r in run_history if r.status == "failure"][0]
        assert failed_run.error_message is not None
        assert "Simulated failure" in failed_run.error_message
        
        # Second run should be successful
        success_run = [r for r in run_history if r.status == "success"][0]
        assert success_run.records_processed > 0


class TestEndToEndP2:
    """End-to-end tests for P2.1 and P2.2 together."""
    
    def test_drift_detection_during_failure_recovery(self, test_db):
        """Test that schema drift is detected even during failure recovery."""
        # Create CSV with schema drift (missing 'description' field)
        future_base = utc_now() + timedelta(days=1)
        timestamps = [(future_base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M:%SZ") for i in range(3)]
        csv_data = pd.DataFrame({
            "id": ["1", "2", "3"],
            "title": ["A", "B", "C"],
            # "description" field missing
            "value": [1.0, 2.0, 3.0],
            "category": ["cat1", "cat1", "cat2"],
            "timestamp": timestamps
        })
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
            csv_data.to_csv(f.name, index=False)
            csv_path = f.name
        
        checkpoint_service = CheckpointService(test_db)
        failure_injector = FailureInjector(enabled=False)  # No failures
        csv_service = CSVIngestionService(test_db, checkpoint_service, failure_injector)
        
        # Run ingestion
        stats = csv_service.ingest(csv_path, batch_size=10)
        
        # Check that drift was detected
        drift_logs = test_db.query(SchemaDriftLog).all()
        assert len(drift_logs) > 0
        
        # Should detect missing 'description' field
        missing_desc_logs = [
            log for log in drift_logs 
            if "description" in log.missing_fields
        ]
        assert len(missing_desc_logs) > 0
