># Identity Unification Architecture

## Overview

The **Identity Unification** system resolves canonical identities for entities across multiple data sources. When the same real-world entity (e.g., "Bitcoin") appears in CSV files, API responses, and RSS feeds, the system recognizes these as the same entity and assigns them a unified canonical ID.

## Problem Solved

**Before:** Each data source created separate records for the same entity:
- CSV record: `csv_btc-bitcoin` → "Bitcoin"
- API record: `api_api1_12345` → "Bitcoin (BTC)"
- RSS record: `rss_abc123` → "Bitcoin News"

**After:** All three records share a canonical identity:
- All three records → `canonical_id: "bitcoin"`
- Query `/entities/bitcoin` returns records from all 3 sources

## Architecture Components

### 1. Database Schema

#### NormalizedData Model
```python
class NormalizedData(Base):
    id = Column(Integer, primary_key=True)
    source_type = Column(String, index=True)  # csv, api_*, rss
    source_id = Column(String, unique=True)    # Source-specific ID
    canonical_id = Column(String, index=True)  # ✨ Unified identity
    title = Column(String)
    # ... other fields
```

**Key Fields:**
- `source_id`: Unique per source (e.g., `csv_btc-bitcoin`)
- `canonical_id`: Unified across sources (e.g., `bitcoin`)

### 2. Identity Resolution Service

**File:** `services/identity_resolution.py`

The `IdentityResolver` class implements multiple matching strategies:

#### Strategy 1: CSV ID Extraction
- **Pattern:** `{symbol}-{name}` (e.g., `btc-bitcoin`)
- **Action:** Extracts canonical name from hyphenated ID
- **Example:** `eth-ethereum` → `ethereum`

#### Strategy 2: Cryptocurrency Symbol Matching
- **Maintains:** Dictionary of 50+ crypto symbols → canonical names
- **Matches:** Symbol fields (`symbol`, `ticker`, `coin_symbol`)
- **Example:** API record with `"symbol": "BTC"` → `bitcoin`

#### Strategy 3: Title/Name Matching
- **Pattern matching:** Recognizes crypto names in titles
- **Symbol extraction:** Extracts symbols from patterns like "Bitcoin (BTC)"
- **Example:** "Ethereum (ETH) Price" → `ethereum`

#### Strategy 4: URL-Based Matching
- **RSS feeds:** Extracts identifiers from URLs
- **Pattern:** `/coins/{symbol}/` or `/coin/{symbol}/`
- **Example:** `cointelegraph.com/news/bitcoin-...` → `bitcoin`

#### Strategy 5: Title Normalization (Fallback)
- **Normalizes:** Lowercase, remove special chars, hyphenate
- **Example:** "Bitcoin News Today" → `bitcoin-news-today`

### 3. Ingestion Integration

All three ingestion services (`csv_ingestion.py`, `api_ingestion.py`, `rss_ingestion.py`) integrate identity resolution:

```python
# In each ingestion service:
def _normalize_record(self, source_id, record, raw_data):
    # Resolve canonical identity
    canonical_id = self.identity_resolver.resolve_canonical_id(
        source_type=self.source_type,
        title=record.title,
        data=raw_data
    )
    
    return NormalizedDataSchema(
        source_id=source_id,
        canonical_id=canonical_id,  # ✨ Unified identity
        title=record.title,
        # ... other fields
    )
```

### 4. API Endpoints

#### GET /data
Enhanced with canonical_id filtering:
```bash
# Get all Bitcoin records across sources
curl "http://localhost:8000/data?canonical_id=bitcoin"
```

#### GET /entities/{canonical_id}
New endpoint for entity-centric queries:
```bash
# Get all source records for Bitcoin
curl "http://localhost:8000/entities/bitcoin"

# Returns:
{
  "data": [
    {
      "source_type": "csv",
      "source_id": "csv_btc-bitcoin",
      "canonical_id": "bitcoin",
      "title": "Bitcoin",
      "value": 45000.50
    },
    {
      "source_type": "api_api1",
      "source_id": "api_api1_12345",
      "canonical_id": "bitcoin",
      "title": "Bitcoin (BTC)",
      "value": 45123.75
    },
    {
      "source_type": "rss",
      "source_id": "rss_abc123",
      "canonical_id": "bitcoin",
      "title": "Bitcoin Price Surges",
      "description": "..."
    }
  ]
}
```

## Migration & Deployment

### 1. Database Migration
```bash
# Apply migration to add canonical_id column
alembic upgrade head
```

### 2. Backfill Existing Data
```bash
# Resolve canonical IDs for historical records
python backfill_canonical_ids.py
```

**Output:**
```
Found 140 records without canonical_id
Progress: 100/140 (71.4%)
✓ Successfully backfilled canonical_id for 140/140 records
✓ Total unique canonical identities: 45

✓ Top unified entities (present in multiple sources):
  - bitcoin: 3 sources
  - ethereum: 3 sources
  - solana: 2 sources
```

### 3. New Data Ingestion
Future ETL runs automatically assign canonical IDs to new records.

## Benefits

### 1. Unified Entity View
Query a single endpoint to get all data about an entity from all sources.

### 2. Data Consolidation
Understand which entities appear across multiple data sources.

### 3. Analytics & Insights
- **Cross-source validation:** Compare values across sources
- **Data completeness:** Identify which sources provide which data
- **Source reliability:** Compare freshness and accuracy

### 4. Deduplication Awareness
While records remain separate (preserving source-specific data), the system tracks which records refer to the same entity.

## Example Use Cases

### Use Case 1: Price Comparison
```python
# Get Bitcoin prices from all sources
GET /entities/bitcoin

# Compare:
# - CSV: Historical reference price
# - API: Real-time market price
# - RSS: News-mentioned price
```

### Use Case 2: Data Enrichment
```python
# Combine data from multiple sources:
# - CSV provides: category, static metadata
# - API provides: real-time value, market data
# - RSS provides: news, sentiment, updates
```

### Use Case 3: Source Coverage Analysis
```sql
-- Find entities present in multiple sources
SELECT canonical_id, COUNT(DISTINCT source_type) as source_count
FROM normalized_data
WHERE canonical_id IS NOT NULL
GROUP BY canonical_id
HAVING COUNT(DISTINCT source_type) > 1;
```

## Configuration & Extension

### Adding New Crypto Symbols
Edit `services/identity_resolution.py`:
```python
self.crypto_symbols = {
    'btc': 'bitcoin',
    'eth': 'ethereum',
    # Add new mappings:
    'arb': 'arbitrum',
    'op': 'optimism',
}
```

### Custom Matching Strategies
Extend `IdentityResolver._match_cryptocurrency()` or add new strategies:
```python
def _match_custom_domain(self, title, data):
    """Custom matching logic for your domain."""
    # Implement domain-specific matching
    pass
```

### Identity Override
For manual corrections:
```sql
-- Override automatic resolution
UPDATE normalized_data 
SET canonical_id = 'corrected-identity'
WHERE source_id = 'specific-source-id';
```

## Monitoring & Validation

### Check Identity Distribution
```sql
-- Count records per canonical ID
SELECT canonical_id, COUNT(*) as record_count
FROM normalized_data
GROUP BY canonical_id
ORDER BY record_count DESC
LIMIT 20;
```

### Identify Unresolved Entities
```sql
-- Find records without canonical ID
SELECT source_type, COUNT(*) 
FROM normalized_data 
WHERE canonical_id IS NULL
GROUP BY source_type;
```

### Multi-Source Entities
```bash
# API endpoint to check unified entities
curl "http://localhost:8000/stats" | jq '.unified_entities'
```

## Testing

### Unit Tests
```python
def test_identity_resolution():
    resolver = IdentityResolver(db)
    
    # Test CSV ID extraction
    assert resolver.resolve_canonical_id(
        "csv", "Bitcoin", {"id": "btc-bitcoin"}
    ) == "bitcoin"
    
    # Test symbol matching
    assert resolver.resolve_canonical_id(
        "api_api1", "Bitcoin (BTC)", {"symbol": "BTC"}
    ) == "bitcoin"
```

### Integration Tests
```bash
# Ingest data and verify canonical IDs
python run_etl.py
curl "http://localhost:8000/entities/bitcoin" | jq '.data | length'
# Should return: 3 (CSV + API + RSS)
```

## Performance Considerations

- **Index:** `canonical_id` is indexed for fast filtering
- **Resolution:** Happens once during ingestion (not on query)
- **Memory:** Symbol dictionary loaded once per service instance
- **Scalability:** O(1) hash lookups for symbol matching

## Future Enhancements

1. **ML-based matching:** Use embeddings for fuzzy matching
2. **User feedback:** Allow manual corrections via API
3. **Confidence scores:** Track matching confidence levels
4. **Conflict resolution:** Handle cases where sources disagree
5. **Entity metadata:** Store additional canonical entity information

## Summary

Identity Unification transforms the ETL system from a **source-centric** to an **entity-centric** architecture, enabling:
- Cross-source entity queries
- Data consolidation and validation
- Richer analytics and insights
- Better data understanding

All while preserving source-specific records and maintaining data lineage.
