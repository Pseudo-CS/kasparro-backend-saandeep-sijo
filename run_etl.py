"""Manual ETL trigger script."""
import asyncio
import logging
import sys

from core.logging_config import setup_logging
from ingestion.etl_orchestrator import run_etl_pipeline

logger = logging.getLogger(__name__)


async def main():
    """Manually trigger ETL pipeline."""
    setup_logging()
    
    logger.info("=" * 80)
    logger.info("MANUAL ETL TRIGGER")
    logger.info("=" * 80)
    
    try:
        results = await run_etl_pipeline()
        
        logger.info("=" * 80)
        logger.info("ETL PIPELINE RESULTS")
        logger.info("=" * 80)
        
        success_count = 0
        fail_count = 0
        
        for source, result in results.items():
            if result and "error" not in result:
                logger.info(f"\n✓ {source.upper()}")
                logger.info(f"  Processed: {result.get('processed', 0)}")
                logger.info(f"  Inserted:  {result.get('inserted', 0)}")
                logger.info(f"  Updated:   {result.get('updated', 0)}")
                logger.info(f"  Failed:    {result.get('failed', 0)}")
                success_count += 1
            else:
                logger.error(f"\n✗ {source.upper()}: FAILED")
                if result and "error" in result:
                    logger.error(f"  Error: {result['error']}")
                fail_count += 1
        
        logger.info("\n" + "=" * 80)
        logger.info(f"SUMMARY: {success_count} succeeded, {fail_count} failed")
        logger.info("=" * 80)
        
        if fail_count > 0:
            sys.exit(1)
    
    except Exception as e:
        logger.error(f"ETL pipeline failed with exception: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
