#!/bin/bash
set -e

echo "Starting ETL Backend Service..."

# Wait for database to be ready
echo "Waiting for database..."
python -c "
import time
import sys
from core.database import test_connection
from core.logging_config import setup_logging

setup_logging()

for i in range(30):
    if test_connection():
        print('Database is ready!')
        sys.exit(0)
    print(f'Attempt {i+1}/30: Database not ready, waiting...')
    time.sleep(2)

print('Database connection timeout!')
sys.exit(1)
"

# Initialize database
echo "Initializing database..."
python -c "
from core.database import init_db
from core.logging_config import setup_logging

setup_logging()
init_db()
print('Database initialized!')
"

# Run initial ETL ingestion
echo "Running initial ETL ingestion..."
python -c "
import asyncio
from ingestion.etl_orchestrator import run_etl_pipeline
from core.logging_config import setup_logging

setup_logging()
asyncio.run(run_etl_pipeline())
print('Initial ETL completed!')
" || echo "Initial ETL failed, continuing..."

# Start ETL scheduler in background
echo "Starting ETL scheduler..."
python -c "
import schedule
import time
import asyncio
from ingestion.etl_orchestrator import run_etl_pipeline
from core.logging_config import setup_logging
import logging

setup_logging()
logger = logging.getLogger(__name__)

def run_scheduled_etl():
    logger.info('Running scheduled ETL pipeline...')
    asyncio.run(run_etl_pipeline())

# Schedule ETL to run every 6 hours
schedule.every(6).hours.do(run_scheduled_etl)

logger.info('ETL scheduler started (runs every 6 hours)')

while True:
    schedule.run_pending()
    time.sleep(60)
" &

# Start API server
echo "Starting API server..."
exec uvicorn api.main:app --host 0.0.0.0 --port 8000 --log-level info
