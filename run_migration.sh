#!/bin/bash
# Manual migration script for Render or production environments
# Usage: bash run_migration.sh

set -e

echo "=================================================="
echo "Running Identity Unification Migration"
echo "=================================================="
echo ""

# Run the migration
python migrate_db.py

echo ""
echo "=================================================="
echo "✓ Migration completed successfully!"
echo "=================================================="
echo ""
echo "The following changes were applied:"
echo "  • Added canonical_id column to normalized_data table"
echo "  • Created index: idx_normalized_canonical_id"
echo "  • Created index: idx_normalized_source_canonical"
echo "  • Created index: idx_normalized_timestamp"
echo ""
echo "Next steps:"
echo "  1. Verify the ETL pipeline is running correctly"
echo "  2. Check that canonical_id values are being populated"
echo "  3. Monitor logs for any identity resolution issues"
echo ""
