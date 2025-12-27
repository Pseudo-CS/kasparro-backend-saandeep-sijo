"""Comprehensive test script for identity unification feature."""
import logging
import sys
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


def test_identity_resolution():
    """Test the identity resolver."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 1: Identity Resolution Logic")
    logger.info("=" * 60)
    
    try:
        from services.identity_resolution import IdentityResolver
        from core.database import get_db_session
        
        db = next(get_db_session())
        resolver = IdentityResolver(db)
        
        tests = [
            ("CSV ID extraction", "csv", "Bitcoin", {"id": "btc-bitcoin"}, "bitcoin"),
            ("Symbol matching", "api_api1", "Bitcoin", {"symbol": "BTC"}, "bitcoin"),
            ("Title normalization", "rss", "Ethereum News", {}, "ethereum-news"),
            ("Ethereum symbol", "api_api1", "Ethereum", {"symbol": "ETH"}, "ethereum"),
            ("Solana CSV ID", "csv", "Solana", {"id": "sol-solana"}, "solana"),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, source_type, title, data, expected in tests:
            result = resolver.resolve_canonical_id(source_type, title, data)
            if result == expected:
                logger.info(f"  ✓ {test_name}: '{result}'")
                passed += 1
            else:
                logger.error(f"  ✗ {test_name}: got '{result}', expected '{expected}'")
                failed += 1
        
        logger.info(f"\nResults: {passed} passed, {failed} failed")
        return failed == 0
        
    except Exception as e:
        logger.error(f"  ✗ Identity resolution test failed: {e}", exc_info=True)
        return False


def test_database_schema():
    """Test that database schema has canonical_id."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Database Schema")
    logger.info("=" * 60)
    
    try:
        from core.database import engine
        from sqlalchemy import inspect
        
        inspector = inspect(engine)
        
        # Check normalized_data columns
        columns = {col['name']: col for col in inspector.get_columns('normalized_data')}
        
        required_columns = ['canonical_id', 'source_type', 'source_id', 'title']
        for col_name in required_columns:
            if col_name in columns:
                logger.info(f"  ✓ Column '{col_name}' exists")
            else:
                logger.error(f"  ✗ Column '{col_name}' missing!")
                return False
        
        # Check indexes
        indexes = {idx['name'] for idx in inspector.get_indexes('normalized_data')}
        
        required_indexes = [
            'idx_normalized_canonical_id',
            'idx_normalized_source_canonical',
            'idx_normalized_timestamp'
        ]
        
        for idx_name in required_indexes:
            if idx_name in indexes:
                logger.info(f"  ✓ Index '{idx_name}' exists")
            else:
                logger.error(f"  ✗ Index '{idx_name}' missing!")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Schema test failed: {e}", exc_info=True)
        return False


def test_ingestion_with_identity():
    """Test that ingestion assigns canonical IDs."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Ingestion with Identity Unification")
    logger.info("=" * 60)
    
    try:
        from core.database import get_db_session, engine
        from ingestion.csv_ingestion import CSVIngestionService
        from services.checkpoint_service import CheckpointService
        
        db = next(get_db_session())
        checkpoint_service = CheckpointService(db)
        csv_service = CSVIngestionService(db, checkpoint_service)
        
        # Test CSV ingestion
        logger.info("  Testing CSV ingestion...")
        result = csv_service.ingest("./data/sample_data.csv")
        
        if "error" in result:
            logger.error(f"  ✗ CSV ingestion failed: {result['error']}")
            return False
        
        logger.info(f"  ✓ CSV ingestion: {result['processed']} processed, {result['inserted']} inserted")
        
        # Check if canonical IDs were assigned
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) as total,
                       COUNT(canonical_id) as with_canonical_id
                FROM normalized_data
                WHERE source_type = 'csv'
            """))
            row = result.fetchone()
            
            if row[0] > 0:
                logger.info(f"  ✓ Found {row[0]} CSV records")
                if row[1] > 0:
                    logger.info(f"  ✓ {row[1]} records have canonical_id ({row[1]/row[0]*100:.0f}%)")
                else:
                    logger.error(f"  ✗ No records have canonical_id!")
                    return False
            else:
                logger.error(f"  ✗ No CSV records found!")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Ingestion test failed: {e}", exc_info=True)
        return False


def test_identity_queries():
    """Test querying by canonical ID."""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Identity-Based Queries")
    logger.info("=" * 60)
    
    try:
        from core.database import get_db_session
        from core.models import NormalizedData
        
        db = next(get_db_session())
        
        # Try to find Bitcoin records
        bitcoin_records = db.query(NormalizedData).filter(
            NormalizedData.canonical_id == 'bitcoin'
        ).all()
        
        if bitcoin_records:
            logger.info(f"  ✓ Found {len(bitcoin_records)} Bitcoin record(s)")
            for rec in bitcoin_records:
                logger.info(f"    - {rec.source_type}: {rec.title}")
        else:
            logger.info(f"  ℹ No Bitcoin records found (may be expected if not in test data)")
        
        # Count unique canonical IDs
        unique_canonical = db.query(NormalizedData.canonical_id).distinct().filter(
            NormalizedData.canonical_id.isnot(None)
        ).count()
        
        logger.info(f"  ✓ Found {unique_canonical} unique canonical identities")
        
        # Find entities in multiple sources
        from sqlalchemy import func
        multi_source = db.query(
            NormalizedData.canonical_id,
            func.count(NormalizedData.id).label('count')
        ).filter(
            NormalizedData.canonical_id.isnot(None)
        ).group_by(
            NormalizedData.canonical_id
        ).having(
            func.count(NormalizedData.id) > 1
        ).all()
        
        if multi_source:
            logger.info(f"  ✓ Found {len(multi_source)} entities in multiple sources:")
            for canonical_id, count in multi_source[:5]:
                logger.info(f"    - {canonical_id}: {count} sources")
        else:
            logger.info(f"  ℹ No multi-source entities found yet")
        
        return True
        
    except Exception as e:
        logger.error(f"  ✗ Query test failed: {e}", exc_info=True)
        return False


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 70)
    logger.info(" IDENTITY UNIFICATION - COMPREHENSIVE TEST SUITE")
    logger.info("=" * 70)
    
    tests = [
        ("Identity Resolution", test_identity_resolution),
        ("Database Schema", test_database_schema),
        ("Ingestion with Identity", test_ingestion_with_identity),
        ("Identity Queries", test_identity_queries),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            logger.error(f"\n✗ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info(" TEST SUMMARY")
    logger.info("=" * 70)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"  {status}: {test_name}")
    
    logger.info("\n" + "=" * 70)
    if passed_count == total_count:
        logger.info(f"✓ ALL TESTS PASSED ({passed_count}/{total_count})")
        logger.info("=" * 70)
        logger.info("\n🎉 Identity unification is ready for production!")
        return 0
    else:
        logger.error(f"✗ SOME TESTS FAILED ({passed_count}/{total_count} passed)")
        logger.error("=" * 70)
        logger.error("\n❌ Please fix failing tests before pushing to repo")
        return 1


if __name__ == "__main__":
    sys.exit(main())
