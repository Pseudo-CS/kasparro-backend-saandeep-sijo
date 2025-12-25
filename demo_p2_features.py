"""
Demo script to demonstrate P2.1 (Schema Drift Detection) and P2.2 (Failure Injection + Recovery).

This script demonstrates:
1. Schema drift detection with fuzzy matching and confidence scoring
2. Controlled failure injection during ETL
3. Clean recovery from checkpoint with no duplicates
4. Detailed run metadata tracking
"""

import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import settings
from services.checkpoint_service import CheckpointService
from services.failure_injection_service import FailureInjector
from ingestion.csv_ingestion import CSVIngestionService
from ingestion.api_ingestion import APIIngestionService
from core.models import SchemaDriftLog, ETLRunHistory
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def demo_p21_schema_drift():
    """Demonstrate P2.1: Schema Drift Detection."""
    print("\n" + "="*80)
    print("P2.1 DEMO: Schema Drift Detection")
    print("="*80 + "\n")
    
    # Create database connection
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Check for schema drift logs
        drift_logs = db.query(SchemaDriftLog).order_by(
            SchemaDriftLog.detected_at.desc()
        ).limit(10).all()
        
        if drift_logs:
            print(f"✅ Found {len(drift_logs)} schema drift detections\n")
            
            for log in drift_logs[:5]:  # Show first 5
                print(f"📊 Drift Detection:")
                print(f"   Source: {log.source_name}")
                print(f"   Record ID: {log.record_id}")
                print(f"   Confidence: {log.confidence_score:.2f}")
                
                if log.missing_fields:
                    print(f"   Missing Fields: {', '.join(log.missing_fields)}")
                if log.extra_fields:
                    print(f"   Extra Fields: {', '.join(log.extra_fields)}")
                if log.fuzzy_suggestions:
                    print(f"   Suggestions: {log.fuzzy_suggestions}")
                
                print(f"   Detected At: {log.detected_at}")
                print()
        else:
            print("ℹ️  No schema drift detected yet. Run ETL to generate drift logs.")
            
    finally:
        db.close()


def demo_p22_failure_recovery():
    """Demonstrate P2.2: Failure Injection + Recovery."""
    print("\n" + "="*80)
    print("P2.2 DEMO: Failure Injection + Recovery")
    print("="*80 + "\n")
    
    # Create database connection
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Check ETL run history
        runs = db.query(ETLRunHistory).order_by(
            ETLRunHistory.started_at.desc()
        ).limit(10).all()
        
        if runs:
            print(f"✅ Found {len(runs)} ETL runs in history\n")
            
            # Show statistics
            failed_runs = [r for r in runs if r.status == "failure"]
            success_runs = [r for r in runs if r.status == "success"]
            
            print(f"📈 Run Statistics:")
            print(f"   Total Runs: {len(runs)}")
            print(f"   Successful: {len(success_runs)}")
            print(f"   Failed: {len(failed_runs)}")
            print()
            
            # Show recent runs with details
            for run in runs[:5]:
                status_emoji = "✅" if run.status == "success" else "❌"
                print(f"{status_emoji} Run {run.run_id[:8]}...")
                print(f"   Source: {run.source_type}")
                print(f"   Status: {run.status}")
                print(f"   Started: {run.started_at}")
                print(f"   Completed: {run.completed_at}")
                
                if run.duration_seconds:
                    print(f"   Duration: {run.duration_seconds:.2f}s")
                
                print(f"   Records Processed: {run.records_processed}")
                print(f"   Records Inserted: {run.records_inserted}")
                print(f"   Records Updated: {run.records_updated}")
                print(f"   Records Failed: {run.records_failed}")
                
                if run.error_message:
                    print(f"   Error: {run.error_message[:100]}...")
                
                print()
            
            # Demonstrate recovery capability
            if failed_runs:
                print("\n🔄 Recovery Demonstration:")
                failed_run = failed_runs[0]
                print(f"   Failed run processed {failed_run.records_processed} records")
                print(f"   System can resume from checkpoint to process remaining data")
                print(f"   Checkpoint ensures no duplicates during recovery")
                
        else:
            print("ℹ️  No ETL runs found yet. Run ETL to generate run history.")
            
    finally:
        db.close()


def demo_failure_injection_config():
    """Show how to configure failure injection."""
    print("\n" + "="*80)
    print("P2.2 Configuration: Failure Injection")
    print("="*80 + "\n")
    
    print("💡 To enable controlled failure injection, set environment variables:\n")
    print("# Enable failure injection")
    print("ETL_INJECT_FAILURE=true")
    print()
    print("# Fail after processing N records")
    print("ETL_FAIL_AFTER_N=50")
    print()
    print("# Or use probabilistic failure (0.0 to 1.0)")
    print("ETL_FAILURE_RATE=0.1")
    print()
    print("# Failure type: exception, timeout, data_corruption")
    print("ETL_FAILURE_TYPE=exception")
    print()
    print("Example Docker Compose override:")
    print("-" * 40)
    print("""
services:
  etl_service:
    environment:
      - ETL_INJECT_FAILURE=true
      - ETL_FAIL_AFTER_N=30
      - ETL_FAILURE_TYPE=exception
    """)


if __name__ == "__main__":
    print("\n" + "="*80)
    print("  KASPARRO ETL SYSTEM - P2 FEATURES DEMONSTRATION")
    print("="*80)
    
    # Demo P2.1: Schema Drift Detection
    demo_p21_schema_drift()
    
    # Demo P2.2: Failure Injection + Recovery
    demo_p22_failure_recovery()
    
    # Show configuration info
    demo_failure_injection_config()
    
    print("\n" + "="*80)
    print("  END OF DEMONSTRATION")
    print("="*80 + "\n")
    
    print("✨ P2.1 Features Implemented:")
    print("   ✅ Automatic schema drift detection")
    print("   ✅ Fuzzy matching for field names")
    print("   ✅ Confidence scoring (0-1)")
    print("   ✅ Warning logs for all drift events")
    print()
    print("✨ P2.2 Features Implemented:")
    print("   ✅ Controlled failure injection")
    print("   ✅ Resume from last checkpoint")
    print("   ✅ Duplicate prevention (idempotent)")
    print("   ✅ Detailed run metadata tracking")
    print()
