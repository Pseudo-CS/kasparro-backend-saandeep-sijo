# Testing & Deployment Scripts

## Quick Start

To set up and test identity unification:

```bash
python setup_and_test.py
```

This automated script will:
1. ✓ Apply database migrations
2. ✓ Run comprehensive tests  
3. ✓ Verify production readiness

## Individual Scripts

### migrate_db.py
Applies database schema migrations without requiring Alembic configuration.

**What it does:**
- Adds `canonical_id` column to `normalized_data` table
- Creates 5 production-grade composite indexes
- Checks existing schema to avoid duplicate changes
- Idempotent (safe to run multiple times)

**Usage:**
```bash
python migrate_db.py
```

**Output:**
```
Database Schema Migration
============================================================
1. Ensuring base tables exist...
  ✓ Base tables verified

2. Applying identity unification migration...
  + Adding canonical_id column...
  ✓ Added canonical_id column
  + Creating canonical_id index...
  ✓ Created canonical_id index

3. Applying production constraints...
  + Creating idx_normalized_source_canonical...
  ✓ Created idx_normalized_source_canonical
  ...
  
✓ All migrations applied successfully!
```

---

### test_identity_unification.py
Comprehensive test suite for identity unification feature.

**Tests:**
1. **Identity Resolution Logic** - Verifies canonical ID generation
2. **Database Schema** - Checks columns and indexes exist
3. **Ingestion with Identity** - Tests CSV ingestion assigns canonical IDs
4. **Identity Queries** - Validates querying by canonical ID

**Usage:**
```bash
python test_identity_unification.py
```

**Output:**
```
IDENTITY UNIFICATION - COMPREHENSIVE TEST SUITE
======================================================================

TEST 1: Identity Resolution Logic
======================================================================
  ✓ CSV ID extraction: 'bitcoin'
  ✓ Symbol matching: 'bitcoin'
  ✓ Title normalization: 'ethereum-news'
  ✓ Ethereum symbol: 'ethereum'
  ✓ Solana CSV ID: 'solana'

Results: 5 passed, 0 failed

TEST 2: Database Schema
======================================================================
  ✓ Column 'canonical_id' exists
  ✓ Column 'source_type' exists
  ✓ Index 'idx_normalized_canonical_id' exists
  ...

TEST SUMMARY
======================================================================
  ✓ PASS: Identity Resolution
  ✓ PASS: Database Schema
  ✓ PASS: Ingestion with Identity
  ✓ PASS: Identity Queries

======================================================================
✓ ALL TESTS PASSED (4/4)
======================================================================

🎉 Identity unification is ready for production!
```

**Exit Codes:**
- `0`: All tests passed
- `1`: One or more tests failed

---

### backfill_canonical_ids.py
Backfills canonical IDs for existing records in the database.

**When to use:**
- After applying migrations to a database with existing data
- When you want to update canonical IDs with improved resolution logic

**What it does:**
- Queries all records without `canonical_id`
- Resolves canonical identity for each
- Updates records in batches of 100
- Shows statistics on multi-source entities

**Usage:**
```bash
python backfill_canonical_ids.py
```

**Output:**
```
Starting canonical_id backfill process...
Found 140 records without canonical_id
Progress: 100/140 (71.4%)
✓ Successfully backfilled canonical_id for 140/140 records
✓ Total unique canonical identities: 45

✓ Top unified entities (present in multiple sources):
  - bitcoin: 3 sources
  - ethereum: 3 sources
  - solana: 2 sources
Backfill process completed
```

---

### setup_and_test.py
Automated end-to-end setup and testing.

**What it does:**
1. Runs `migrate_db.py` to apply schema changes
2. Runs `test_identity_unification.py` to verify everything works
3. Provides clear pass/fail status

**Usage:**
```bash
python setup_and_test.py
```

**Output:**
```
IDENTITY UNIFICATION - SETUP & TEST
======================================================================
This script will:
  1. Apply database migrations
  2. Run comprehensive tests
  3. Verify production readiness

Step: Apply Database Migrations
======================================================================
Command: python migrate_db.py
✓ Apply Database Migrations completed successfully

Step: Run Identity Unification Tests
======================================================================
Command: python test_identity_unification.py
✓ Run Identity Unification Tests completed successfully

======================================================================
✓ ALL SETUP AND TESTS COMPLETED SUCCESSFULLY!
======================================================================

🎉 Identity unification is ready to push!

Next steps:
  git add .
  git commit -m 'Add identity unification feature'
  git push
```

**Exit Codes:**
- `0`: Setup and tests passed
- `1`: Setup or tests failed

---

## Workflow

### For New Installations

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up database and test
python setup_and_test.py

# 3. If tests pass, you're ready!
```

### For Existing Databases

```bash
# 1. Apply migrations
python migrate_db.py

# 2. Backfill existing data
python backfill_canonical_ids.py

# 3. Run tests to verify
python test_identity_unification.py
```

### Before Pushing to Git

```bash
# Always run full test suite
python setup_and_test.py

# If all tests pass:
git add .
git commit -m "Add identity unification feature"
git push
```

---

## Troubleshooting

### "canonical_id column does not exist"
**Solution:** Run `python migrate_db.py`

### "tests failed"
**Check:**
1. Database is running
2. Migrations were applied
3. `.env` file is configured
4. Dependencies are installed

**Debug:**
```bash
# Check database connection
python -c "from core.database import test_connection; print(test_connection())"

# Check if migrations were applied
python -c "from sqlalchemy import inspect; from core.database import engine; print([c['name'] for c in inspect(engine).get_columns('normalized_data')])"
```

### "backfill found 0 records"
This is normal if:
- Database is empty (no data ingested yet)
- All records already have canonical_id

Run ingestion first:
```bash
python init_db.py
```

---

## CI/CD Integration

Add to your CI pipeline:

```yaml
# GitHub Actions example
- name: Setup and Test Identity Unification
  run: |
    python setup_and_test.py
    
# Or separate steps:
- name: Apply Migrations
  run: python migrate_db.py
  
- name: Run Identity Tests
  run: python test_identity_unification.py
```

---

## See Also

- [IDENTITY_UNIFICATION.md](IDENTITY_UNIFICATION.md) - Architecture guide
- [IDENTITY_UNIFICATION_IMPLEMENTATION.md](IDENTITY_UNIFICATION_IMPLEMENTATION.md) - Implementation details
- [DATA_MODELING_GUIDE.md](DATA_MODELING_GUIDE.md) - Database schema documentation
