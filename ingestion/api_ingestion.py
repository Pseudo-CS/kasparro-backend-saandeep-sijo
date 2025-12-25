"""API data ingestion service."""
import httpx
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import asyncio

from core.models import RawAPIData, NormalizedData
from schemas.data_schemas import APIRecordSchema, NormalizedDataSchema, SourceType
from services.etl_utils import generate_source_id, safe_parse_datetime, safe_float, RateLimiter
from services.checkpoint_service import CheckpointService
from services.schema_drift_service import SchemaDriftDetector
from services.failure_injection_service import FailureInjector
from services.retry_service import with_async_retry, RetryConfig, global_rate_limiter
from core.config import settings

logger = logging.getLogger(__name__)


class APIIngestionService:
    """Service for ingesting data from API sources."""
    
    def __init__(
        self,
        db: Session,
        checkpoint_service: CheckpointService,
        api_url: str,
        api_key: str,
        source_name: str = "api1",
        failure_injector: Optional[FailureInjector] = None
    ):
        self.db = db
        self.checkpoint_service = checkpoint_service
        self.api_url = api_url
        self.api_key = api_key
        self.source_name = source_name
        self.source_type = f"api_{source_name}"
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            settings.etl_rate_limit_calls,
            settings.etl_rate_limit_period
        )
        
        # Initialize schema drift detector
        self.drift_detector = SchemaDriftDetector(db, self.source_type)
        self._setup_expected_schema()
        
        # Initialize failure injector (P2.2)
        self.failure_injector = failure_injector or FailureInjector.from_env()
        
        # Configure per-source rate limiting (P2.3)
        global_rate_limiter.configure_source(
            self.source_type,
            settings.etl_rate_limit_calls,
            settings.etl_rate_limit_period
        )
        
        # Configure retry policy (P2.3)
        self.retry_config = RetryConfig(
            max_retries=3,
            initial_backoff=2.0,
            max_backoff=30.0,
            backoff_multiplier=2.0
        )
    
    def _setup_expected_schema(self):
        """Define expected API schema for drift detection."""
        expected_schema = {
            "id": str,
            "name": str,
            "symbol": str,
            "rank": int,
            "price_usd": float,
            "market_cap_usd": float,
            "volume_24h_usd": float,
            "percent_change_24h": float
        }
        self.drift_detector.set_expected_schema(expected_schema)
    
    async def ingest(self, batch_size: int = 100) -> dict:
        """
        Ingest data from API.
        
        Args:
            batch_size: Number of records to fetch per request
            
        Returns:
            Statistics dictionary
        """
        logger.info(f"Starting API ingestion from {self.api_url}")
        
        # Start ETL run
        run_id = self.checkpoint_service.start_run(
            self.source_type,
            metadata={"api_url": self.api_url, "source_name": self.source_name}
        )
        
        stats = {
            "processed": 0,
            "inserted": 0,
            "updated": 0,
            "failed": 0,
            "errors": []
        }
        
        try:
            # Get last processed timestamp for incremental loading
            last_timestamp = self.checkpoint_service.get_last_successful_timestamp(
                self.source_type
            )
            
            # Fetch data from API
            records = await self._fetch_data(last_timestamp)
            logger.info(f"Fetched {len(records)} records from API")
            
            # Process records
            for record_data in records:
                try:
                    record_stats = self._process_record(record_data)
                    stats["processed"] += record_stats["processed"]
                    stats["inserted"] += record_stats["inserted"]
                    stats["updated"] += record_stats["updated"]
                    stats["failed"] += record_stats["failed"]
                    
                except Exception as e:
                    logger.warning(f"Failed to process API record: {e}")
                    stats["failed"] += 1
                    stats["errors"].append(str(e))
            
            self.db.commit()
            
            # Complete run successfully
            self.checkpoint_service.complete_run(
                run_id,
                self.source_type,
                "success",
                records_processed=stats["processed"],
                records_inserted=stats["inserted"],
                records_updated=stats["updated"],
                records_failed=stats["failed"]
            )
            
            logger.info(f"API ingestion completed: {stats}")
            
        except Exception as e:
            logger.error(f"API ingestion failed: {e}")
            stats["errors"].append(str(e))
            
            # Mark run as failed
            self.checkpoint_service.complete_run(
                run_id,
                self.source_type,
                "failure",
                error_message=str(e)
            )
            raise
        
        return stats
    
    async def _fetch_data(self, last_timestamp: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch data from API with authentication and rate limiting.
        
        Args:
            last_timestamp: Last processed timestamp for incremental loading
            
        Returns:
            List of records
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        params = {}
        if last_timestamp:
            # Add timestamp filter for incremental loading
            params["since"] = last_timestamp.isoformat()
        
        all_records = []
        page = 1
        has_more = True
        
        async with httpx.AsyncClient() as client:
            while has_more:
                # Add pagination parameters
                params["page"] = page
                params["per_page"] = 100
                
                # Use retry decorator for API calls (P2.3)
                try:
                    records = await self._fetch_with_retry(client, params, headers)
                    all_records.extend(records)
                    
                    # Check for more pages (simple heuristic)
                    if len(records) == 0:
                        has_more = False
                    else:
                        has_more = False  # Single page for now
                    
                    page += 1
                    
                except httpx.HTTPStatusError as e:
                    logger.error(f"API request failed: {e}")
                    raise
                except Exception as e:
                    logger.error(f"Error fetching data: {e}")
                    raise
        
        return all_records
    
    @with_async_retry(
        config=RetryConfig(max_retries=3, initial_backoff=2.0),
        retryable_exceptions=(httpx.HTTPError, httpx.TimeoutException)
    )
    async def _fetch_with_retry(
        self, 
        client: httpx.AsyncClient, 
        params: dict, 
        headers: dict
    ) -> list:
        """Fetch data with retry and exponential backoff (P2.3)."""
        # Apply per-source rate limiting
        global_rate_limiter.wait_if_needed(self.source_type)
        
        response = await client.get(
            self.api_url,
            headers=headers,
            params=params,
            timeout=30.0
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Extract records (adjust based on API structure)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "data" in data:
            return data["data"]
        elif isinstance(data, dict) and "results" in data:
            return data["results"]
        else:
            return [data]
    
    def _process_record(self, raw_data: Dict[str, Any]) -> dict:
        """
        Process a single API record.
        
        Args:
            raw_data: Raw API record
            
        Returns:
            Processing statistics
        """
        stats = {
            "processed": 0,
            "inserted": 0,
            "updated": 0,
            "failed": 0
        }
        
        # Generate source ID
        source_id = generate_source_id(self.source_type, raw_data)
        
        # Validate with Pydantic
        record = APIRecordSchema(
            id=raw_data.get('id', source_id),
            name=raw_data.get('name', raw_data.get('title', '')),
            description=raw_data.get('description'),
            amount=safe_float(raw_data.get('amount', raw_data.get('value'))),
            type=raw_data.get('type', raw_data.get('category')),
            created_at=safe_parse_datetime(raw_data.get('created_at')),
            tags=raw_data.get('tags', [])
        )
        
        # Store raw data (idempotent - upsert)
        self._upsert_raw_data(source_id, raw_data)
        
        # Normalize and store
        normalized = self._normalize_record(source_id, record)
        is_new = self._upsert_normalized_data(normalized)
        
        if is_new:
            stats["inserted"] += 1
        else:
            stats["updated"] += 1
        
        stats["processed"] += 1
        return stats
    
    def _upsert_raw_data(self, source_id: str, raw_data: dict):
        """Store or update raw API data."""
        existing = self.db.query(RawAPIData).filter(
            RawAPIData.source_id == source_id
        ).first()
        
        if existing:
            existing.raw_data = raw_data
        else:
            raw_record = RawAPIData(
                source_id=source_id,
                source_name=self.source_name,
                raw_data=raw_data
            )
            self.db.add(raw_record)
    
    def _normalize_record(
        self,
        source_id: str,
        record: APIRecordSchema
    ) -> NormalizedDataSchema:
        """Normalize API record to unified schema."""
        return NormalizedDataSchema(
            source_type=SourceType.API1 if self.source_name == "api1" else SourceType.API2,
            source_id=source_id,
            title=record.name,
            description=record.description,
            value=record.amount,
            category=record.type,
            tags=record.tags,
            source_timestamp=record.created_at,
            metadata={"original_id": record.id, "source_name": self.source_name}
        )
    
    def _upsert_normalized_data(self, normalized: NormalizedDataSchema) -> bool:
        """
        Store or update normalized data.
        
        Returns:
            True if inserted, False if updated
        """
        existing = self.db.query(NormalizedData).filter(
            NormalizedData.source_id == normalized.source_id
        ).first()
        
        if existing:
            # Update existing record
            existing.title = normalized.title
            existing.description = normalized.description
            existing.value = normalized.value
            existing.category = normalized.category
            existing.tags = normalized.tags
            existing.source_timestamp = normalized.source_timestamp
            existing.extra_metadata = normalized.extra_metadata
            existing.updated_at = datetime.utcnow()
            return False
        else:
            # Insert new record
            new_record = NormalizedData(
                source_type=normalized.source_type.value,
                source_id=normalized.source_id,
                title=normalized.title,
                description=normalized.description,
                value=normalized.value,
                category=normalized.category,
                tags=normalized.tags,
                source_timestamp=normalized.source_timestamp,
                extra_metadata=normalized.extra_metadata
            )
            self.db.add(new_record)
            return True
