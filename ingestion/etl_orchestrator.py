"""ETL orchestrator to run all ingestion services."""
import asyncio
import logging
from typing import Dict, Any

from core.database import get_db
from core.config import settings
from services.checkpoint_service import CheckpointService
from ingestion.csv_ingestion import CSVIngestionService
from ingestion.api_ingestion import APIIngestionService
from ingestion.rss_ingestion import RSSIngestionService

logger = logging.getLogger(__name__)


class ETLOrchestrator:
    """Orchestrates ETL pipeline execution."""
    
    def __init__(self):
        self.results = {}
    
    async def run_all(self) -> Dict[str, Any]:
        """
        Run all ETL pipelines.
        
        Returns:
            Dictionary of results for each source
        """
        logger.info("Starting ETL orchestrator")
        
        results = {
            "csv": None,
            "api1": None,
            "rss": None,
            "api2": None
        }
        
        # Run CSV ingestion
        try:
            results["csv"] = await self.run_csv_ingestion()
        except Exception as e:
            logger.error(f"CSV ingestion failed: {e}")
            results["csv"] = {"error": str(e)}
        
        # Run API1 ingestion
        try:
            results["api1"] = await self.run_api_ingestion(
                settings.api_url_source_1,
                settings.api_key_source_1,
                "api1"
            )
        except Exception as e:
            logger.error(f"API1 ingestion failed: {e}")
            results["api1"] = {"error": str(e)}
        
        # Run API2 ingestion (if configured)
        if settings.api_url_source_2 and settings.api_key_source_2:
            try:
                results["api2"] = await self.run_api_ingestion(
                    settings.api_url_source_2,
                    settings.api_key_source_2,
                    "api2"
                )
            except Exception as e:
                logger.error(f"API2 ingestion failed: {e}")
                results["api2"] = {"error": str(e)}
        
        # Run RSS ingestion
        try:
            results["rss"] = await self.run_rss_ingestion()
        except Exception as e:
            logger.error(f"RSS ingestion failed: {e}")
            results["rss"] = {"error": str(e)}
        
        logger.info("ETL orchestrator completed")
        return results
    
    async def run_csv_ingestion(self) -> Dict[str, Any]:
        """Run CSV ingestion."""
        logger.info("Running CSV ingestion")
        
        with get_db() as db:
            checkpoint_service = CheckpointService(db)
            csv_service = CSVIngestionService(db, checkpoint_service)
            
            result = csv_service.ingest(settings.csv_source_path)
            return result
    
    async def run_api_ingestion(
        self,
        api_url: str,
        api_key: str,
        source_name: str
    ) -> Dict[str, Any]:
        """Run API ingestion."""
        logger.info(f"Running API ingestion for {source_name}")
        
        with get_db() as db:
            checkpoint_service = CheckpointService(db)
            api_service = APIIngestionService(
                db,
                checkpoint_service,
                api_url,
                api_key,
                source_name
            )
            
            result = await api_service.ingest()
            return result
    
    async def run_rss_ingestion(self) -> Dict[str, Any]:
        """Run RSS ingestion."""
        logger.info("Running RSS ingestion")
        
        with get_db() as db:
            checkpoint_service = CheckpointService(db)
            rss_service = RSSIngestionService(
                db,
                checkpoint_service,
                settings.rss_feed_url
            )
            
            result = rss_service.ingest()
            return result


async def run_etl_pipeline():
    """Entry point for running ETL pipeline."""
    orchestrator = ETLOrchestrator()
    results = await orchestrator.run_all()
    
    # Log summary
    logger.info("ETL Pipeline Results:")
    for source, result in results.items():
        if result and "error" not in result:
            logger.info(
                f"  {source}: processed={result.get('processed', 0)}, "
                f"inserted={result.get('inserted', 0)}, "
                f"updated={result.get('updated', 0)}, "
                f"failed={result.get('failed', 0)}"
            )
        else:
            logger.error(f"  {source}: FAILED - {result.get('error', 'Unknown error')}")
    
    return results


if __name__ == "__main__":
    from core.logging_config import setup_logging
    from core.database import init_db
    
    setup_logging()
    init_db()
    
    asyncio.run(run_etl_pipeline())
