# ETL Backend Service - Production-Grade Assignment

A comprehensive, production-grade ETL (Extract, Transform, Load) backend service with a REST API, built as a complete solution for data ingestion, normalization, and serving.

## 🎯 Project Overview

This project implements a complete ETL pipeline and backend API service that:
- Ingests data from **3 sources**: CSV, API, and RSS feeds
- Stores raw data and normalizes it into a unified schema
- Provides REST API endpoints with pagination, filtering, and metadata
- Implements incremental ingestion with checkpoint management
- Handles authentication securely (no hard-coded keys)
- Runs in Docker containers with automatic ETL scheduling
- Includes comprehensive test coverage

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     ETL Backend Service                      │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ CSV Source   │  │ API Sources  │  │  RSS Feed    │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                  │                  │               │
│         ▼                  ▼                  ▼               │
│  ┌─────────────────────────────────────────────────┐        │
│  │         ETL Ingestion Layer                     │        │
│  │  - Type Validation (Pydantic)                   │        │
│  │  - Incremental Loading                          │        │
│  │  - Rate Limiting                                │        │
│  │  - Error Handling                               │        │
│  └─────────────────┬───────────────────────────────┘        │
│                    │                                          │
│                    ▼                                          │
│  ┌─────────────────────────────────────────────────┐        │
│  │            PostgreSQL Database                  │        │
│  │  ┌───────────────┐  ┌──────────────────┐       │        │
│  │  │  Raw Tables   │  │ Normalized Table │       │        │
│  │  │  - raw_csv    │  │ - normalized_data│       │        │
│  │  │  - raw_api    │  └──────────────────┘       │        │
│  │  │  - raw_rss    │  ┌──────────────────┐       │        │
│  │  └───────────────┘  │ Checkpoint Table │       │        │
│  │                     │ - etl_checkpoints│       │        │
│  │                     │ - etl_run_history│       │        │
│  │                     └──────────────────┘       │        │
│  └─────────────────┬───────────────────────────────┘        │
│                    │                                          │
│                    ▼                                          │
│  ┌─────────────────────────────────────────────────┐        │
│  │          FastAPI REST API                       │        │
│  │  - GET /data (pagination, filtering)            │        │
│  │  - GET /health (DB + ETL status)                │        │
│  │  - GET /stats (ETL summaries)                   │        │
│  └─────────────────────────────────────────────────┘        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
kasparro-backend-saandeep-sijo/
├── api/                          # FastAPI application
│   ├── __init__.py
│   └── main.py                   # API endpoints (/data, /health, /stats)
├── core/                         # Core configuration and utilities
│   ├── __init__.py
│   ├── config.py                 # Settings management (Pydantic)
│   ├── database.py               # Database connection & session
│   ├── logging_config.py         # Logging configuration
│   └── models.py                 # SQLAlchemy models
├── ingestion/                    # ETL ingestion services
│   ├── __init__.py
│   ├── csv_ingestion.py          # CSV data ingestion
│   ├── api_ingestion.py          # API data ingestion
│   ├── rss_ingestion.py          # RSS feed ingestion
│   └── etl_orchestrator.py       # ETL pipeline orchestrator
├── services/                     # Business logic services
│   ├── __init__.py
│   ├── checkpoint_service.py     # Checkpoint management
│   └── etl_utils.py              # ETL utilities
├── schemas/                      # Pydantic schemas
│   ├── __init__.py
│   └── data_schemas.py           # Data validation schemas
├── tests/                        # Comprehensive test suite
│   ├── __init__.py
│   ├── conftest.py               # Test configuration
│   ├── test_api_endpoints.py    # API endpoint tests
│   ├── test_csv_ingestion.py    # CSV ingestion tests
│   ├── test_checkpoint_service.py # Checkpoint tests
│   └── test_etl_utils.py         # Utility tests
├── data/                         # Data files
│   └── sample_data.csv           # Sample CSV data
├── Dockerfile                    # Docker container definition
├── docker-compose.yml            # Docker Compose configuration
├── docker-entrypoint.sh          # Container startup script
├── Makefile                      # Build and deployment commands
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
├── .gitignore                    # Git ignore rules
└── README.md                     # This file
```

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Make (optional, for convenient commands)
- API keys for your data sources

### Setup

1. **Clone the repository:**
   ```bash
   cd kasparro-backend-saandeep-sijo
   ```

2. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` and add your API keys:
   ```bash
   # Get CoinPaprika API key from: https://coinpaprika.com/api
   API_KEY_SOURCE_1=your_coinpaprika_api_key_here
   API_URL_SOURCE_1=https://api.coinpaprika.com/v1/tickers
   
   # CoinGecko is free, no API key required
   API_URL_SOURCE_2=https://api.coingecko.com/api/v3/coins/markets
   
   # RSS feed for crypto news
   RSS_FEED_URL=https://cointelegraph.com/rss
   ```

3. **Start the services:**
   ```bash
   make up
   ```
   
   Or without Make:
   ```bash
   docker-compose up -d
   ```

4. **Verify the service is running:**
   ```bash
   curl http://localhost:8000/health
   ```

5. **Access the API documentation:**
   Open your browser to: http://localhost:8000/docs

## 📊 API Endpoints

### GET /data
Retrieve normalized data with pagination and filtering.

**Parameters:**
- `page` (int): Page number (default: 1)
- `page_size` (int): Items per page (default: 50, max: 1000)
- `source_type` (string): Filter by source (csv, api1, api2, rss)
- `category` (string): Filter by category
- `search` (string): Search in title and description

**Example:**
```bash
curl "http://localhost:8000/data?page=1&page_size=10&source_type=csv"
```

**Response:**
```json
{
  "data": [
    {
      "source_type": "csv",
      "source_id": "csv_1",
      "title": "Sample Product A",
      "description": "High-quality product",
      "value": 99.99,
      "category": "electronics",
      "tags": null,
      "source_timestamp": "2024-01-15T10:30:00Z",
      "metadata": {"original_id": "1"}
    }
  ],
  "metadata": {
    "request_id": "uuid-here",
    "api_latency_ms": 45.23,
    "pagination": {
      "page": 1,
      "page_size": 10,
      "total_records": 100,
      "total_pages": 10
    },
    "filters_applied": {
      "source_type": "csv"
    }
  }
}
```

### GET /health
Health check endpoint.

**Example:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "database_connected": true,
  "etl_last_run": "2024-12-25T10:30:00Z",
  "etl_status": "success",
  "timestamp": "2024-12-25T11:00:00Z"
}
```

### GET /stats
ETL statistics and summaries.

**Parameters:**
- `limit` (int): Number of recent runs to return (default: 10)

**Example:**
```bash
curl http://localhost:8000/stats?limit=5
```

**Response:**
```json
{
  "checkpoints": [
    {
      "source_type": "csv",
      "records_processed": 1000,
      "last_success_at": "2024-12-25T10:30:00Z",
      "last_failure_at": null,
      "status": "success",
      "metadata": {}
    }
  ],
  "recent_runs": [
    {
      "run_id": "run_20241225_103000_abc123",
      "source_type": "csv",
      "started_at": "2024-12-25T10:30:00Z",
      "completed_at": "2024-12-25T10:35:00Z",
      "duration_seconds": 300.5,
      "records_processed": 1000,
      "records_inserted": 800,
      "records_updated": 200,
      "records_failed": 0,
      "status": "success"
    }
  ],
  "summary": {
    "total_records_normalized": 5000,
    "total_records_processed": 5000,
    "successful_sources": 3,
    "failed_sources": 0,
    "total_sources": 3
  }
}
```

## 🔄 ETL Pipeline

### Data Sources

1. **CSV Source**: Ingests cryptocurrency data from CSV files
   - Incremental loading based on timestamps
   - Type validation with Pydantic
   - Batch processing for efficiency

2. **API Source 1 - CoinPaprika**: Ingests cryptocurrency ticker data
   - API: https://api.coinpaprika.com/v1/tickers
   - Requires API key (free tier available at https://coinpaprika.com/api)
   - Rate limiting to avoid throttling
   - Provides: price, volume, market cap, price changes

3. **API Source 2 - CoinGecko**: Ingests cryptocurrency market data
   - API: https://api.coingecko.com/api/v3/coins/markets
   - Free tier, no API key required
   - Pagination support
   - Provides: current price, market data, 24h changes

4. **RSS Feed**: Ingests cryptocurrency news from Cointelegraph
   - Source: https://cointelegraph.com/rss
   - Parses XML/RSS formats
   - Extracts news articles and metadata
   - Tracks entries by GUID or link

### Data Flow

1. **Extraction**: Data is fetched from sources
2. **Validation**: Pydantic schemas validate and type-check data
3. **Raw Storage**: Original data stored in raw_* tables
4. **Normalization**: Data transformed to unified schema
5. **Storage**: Normalized data stored in normalized_data table
6. **Checkpointing**: Progress tracked in etl_checkpoints table

### Incremental Ingestion

- **Checkpoint Table**: Tracks last processed timestamp/ID for each source
- **Resume on Failure**: Automatically resumes from last checkpoint after failure
- **Idempotent Writes**: Same data can be ingested multiple times safely
- **Upsert Logic**: Updates existing records, inserts new ones

### Scheduling

The ETL pipeline runs automatically:
- **Initial Run**: On container startup
- **Scheduled Runs**: Every 6 hours (configurable)
- **Manual Trigger**: `make run-etl`

## 🧪 Testing

### Run All Tests

```bash
make test
```

Or:
```bash
docker-compose exec etl_service pytest tests/ -v --cov=. --cov-report=term-missing
```

### Test Coverage

The test suite covers:
- ✅ ETL transformation logic
- ✅ Incremental ingestion
- ✅ Failure scenarios and recovery
- ✅ API endpoints (pagination, filtering)
- ✅ Schema validation and mismatches
- ✅ Checkpoint management
- ✅ Rate limiting logic
- ✅ Idempotent operations

### Test Files

- `test_etl_utils.py`: Utility functions and helpers
- `test_csv_ingestion.py`: CSV ingestion logic
- `test_api_endpoints.py`: API endpoint behavior
- `test_checkpoint_service.py`: Checkpoint and resume logic

## 🛠️ Make Commands

```bash
make up          # Start all services
make down        # Stop all services
make restart     # Restart services
make logs        # View all logs
make logs-api    # View API logs only
make logs-db     # View database logs only
make build       # Build Docker images
make test        # Run test suite
make run-etl     # Manually trigger ETL
make shell       # Open shell in container
make db-shell    # Open PostgreSQL shell
make clean       # Remove all containers and volumes
```

## 🔒 Security

### API Key Management

- **Environment Variables**: All API keys stored in `.env` file
- **No Hard-coding**: No keys in source code
- **Docker Secrets**: Keys passed to containers via environment
- **Validation**: Settings validated with Pydantic

### Database Security

- **Connection Pooling**: Secure connection management
- **Parameterized Queries**: SQL injection prevention
- **Access Control**: Database credentials in environment only

## 📈 Monitoring & Observability

### Logs

- **Structured Logging**: JSON-formatted logs with timestamps
- **Log Levels**: Configurable (DEBUG, INFO, WARNING, ERROR)
- **Request Tracking**: Each API request has unique request_id
- **ETL Tracking**: Each ETL run has unique run_id

### Metrics

Available via `/stats` endpoint:
- Records processed per source
- Success/failure rates
- Run durations
- Last run timestamps
- Error messages

### Health Checks

- **Database Connectivity**: Tested on each health check
- **ETL Status**: Last run status included
- **Docker Health**: Built-in container health checks

## 🚢 Deployment

### Cloud Deployment (Example with AWS)

1. **Build and push Docker image:**
   ```bash
   docker build -t your-registry/etl-service:latest .
   docker push your-registry/etl-service:latest
   ```

2. **Deploy to ECS/EKS or EC2:**
   - Set environment variables in AWS Secrets Manager
   - Configure RDS PostgreSQL instance
   - Set up EventBridge/CloudWatch for scheduled ETL runs
   - Configure Application Load Balancer for API

3. **Scheduled ETL:**
   - AWS EventBridge rule (cron: `0 */6 * * *`)
   - Triggers ECS task or Lambda to run ETL
   - Or use built-in scheduler (runs inside container)

### Environment Variables for Production

```bash
# Database
DATABASE_URL=postgresql://user:pass@rds-endpoint:5432/etl_db

# API Keys (from AWS Secrets Manager)
API_KEY_SOURCE_1=secret_key
API_KEY_SOURCE_2=secret_key

# Application
ENVIRONMENT=production
LOG_LEVEL=INFO
```

## 🔍 Smoke Test Procedure

### End-to-End Smoke Test

1. **Start the service:**
   ```bash
   make up
   ```

2. **Wait for initialization (30-60 seconds):**
   ```bash
   make logs-api
   ```
   
   Look for: "Initial ETL completed!"

3. **Test API health:**
   ```bash
   curl http://localhost:8000/health
   ```
   
   Expected: `"status": "healthy"`, `"database_connected": true`

4. **Test data retrieval:**
   ```bash
   curl http://localhost:8000/data?page=1&page_size=5
   ```
   
   Expected: Returns data array with records

5. **Test filtering:**
   ```bash
   curl "http://localhost:8000/data?source_type=csv&category=electronics"
   ```
   
   Expected: Returns filtered results

6. **Test statistics:**
   ```bash
   curl http://localhost:8000/stats
   ```
   
   Expected: Shows checkpoint status and run history

7. **Test ETL restart/resume:**
   ```bash
   docker-compose restart etl_service
   make logs-api
   ```
   
   Expected: Service resumes, ETL runs successfully

8. **Manual ETL trigger:**
   ```bash
   make run-etl
   ```
   
   Expected: ETL runs and completes successfully

9. **Test rate limiting** (if applicable):
   - Make rapid API calls and verify no 429 errors in ingestion

10. **Check logs for errors:**
    ```bash
    make logs | grep ERROR
    ```
    
    Expected: No critical errors

## 📋 Assignment Checklist

### P0 Requirements ✅

- ✅ Data ingestion from API source (with authentication)
- ✅ Data ingestion from CSV source
- ✅ Raw data storage (raw_csv_data, raw_api_data, raw_rss_data)
- ✅ Normalized schema (normalized_data table)
- ✅ Type cleaning and validation (Pydantic schemas)
- ✅ Incremental ingestion (checkpoint-based)
- ✅ Secure authentication (environment variables)
- ✅ GET /data endpoint (pagination, filtering, metadata)
- ✅ GET /health endpoint (DB connectivity, ETL status)
- ✅ Docker setup (Dockerfile, docker-compose.yml)
- ✅ Makefile (make up, make down)
- ✅ README with setup instructions
- ✅ Basic test suite

### P1 Requirements ✅

- ✅ Third data source (RSS feed)
- ✅ Schema unification across all sources
- ✅ Checkpoint table (etl_checkpoints)
- ✅ Resume-on-failure logic
- ✅ Idempotent writes (upsert operations)
- ✅ GET /stats endpoint (ETL summaries, run history)
- ✅ Comprehensive test coverage
- ✅ Clean architecture (separate layers)

### Final Evaluation Requirements ✅

- ✅ API access with authentication (secure key management)
- ✅ Working Docker image (auto-starts ETL and API)
- ✅ Automated test suite (pytest with coverage)
- ✅ Cloud deployment ready (instructions included)
- ✅ Smoke test procedure (documented above)

## 🤝 Support

For issues or questions:
1. Check the logs: `make logs`
2. Review test output: `make test`
3. Verify environment variables: `.env` file
4. Check API documentation: http://localhost:8000/docs

## 📄 License

This project is created as an assignment submission.

---

**Author**: Saandeep Sijo  
**Date**: December 25, 2025  
**Version**: 1.0.0
