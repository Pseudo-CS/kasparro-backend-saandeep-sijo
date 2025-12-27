"""
Manual migration runner for production environments.
Can be executed directly or via Render shell.

Usage:
    python run_migration_manual.py
"""
import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Run database migrations manually."""
    print("=" * 60)
    print("Identity Unification Migration")
    print("=" * 60)
    print()
    
    try:
        # Import and run migration
        from migrate_db import main as run_migration
        
        logger.info("Starting migration...")
        run_migration()
        
        print()
        print("=" * 60)
        print("✓ Migration completed successfully!")
        print("=" * 60)
        print()
        print("Changes applied:")
        print("  • canonical_id column added to normalized_data")
        print("  • Identity resolution indexes created")
        print("  • Production-grade constraints applied")
        print()
        print("Next steps:")
        print("  1. Restart your ETL service")
        print("  2. Verify canonical_id population in logs")
        print("  3. Test identity queries")
        print()
        
        return 0
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        print()
        print("=" * 60)
        print("✗ Migration failed!")
        print("=" * 60)
        print()
        print(f"Error: {e}")
        print()
        print("Troubleshooting:")
        print("  1. Check database connection")
        print("  2. Verify DATABASE_URL environment variable")
        print("  3. Ensure database user has ALTER TABLE permissions")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
