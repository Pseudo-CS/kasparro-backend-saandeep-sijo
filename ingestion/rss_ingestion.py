"""RSS feed ingestion service."""
import feedparser
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from core.models import RawRSSData, NormalizedData
from schemas.data_schemas import RSSRecordSchema, NormalizedDataSchema, SourceType
from services.etl_utils import generate_source_id, safe_parse_datetime
from services.checkpoint_service import CheckpointService
from services.schema_drift_service import SchemaDriftDetector
from services.failure_injection_service import FailureInjector

logger = logging.getLogger(__name__)


class RSSIngestionService:
    """Service for ingesting data from RSS feeds."""
    
    def __init__(
        self, 
        db: Session, 
        checkpoint_service: CheckpointService, 
        feed_url: str,
        failure_injector: Optional[FailureInjector] = None
    ):
        self.db = db
        self.checkpoint_service = checkpoint_service
        self.feed_url = feed_url
        self.source_type = SourceType.RSS.value
        
        # Initialize schema drift detector
        self.drift_detector = SchemaDriftDetector(db, self.source_type)
        self._setup_expected_schema()
        
        # Initialize failure injector (P2.2)
        self.failure_injector = failure_injector or FailureInjector.from_env()
    
    def _setup_expected_schema(self):
        """Define expected RSS schema for drift detection."""
        expected_schema = {
            "title": str,
            "link": str,
            "published": str,
            "summary": str,
            "id": str
        }
        self.drift_detector.set_expected_schema(expected_schema)
    
    def ingest(self) -> dict:
        """
        Ingest data from RSS feed.
        
        Returns:
            Statistics dictionary
        """
        logger.info(f"Starting RSS ingestion from {self.feed_url}")
        
        # Start ETL run
        run_id = self.checkpoint_service.start_run(
            self.source_type,
            metadata={"feed_url": self.feed_url}
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
            
            # Parse RSS feed
            feed = feedparser.parse(self.feed_url)
            
            if feed.bozo:
                logger.warning(f"RSS feed has errors: {feed.bozo_exception}")
            
            logger.info(f"Fetched {len(feed.entries)} entries from RSS feed")
            
            # Process each entry
            for entry in feed.entries:
                try:
                    # Check if should process (incremental)
                    entry_date = self._get_entry_date(entry)
                    if last_timestamp and entry_date:
                        if entry_date <= last_timestamp:
                            continue  # Skip already processed
                    
                    record_stats = self._process_entry(entry)
                    stats["processed"] += record_stats["processed"]
                    stats["inserted"] += record_stats["inserted"]
                    stats["updated"] += record_stats["updated"]
                    stats["failed"] += record_stats["failed"]
                    
                except Exception as e:
                    logger.warning(f"Failed to process RSS entry: {e}")
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
            
            logger.info(f"RSS ingestion completed: {stats}")
            
        except Exception as e:
            logger.error(f"RSS ingestion failed: {e}")
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
    
    def _get_entry_date(self, entry) -> Optional[datetime]:
        """Extract date from RSS entry."""
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            from time import mktime
            return datetime.fromtimestamp(mktime(entry.published_parsed))
        elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
            from time import mktime
            return datetime.fromtimestamp(mktime(entry.updated_parsed))
        return None
    
    def _process_entry(self, entry) -> dict:
        """
        Process a single RSS entry.
        
        Args:
            entry: RSS feed entry
            
        Returns:
            Processing statistics
        """
        stats = {
            "processed": 0,
            "inserted": 0,
            "updated": 0,
            "failed": 0
        }
        
        # Extract data from entry
        raw_data = {
            "id": getattr(entry, 'id', getattr(entry, 'link', '')),
            "title": getattr(entry, 'title', ''),
            "summary": getattr(entry, 'summary', getattr(entry, 'description', '')),
            "link": getattr(entry, 'link', ''),
            "published": self._get_entry_date(entry),
            "categories": [tag.term for tag in getattr(entry, 'tags', [])]
        }
        
        # Generate source ID
        source_id = generate_source_id(self.source_type, raw_data)
        
        # Validate with Pydantic
        record = RSSRecordSchema(
            id=source_id,
            title=raw_data['title'],
            summary=raw_data['summary'],
            link=raw_data['link'],
            published=raw_data['published'],
            categories=raw_data['categories']
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
        """Store or update raw RSS data."""
        # Convert datetime to ISO format for JSON storage
        if raw_data.get('published'):
            raw_data['published'] = raw_data['published'].isoformat()
        
        existing = self.db.query(RawRSSData).filter(
            RawRSSData.source_id == source_id
        ).first()
        
        if existing:
            existing.raw_data = raw_data
        else:
            raw_record = RawRSSData(
                source_id=source_id,
                raw_data=raw_data
            )
            self.db.add(raw_record)
    
    def _normalize_record(
        self,
        source_id: str,
        record: RSSRecordSchema
    ) -> NormalizedDataSchema:
        """Normalize RSS record to unified schema."""
        return NormalizedDataSchema(
            source_type=SourceType.RSS,
            source_id=source_id,
            title=record.title,
            description=record.summary,
            value=None,  # RSS feeds typically don't have numeric values
            category=record.categories[0] if record.categories else None,
            tags=record.categories,
            source_timestamp=record.published,
            metadata={"link": record.link}
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
