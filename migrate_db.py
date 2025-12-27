"""Apply database schema migrations for identity unification and production constraints."""
import logging
from sqlalchemy import text, inspect
from core.database import engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns


def index_exists(index_name: str) -> bool:
    """Check if an index exists."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_indexes 
                WHERE indexname = :index_name
            )
        """), {"index_name": index_name})
        return result.scalar()


def apply_canonical_id_migration():
    """Add canonical_id column and index if they don't exist."""
    logger.info("Checking canonical_id migration...")
    
    if column_exists('normalized_data', 'canonical_id'):
        logger.info("  ✓ canonical_id column already exists")
    else:
        logger.info("  + Adding canonical_id column...")
        with engine.connect() as conn:
            conn.execute(text("""
                ALTER TABLE normalized_data 
                ADD COLUMN canonical_id VARCHAR(255)
            """))
            conn.commit()
        logger.info("  ✓ Added canonical_id column")
    
    if index_exists('idx_normalized_canonical_id'):
        logger.info("  ✓ canonical_id index already exists")
    else:
        logger.info("  + Creating canonical_id index...")
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE INDEX idx_normalized_canonical_id 
                ON normalized_data(canonical_id)
            """))
            conn.commit()
        logger.info("  ✓ Created canonical_id index")


def apply_production_constraints():
    """Apply production-grade constraints and indexes."""
    logger.info("Checking production constraints...")
    
    migrations = [
        # Composite index for entity queries
        ("idx_normalized_source_canonical", """
            CREATE INDEX IF NOT EXISTS idx_normalized_source_canonical 
            ON normalized_data(source_type, canonical_id)
        """),
        
        # Index for time-series queries
        ("idx_normalized_timestamp", """
            CREATE INDEX IF NOT EXISTS idx_normalized_timestamp 
            ON normalized_data(source_timestamp)
        """),
        
        # Checkpoint status index
        ("idx_checkpoint_status", """
            CREATE INDEX IF NOT EXISTS idx_checkpoint_status 
            ON etl_checkpoints(status)
        """),
        
        # Composite index for run history
        ("idx_run_history_source_started", """
            CREATE INDEX IF NOT EXISTS idx_run_history_source_started 
            ON etl_run_history(source_type, started_at)
        """),
        
        # Composite index for drift logs
        ("idx_drift_source_detected", """
            CREATE INDEX IF NOT EXISTS idx_drift_source_detected 
            ON schema_drift_logs(source_name, detected_at)
        """),
    ]
    
    with engine.connect() as conn:
        for index_name, sql in migrations:
            if index_exists(index_name):
                logger.info(f"  ✓ {index_name} already exists")
            else:
                logger.info(f"  + Creating {index_name}...")
                conn.execute(text(sql))
                conn.commit()
                logger.info(f"  ✓ Created {index_name}")


def main():
    """Apply all pending migrations."""
    logger.info("=" * 60)
    logger.info("Database Schema Migration")
    logger.info("=" * 60)
    
    try:
        # Ensure base tables exist
        logger.info("\n1. Ensuring base tables exist...")
        init_db()
        logger.info("  ✓ Base tables verified")
        
        # Apply canonical_id migration
        logger.info("\n2. Applying identity unification migration...")
        apply_canonical_id_migration()
        
        # Apply production constraints
        logger.info("\n3. Applying production constraints...")
        apply_production_constraints()
        
        logger.info("\n" + "=" * 60)
        logger.info("✓ All migrations applied successfully!")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"\n✗ Migration failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
