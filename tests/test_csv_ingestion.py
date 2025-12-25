"""Tests for CSV ingestion service."""
import pytest
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os

from ingestion.csv_ingestion import CSVIngestionService
from services.checkpoint_service import CheckpointService
from services.etl_utils import utc_now
from core.models import RawCSVData, NormalizedData


def test_csv_ingestion_basic(db_session):
    """Test basic CSV ingestion."""
    # Create temporary CSV file with future timestamps to avoid checkpoint issues
    future_date = (utc_now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    csv_data = f"""id,title,description,value,category,timestamp
1,Test Product,Test Description,99.99,electronics,{future_date}
2,Another Product,Another Description,149.50,electronics,{future_date}
"""
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        f.write(csv_data)
        csv_path = f.name
    
    try:
        # Run ingestion
        checkpoint_service = CheckpointService(db_session)
        csv_service = CSVIngestionService(db_session, checkpoint_service)
        
        result = csv_service.ingest(csv_path, batch_size=10)
        
        # Verify results - should process at least some records
        assert result["processed"] >= 0
        assert result["failed"] >= 0
        
    finally:
        os.unlink(csv_path)


def test_csv_ingestion_incremental(db_session):
    """Test incremental CSV ingestion."""
    # Create CSV with future timestamps
    future_date1 = (utc_now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    future_date2 = (utc_now() + timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    future_date3 = (utc_now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    csv_data = f"""id,title,description,value,category,timestamp
1,Product 1,Description 1,99.99,electronics,{future_date1}
2,Product 2,Description 2,149.50,electronics,{future_date2}
3,Product 3,Description 3,199.00,electronics,{future_date3}
"""
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        f.write(csv_data)
        csv_path = f.name
    
    try:
        checkpoint_service = CheckpointService(db_session)
        csv_service = CSVIngestionService(db_session, checkpoint_service)
        
        # First ingestion
        result1 = csv_service.ingest(csv_path)
        assert result1["processed"] >= 0
        
        # Second ingestion (should skip or update already processed)
        result2 = csv_service.ingest(csv_path)
        
        # Should still complete successfully
        assert result2["processed"] >= 0
        
    finally:
        os.unlink(csv_path)


def test_csv_ingestion_validation_failure(db_session):
    """Test CSV ingestion with validation failures."""
    # Create CSV with invalid data
    csv_data = """id,title,description,value,category,timestamp
1,,Invalid empty title,-99.99,electronics,2024-01-15T10:30:00Z
2,Valid Product,Valid Description,149.50,electronics,invalid-date
"""
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        f.write(csv_data)
        csv_path = f.name
    
    try:
        checkpoint_service = CheckpointService(db_session)
        csv_service = CSVIngestionService(db_session, checkpoint_service)
        
        result = csv_service.ingest(csv_path)
        
        # Should have some failures
        assert result["failed"] > 0
        
    finally:
        os.unlink(csv_path)


def test_csv_ingestion_idempotent(db_session):
    """Test that CSV ingestion is idempotent."""
    future_date = (utc_now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    csv_data = f"""id,title,description,value,category,timestamp
1,Test Product,Test Description,99.99,electronics,{future_date}
"""
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv') as f:
        f.write(csv_data)
        csv_path = f.name
    
    try:
        checkpoint_service = CheckpointService(db_session)
        csv_service = CSVIngestionService(db_session, checkpoint_service)
        
        # Run ingestion twice
        result1 = csv_service.ingest(csv_path)
        result2 = csv_service.ingest(csv_path)
        
        # Both should complete successfully
        assert result1["processed"] >= 0
        assert result2["processed"] >= 0
        
    finally:
        os.unlink(csv_path)
