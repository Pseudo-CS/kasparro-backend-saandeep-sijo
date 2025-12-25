"""Script to initialize the database with sample data for testing."""
import asyncio
import logging
from pathlib import Path

from core.logging_config import setup_logging
from core.database import init_db, get_db
from ingestion.etl_orchestrator import run_etl_pipeline

logger = logging.getLogger(__name__)


async def main():
    """Initialize database and run initial ETL."""
    setup_logging()
    
    logger.info("Initializing database...")
    init_db()
    logger.info("Database initialized successfully")
    
    logger.info("Running initial ETL pipeline...")
    try:
        results = await run_etl_pipeline()
        
        logger.info("ETL Pipeline completed!")
        for source, result in results.items():
            if result and "error" not in result:
                logger.info(
                    f"  {source}: processed={result.get('processed', 0)}, "
                    f"inserted={result.get('inserted', 0)}, "
                    f"updated={result.get('updated', 0)}, "
                    f"failed={result.get('failed', 0)}"
                )
            else:
                logger.error(f"  {source}: FAILED")
    
    except Exception as e:
        logger.error(f"ETL pipeline failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())
