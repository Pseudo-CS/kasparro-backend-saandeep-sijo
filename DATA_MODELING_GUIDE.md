# Production-Grade Data Modeling & Normalization

## Overview

This document describes the production-grade data modeling practices implemented in the ETL backend service, focusing on proper normalization, constraints, indexing, and data integrity.

## Database Normalization

### Normal Forms Achieved

#### 1NF (First Normal Form) ✓
- **Atomic Values:** All columns contain atomic (indivisible) values
- **No Repeating Groups:** Tags and metadata stored as JSON (acceptable for flexibility)
- **Primary Keys:** Every table has a unique primary key

#### 2NF (Second Normal Form) ✓
- **Full Functional Dependency:** All non-key attributes depend on the entire primary key
- **No Partial Dependencies:** Each table serves a single purpose

#### 3NF (Third Normal Form) ✓
- **Transitive Dependency Elimination:** Non-key attributes don't depend on other non-key attributes
- **Separation of Concerns:** Raw data, normalized data, checkpoints, and logs are separate

## Schema Design

### 1. Raw Data Tables (Stage 1)

#### Purpose
Store unmodified source data for:
- **Audit trail:** Complete historical record
- **Reprocessing:** Ability to re-normalize with updated logic
- **Debugging:** Troubleshoot data quality issues

#### Tables

**raw_csv_data**
```sql
CREATE TABLE raw_csv_data (
    id INTEGER PRIMARY KEY,
    source_id VARCHAR(255) NOT NULL UNIQUE,  -- Natural key from source
    raw_data JSON NOT NULL,                  -- Complete row data
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_raw_csv_ingested_at ON raw_csv_data(ingested_at);
```

**raw_api_data**
```sql
CREATE TABLE raw_api_data (
    id INTEGER PRIMARY KEY,
    source_id VARCHAR(255) NOT NULL UNIQUE,
    source_name VARCHAR(50) NOT NULL,        -- API identifier
    raw_data JSON NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_raw_api_source_ingested ON raw_api_data(source_name, ingested_at);
```

**raw_rss_data**
```sql
CREATE TABLE raw_rss_data (
    id INTEGER PRIMARY KEY,
    source_id VARCHAR(500) NOT NULL UNIQUE,  -- Longer for URLs
    raw_data JSON NOT NULL,
    ingested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_raw_rss_ingested_at ON raw_rss_data(ingested_at);
```

### 2. Normalized Data Table (Stage 2)

#### Purpose
Unified, cleaned, standardized data ready for consumption:
- **Schema Consistency:** Common structure across sources
- **Data Quality:** Validated and type-checked
- **Query Performance:** Indexed for fast retrieval

#### Table

**normalized_data**
```sql
CREATE TABLE normalized_data (
    id INTEGER PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,          -- Dimension: data source
    source_id VARCHAR(255) NOT NULL UNIQUE,    -- Natural key
    canonical_id VARCHAR(255),                 -- Identity unification
    
    -- Business data
    title VARCHAR(500) NOT NULL,
    description TEXT,
    value FLOAT,
    category VARCHAR(100),
    tags JSON,
    
    -- Temporal data
    source_timestamp TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    
    -- Extensibility
    extra_metadata JSON
);

-- Single-column indexes
CREATE INDEX idx_normalized_source_type ON normalized_data(source_type);
CREATE INDEX idx_normalized_created_at ON normalized_data(created_at);
CREATE INDEX idx_normalized_category ON normalized_data(category);
CREATE INDEX idx_normalized_canonical_id ON normalized_data(canonical_id);
CREATE INDEX idx_normalized_timestamp ON normalized_data(source_timestamp);

-- Composite indexes for common queries
CREATE INDEX idx_normalized_source_canonical ON normalized_data(source_type, canonical_id);
```

### 3. ETL Metadata Tables

#### etl_checkpoints
Tracks incremental ingestion state per source:

```sql
CREATE TABLE etl_checkpoints (
    id INTEGER PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL UNIQUE,   -- One row per source
    last_processed_id VARCHAR(255),
    last_processed_timestamp TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    last_failure_at TIMESTAMP WITH TIME ZONE,
    records_processed INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL,               -- success, failure, running
    error_message TEXT,
    extra_metadata JSON
);

CREATE INDEX idx_checkpoint_source_type ON etl_checkpoints(source_type);
CREATE INDEX idx_checkpoint_status ON etl_checkpoints(status);
```

#### etl_run_history
Historical log of all ETL executions:

```sql
CREATE TABLE etl_run_history (
    id INTEGER PRIMARY KEY,
    run_id VARCHAR(100) NOT NULL UNIQUE,       -- UUID per run
    source_type VARCHAR(50) NOT NULL,
    
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds FLOAT,
    
    records_processed INTEGER NOT NULL DEFAULT 0,
    records_inserted INTEGER NOT NULL DEFAULT 0,
    records_updated INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,
    
    status VARCHAR(20) NOT NULL,
    error_message TEXT,
    extra_metadata JSON
);

CREATE INDEX idx_run_history_started_at ON etl_run_history(started_at);
CREATE INDEX idx_run_history_status ON etl_run_history(status);
CREATE INDEX idx_run_history_source_started ON etl_run_history(source_type, started_at);
```

### 4. Data Quality Tables

#### schema_drift_logs
Tracks data quality and schema changes:

```sql
CREATE TABLE schema_drift_logs (
    id INTEGER PRIMARY KEY,
    source_name VARCHAR(50) NOT NULL,
    record_id VARCHAR(255) NOT NULL,
    confidence_score FLOAT NOT NULL,           -- 0.0 to 1.0
    
    missing_fields JSON,
    extra_fields JSON,
    type_mismatches JSON,
    fuzzy_suggestions JSON,
    
    detected_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_drift_detected_at ON schema_drift_logs(detected_at);
CREATE INDEX idx_drift_source_name ON schema_drift_logs(source_name);
CREATE INDEX idx_drift_source_detected ON schema_drift_logs(source_name, detected_at);
```

## Production-Grade Constraints

### String Length Constraints

**Why:** Prevent unbounded storage growth and define data expectations

| Column Type | Max Length | Rationale |
|-------------|------------|-----------|
| source_type | 50 | Fixed vocabulary (csv, api1, api2, rss) |
| source_id | 255 | Standard identifier length |
| source_id (RSS) | 500 | URLs can be longer |
| title | 500 | Reasonable title length |
| category | 100 | Category names are typically short |
| run_id | 100 | UUID + prefix |
| status | 20 | Fixed vocabulary |
| canonical_id | 255 | Normalized identifiers |

### NOT NULL Constraints

**Why:** Enforce data integrity and prevent NULL-related bugs

**Critical fields that must exist:**
- All primary keys
- `source_type`, `source_id` (identity)
- `title` (core business data)
- `raw_data` (audit trail)
- `ingested_at`, `started_at` (temporal tracking)
- `records_*` counters (default 0)
- `status` (state tracking)

### UNIQUE Constraints

**Why:** Prevent duplicates and enable idempotent operations

- `source_id` in raw tables (source-level deduplication)
- `source_id` in normalized_data (normalized-level deduplication)
- `source_type` in etl_checkpoints (one checkpoint per source)
- `run_id` in etl_run_history (unique run tracking)

## Indexing Strategy

### Single-Column Indexes

**Purpose:** Fast filtering on individual columns

```sql
-- Filtering by source
CREATE INDEX idx_normalized_source_type ON normalized_data(source_type);

-- Time-series queries
CREATE INDEX idx_normalized_created_at ON normalized_data(created_at);
CREATE INDEX idx_normalized_timestamp ON normalized_data(source_timestamp);

-- Category browsing
CREATE INDEX idx_normalized_category ON normalized_data(category);

-- Identity lookup
CREATE INDEX idx_normalized_canonical_id ON normalized_data(canonical_id);
```

### Composite Indexes

**Purpose:** Optimize multi-column queries

```sql
-- Entity queries: "Get all sources for Bitcoin"
CREATE INDEX idx_normalized_source_canonical 
ON normalized_data(source_type, canonical_id);

-- Time-series per source: "API1 records from last week"
CREATE INDEX idx_run_history_source_started 
ON etl_run_history(source_type, started_at);

-- Drift analysis: "Schema drift for RSS feed this month"
CREATE INDEX idx_drift_source_detected 
ON schema_drift_logs(source_name, detected_at);

-- API ingestion lookup: "Recent API1 data"
CREATE INDEX idx_raw_api_source_ingested 
ON raw_api_data(source_name, ingested_at);
```

### Index Selection Guidelines

1. **Cardinality:** Index high-cardinality columns (many unique values)
2. **Query Patterns:** Index columns used in WHERE, JOIN, ORDER BY
3. **Composite Order:** Most selective column first
4. **Avoid Over-Indexing:** Each index adds write overhead

## Data Types

### Temporal Data

**Always use `TIMESTAMP WITH TIME ZONE`:**
- Handles multiple timezones correctly
- Prevents subtraction errors
- Future-proof for global deployments

```python
# Good
created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

# Bad
created_at = Column(DateTime)  # No timezone!
```

### Numeric Data

```python
# Counts (always non-negative)
records_processed = Column(Integer, nullable=False, default=0)

# Measurements (can be decimal)
value = Column(Float, nullable=True)

# Confidence scores (0.0 to 1.0)
confidence_score = Column(Float, nullable=False)
```

### JSON Data

**Use for:**
- Variable schema data (raw_data)
- Arrays (tags, categories)
- Nested structures (extra_metadata)

**Don't use for:**
- Queryable business data
- Data with fixed schema

## Query Optimization Patterns

### 1. Entity-Centric Query
```python
# Get all sources for Bitcoin
records = db.query(NormalizedData).filter(
    NormalizedData.canonical_id == 'bitcoin'
).all()
# Uses: idx_normalized_canonical_id
```

### 2. Time-Series Query
```python
# Get recent RSS data
records = db.query(NormalizedData).filter(
    NormalizedData.source_type == 'rss',
    NormalizedData.created_at >= last_week
).order_by(desc(NormalizedData.created_at)).all()
# Uses: idx_normalized_source_type + idx_normalized_created_at
```

### 3. Multi-Source Entity Query
```python
# Get Bitcoin from all sources ordered by freshness
records = db.query(NormalizedData).filter(
    NormalizedData.canonical_id == 'bitcoin'
).order_by(desc(NormalizedData.source_timestamp)).all()
# Uses: idx_normalized_source_canonical + idx_normalized_timestamp
```

### 4. ETL Monitoring Query
```python
# Get failed runs in the last 24 hours
runs = db.query(ETLRunHistory).filter(
    ETLRunHistory.status == 'failure',
    ETLRunHistory.started_at >= yesterday
).order_by(desc(ETLRunHistory.started_at)).all()
# Uses: idx_run_history_status + idx_run_history_started_at
```

## Data Integrity

### Referential Integrity

**Current Design:** No foreign keys between raw and normalized tables

**Rationale:**
- Raw tables are append-only archives
- Normalized data can be regenerated
- Allows for flexible reprocessing

**Future Enhancement:** Could add FKs if needed:
```sql
ALTER TABLE normalized_data 
ADD CONSTRAINT fk_csv_source 
FOREIGN KEY (source_id) 
REFERENCES raw_csv_data(source_id) 
ON DELETE CASCADE;
```

### Application-Level Integrity

**Enforced by application logic:**
- Idempotent upserts (source_id uniqueness)
- Checkpoint atomicity (transaction boundaries)
- Status transitions (success/failure/running)

## Migration Strategy

### Step 1: Apply Migrations
```bash
# Add canonical_id
alembic upgrade add_canonical_id

# Add production constraints
alembic upgrade 002_production_constraints
```

### Step 2: Backfill Data
```bash
python backfill_canonical_ids.py
```

### Step 3: Verify Constraints
```sql
-- Check for NULL violations
SELECT COUNT(*) FROM normalized_data WHERE title IS NULL;

-- Check string lengths
SELECT MAX(LENGTH(source_id)) FROM normalized_data;

-- Verify indexes exist
SELECT indexname FROM pg_indexes WHERE tablename = 'normalized_data';
```

## Best Practices

### ✓ DO

1. **Use explicit lengths** for VARCHAR columns
2. **Add NOT NULL** for required fields
3. **Create composite indexes** for common multi-column queries
4. **Use timezone-aware timestamps** everywhere
5. **Set defaults** for counter columns (0, not NULL)
6. **Document schema changes** in migration files
7. **Test migrations** on staging data first

### ✗ DON'T

1. **Don't use unbounded strings** (VARCHAR without length)
2. **Don't allow NULLs** unless the field is truly optional
3. **Don't over-index** (creates write overhead)
4. **Don't use naive timestamps** (always use timezone)
5. **Don't skip migrations** (always use Alembic)
6. **Don't hardcode values** (use enums or constants)
7. **Don't ignore query performance** (monitor slow queries)

## Monitoring & Maintenance

### Table Statistics
```sql
-- Table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Index usage
SELECT 
    indexrelname AS index_name,
    idx_scan AS index_scans,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

### Performance Metrics
- Query latency (track via API metrics)
- Index hit ratio (should be >99%)
- Table bloat (vacuum regularly)
- Missing indexes (analyze slow queries)

## Summary

This production-grade data model provides:

✓ **Proper Normalization** (1NF, 2NF, 3NF)
✓ **Data Integrity** (NOT NULL, UNIQUE constraints)
✓ **Performance** (Strategic indexing)
✓ **Scalability** (Efficient query patterns)
✓ **Maintainability** (Clear schema, good documentation)
✓ **Auditability** (Raw data preservation)
✓ **Flexibility** (JSON for variable schema)

All while maintaining data lineage, supporting identity unification, and enabling comprehensive ETL monitoring.
