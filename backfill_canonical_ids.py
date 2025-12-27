"""Backfill canonical_id for existing normalized data."""
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.models import NormalizedData
from services.identity_resolution import IdentityResolver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def backfill_canonical_ids():
    """
    Backfill canonical_id for all existing records in normalized_data table.
    
    This script resolves canonical identities for records that were ingested
    before the identity unification feature was added.
    """
    # Create database connection
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        # Initialize identity resolver
        resolver = IdentityResolver(db)
        
        # Get all records without canonical_id
        records = db.query(NormalizedData).filter(
            NormalizedData.canonical_id.is_(None)
        ).all()
        
        total_records = len(records)
        logger.info(f"Found {total_records} records without canonical_id")
        
        if total_records == 0:
            logger.info("All records already have canonical_id")
            return
        
        updated_count = 0
        
        for i, record in enumerate(records, 1):
            try:
                # Build data dict from extra_metadata
                data = record.extra_metadata or {}
                data['title'] = record.title
                
                # Resolve canonical identity
                canonical_id = resolver.resolve_canonical_id(
                    source_type=record.source_type,
                    title=record.title,
                    data=data
                )
                
                # Update record
                record.canonical_id = canonical_id
                updated_count += 1
                
                # Commit in batches
                if i % 100 == 0:
                    db.commit()
                    logger.info(f"Progress: {i}/{total_records} ({(i/total_records)*100:.1f}%)")
                
            except Exception as e:
                logger.error(f"Error processing record {record.id}: {e}")
                continue
        
        # Final commit
        db.commit()
        
        logger.info(f"✓ Successfully backfilled canonical_id for {updated_count}/{total_records} records")
        
        # Show some statistics
        canonical_count = db.query(NormalizedData.canonical_id).distinct().count()
        logger.info(f"✓ Total unique canonical identities: {canonical_count}")
        
        # Show examples of multi-source entities
        from sqlalchemy import func
        multi_source = db.query(
            NormalizedData.canonical_id,
            func.count(NormalizedData.id).label('source_count')
        ).filter(
            NormalizedData.canonical_id.isnot(None)
        ).group_by(
            NormalizedData.canonical_id
        ).having(
            func.count(NormalizedData.id) > 1
        ).order_by(
            func.count(NormalizedData.id).desc()
        ).limit(10).all()
        
        if multi_source:
            logger.info("\n✓ Top unified entities (present in multiple sources):")
            for canonical_id, count in multi_source:
                logger.info(f"  - {canonical_id}: {count} sources")
        
    except Exception as e:
        logger.error(f"Error during backfill: {e}", exc_info=True)
        db.rollback()
        raise
    
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting canonical_id backfill process...")
    backfill_canonical_ids()
    logger.info("Backfill process completed")
