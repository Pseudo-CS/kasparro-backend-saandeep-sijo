# ETL Backend Service - Development Notes

## Development Setup

### Local Development (Without Docker)

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up PostgreSQL locally:**
   ```bash
   # Install PostgreSQL (macOS)
   brew install postgresql
   brew services start postgresql
   
   # Create database
   createdb etl_db
   ```

4. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Initialize database:**
   ```bash
   python init_db.py
   ```

6. **Run API server:**
   ```bash
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Run ETL manually:**
   ```bash
   python run_etl.py
   ```

## Architecture Decisions

### Why Pydantic?
- **Type Safety**: Automatic validation of incoming data
- **Documentation**: Self-documenting schemas
- **Performance**: Fast validation with minimal overhead
- **Integration**: Perfect fit with FastAPI

### Why SQLAlchemy?
- **ORM Benefits**: Clean, Pythonic database interactions
- **Migration Support**: Easy schema evolution with Alembic
- **Connection Pooling**: Built-in connection management
- **Database Agnostic**: Easy to switch databases

### Why FastAPI?
- **Performance**: Async support, similar to Node.js/Go
- **Type Hints**: Leverages Python type hints
- **Auto Documentation**: Swagger UI out of the box
- **Modern**: Latest Python 3.6+ features

### Why Docker?
- **Consistency**: Same environment everywhere
- **Isolation**: No dependency conflicts
- **Portability**: Runs anywhere Docker runs
- **Simplicity**: One command to start everything

## Data Flow

```
CSV/API/RSS → Validate (Pydantic) → Raw Tables → Transform → Normalized Table → API
                                           ↓
                                    Checkpoint Table
```

## Database Schema Design

### Raw Tables
Purpose: Store original data exactly as received
- `raw_csv_data`: CSV records
- `raw_api_data`: API responses
- `raw_rss_data`: RSS feed entries

Benefits:
- Data lineage and audit trail
- Ability to re-process if transformation logic changes
- Debugging and troubleshooting

### Normalized Table
Purpose: Unified schema across all sources
- Single source of truth for querying
- Consistent field names and types
- Efficient indexing and querying

### Checkpoint Table
Purpose: Track ETL progress and state
- Enables incremental loading
- Supports resume-on-failure
- Provides run statistics

## API Design

### RESTful Principles
- GET /data: Read operation, idempotent
- GET /health: System status check
- GET /stats: ETL metrics and monitoring

### Response Format
```json
{
  "data": [...],
  "metadata": {
    "request_id": "uuid",
    "api_latency_ms": 42.3,
    "pagination": {...}
  }
}
```

Benefits:
- Consistent structure
- Easy to extend
- Includes request tracking
- Performance metrics

## Testing Strategy

### Unit Tests
- Individual functions and methods
- Mock external dependencies
- Fast execution

### Integration Tests
- Database interactions
- API endpoints
- ETL pipeline

### Test Coverage Goals
- 80%+ code coverage
- All critical paths tested
- Edge cases and error scenarios

## Performance Considerations

### Database Indexing
```sql
-- Source ID for deduplication
CREATE INDEX idx_normalized_source_id ON normalized_data(source_id);

-- Timestamp for incremental loading
CREATE INDEX idx_normalized_created_at ON normalized_data(created_at);

-- Category for filtering
CREATE INDEX idx_normalized_category ON normalized_data(category);
```

### Batch Processing
- Process CSV in batches (default: 1000 records)
- Commit after each batch
- Reduces memory usage
- Allows partial progress

### Connection Pooling
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=10,        # Number of connections to maintain
    max_overflow=20,     # Additional connections when needed
    pool_pre_ping=True   # Verify connection before use
)
```

## Error Handling

### Strategy
1. **Try-Catch at Multiple Levels**
   - Individual record processing
   - Batch processing
   - Service level
   - API level

2. **Logging**
   - Log all errors with context
   - Include stack traces for debugging
   - Structured logging for parsing

3. **Graceful Degradation**
   - Continue processing after individual failures
   - Update checkpoint on partial success
   - Return meaningful error messages

## Security Considerations

### API Keys
- **Never** commit to version control
- Store in environment variables
- Use secret management services in production

### Database
- Use connection string with credentials from environment
- Enable SSL for database connections in production
- Use read-only user for API queries if possible

### API
- Rate limiting on endpoints
- Input validation with Pydantic
- SQL injection prevention (parameterized queries)

## Monitoring & Alerting

### Key Metrics
- ETL run success/failure rate
- API response times
- Database connection pool usage
- Error rates by source

### Suggested Alerts
- ETL failure (immediate)
- High error rate (>5% failures)
- API latency >1s (warning)
- Database connection errors

## Future Enhancements

### Phase 1 (Next Sprint)
- [ ] Add more data sources
- [ ] Implement data quality checks
- [ ] Add data lineage tracking
- [ ] Implement change data capture

### Phase 2 (Future)
- [ ] GraphQL API
- [ ] Real-time streaming ingestion
- [ ] Machine learning for anomaly detection
- [ ] Advanced analytics dashboard

### Phase 3 (Long-term)
- [ ] Multi-tenancy support
- [ ] Data versioning
- [ ] Advanced access control
- [ ] Data marketplace features

## Common Issues & Solutions

### Issue: Database connection timeout
**Solution**: Check DATABASE_URL, verify PostgreSQL is running, increase timeout

### Issue: ETL fails on large CSV
**Solution**: Reduce batch size, increase memory allocation

### Issue: API keys not working
**Solution**: Verify .env file is loaded, check for typos, ensure no trailing spaces

### Issue: Docker container exits immediately
**Solution**: Check logs with `docker-compose logs`, verify environment variables

### Issue: Tests failing
**Solution**: Ensure test database is clean, check test fixtures, verify mocks

## Code Style

### Follow PEP 8
- 4 spaces for indentation
- Max line length: 100 characters
- Docstrings for all public functions

### Type Hints
```python
def process_data(data: Dict[str, Any]) -> Optional[NormalizedDataSchema]:
    """Process raw data and return normalized schema."""
    ...
```

### Imports Order
1. Standard library
2. Third-party packages
3. Local modules

### Documentation
- Docstrings for all public classes and functions
- Inline comments for complex logic
- README for setup and usage

## Contributing

### Pull Request Process
1. Create feature branch
2. Write tests for new features
3. Ensure all tests pass
4. Update documentation
5. Submit PR with description

### Commit Messages
```
feat: add RSS feed ingestion
fix: resolve checkpoint update issue
docs: update deployment guide
test: add API endpoint tests
refactor: simplify ETL orchestrator
```

---

**Last Updated**: December 25, 2025
