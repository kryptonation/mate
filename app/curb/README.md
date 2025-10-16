# CURB (Taxi Fleet) Module - Updated

This module handles the automated processing of CURB taxi meter trip data using modern async patterns, SQLAlchemy 2.x, and proper dependency injection.

## Overview

The CURB system processes taxi trip data through the following workflow:

1. **Fetch & Import**: Retrieve trip data from the CURB SOAP API and import into database
2. **Reconcile**: Mark trips as reconciled (locally for dev/uat, on server for production)
3. **Associate**: Link trips with active leases
4. **Post**: Create ledger entries for trips

## Architecture

### Technology Stack

- **SQLAlchemy 2.x**: ORM with async support
- **FastAPI**: Async REST API endpoints
- **Celery**: Task queue for automated processing
- **Redis**: Message broker and result backend
- **HTTPX**: Async HTTP client for SOAP API calls
- **Pydantic**: Schema validation

### Module Structure

```
app/curb/
├── __init__.py              # Module exports
├── models.py                # SQLAlchemy 2.x models
├── schemas.py               # Pydantic schemas
├── repository.py            # Data access layer (async)
├── services.py              # Business logic layer (async)
├── router.py                # FastAPI endpoints (async)
├── tasks.py                 # Celery tasks
├── soap_client.py           # Async SOAP client
├── utils.py                 # XML parsing utilities
├── exceptions.py            # Custom exceptions
└── README.md                # This file
```

### Design Patterns

- **Repository Pattern**: Data access abstraction
- **Service Layer**: Business logic separation
- **Dependency Injection**: Clean dependencies between layers
- **Async/Await**: Non-blocking I/O operations
- **Task Queue**: Background job processing

## Models

### CURBTrip

Main trip data model with comprehensive fields:

**Identifiers:**
- `id`: Primary key
- `record_id`: CURB record identifier (unique with period)
- `period`: Trip period (YYYYMM format)
- `trip_number`: Service number

**Vehicle & Driver:**
- `cab_number`: Vehicle medallion/plate number
- `driver_id`: Driver identifier
- `driver_fk`, `medallion_fk`, `vehicle_fk`: Foreign keys for associations

**Timing:**
- `start_date`, `end_date`: Trip dates
- `start_time`, `end_time`: Trip times

**Fare Breakdown:**
- `trip_amount`: Base fare
- `tips`: Tip amount
- `extras`: Extra charges
- `tolls`: Toll charges
- `tax`: State tax
- `imp_tax`: Improvement surcharge
- `total_amount`: Total fare

**Fees:**
- `ehail_fee`: E-hail service fee
- `health_fee`: Health surcharge
- `congestion_fee`: Congestion pricing
- `airport_fee`: Airport pickup/dropoff fee
- `cbdt_fee`: Congestion relief zone toll

**Location:**
- `gps_start_lat`, `gps_start_lon`: Start coordinates
- `gps_end_lat`, `gps_end_lon`: End coordinates
- `from_address`, `to_address`: Address strings

**Payment:**
- `payment_type`: T=Cash, P=Private, C=Credit Card
- `cc_number`: Masked card number
- `auth_code`: Authorization code
- `auth_amount`: Authorized amount

**Status:**
- `is_reconciled`: Reconciliation status
- `is_posted`: Posting status
- `recon_stat`: Reconciliation receipt number
- `status`: Current status (Imported/Reconciled/Posted/Failed)
- `associate_failed_reason`: Association failure reason
- `post_failed_reason`: Posting failure reason

**Metadata:**
- `passengers`: Number of passengers
- `distance_service`: Distance in service (miles)
- `distance_bs`: Dead head distance
- `reservation_number`: Reservation ID
- `import_id`: Reference to import log

### CURBImportLog

Tracks import operations:

- `id`: Primary key
- `import_source`: Source (SOAP/Upload/Manual)
- `imported_by`: User or system
- `import_start`, `import_end`: Timestamps
- `total_records`: Total processed
- `success_count`: Successfully imported
- `failure_count`: Failed imports
- `duplicate_count`: Duplicates skipped
- `status`: IN_PROGRESS/COMPLETED/FAILED/PARTIAL
- `error_summary`: Error details

### CURBTripReconciliation

Tracks reconciliation operations:

- `id`: Primary key
- `trip_id`: Reference to CURBTrip (unique)
- `recon_stat`: Reconciliation receipt number
- `reconciled_at`: Timestamp
- `reconciled_by`: User or system
- `reconciliation_type`: LOCAL or REMOTE

## API Endpoints

### Trip Operations

**List Trips**
```
GET /curb/trips
Query Parameters:
  - trip_id: Filter by trip ID
  - record_id: Filter by record ID
  - period: Filter by period
  - driver_id: Comma-separated driver IDs
  - cab_number: Comma-separated cab numbers
  - start_date_from, start_date_to: Date range
  - payment_type: T, P, or C
  - is_reconciled: Boolean
  - is_posted: Boolean
  - status: Comma-separated statuses
  - page, per_page: Pagination
  - sort_by, sort_order: Sorting
```

**Get Trip**
```
GET /curb/trips/{trip_id}
```

**Update Trip**
```
PATCH /curb/trips/{trip_id}
Body: CURBTripUpdate schema
```

**Export Trips**
```
GET /curb/trips/export/{format}
Formats: excel, pdf
Query Parameters: Same as list trips
```

### Import Operations

**Import Trips**
```
POST /curb/import
Query Parameters:
  - from_date: MM/DD/YYYY
  - to_date: MM/DD/YYYY
  - driver_id: Optional filter
  - cab_number: Optional filter
  - recon_stat: Reconciliation filter
```

### Reconciliation Operations

**Reconcile Trips**
```
POST /curb/reconcile
Query Parameters:
  - trip_ids: List of trip IDs
  - recon_stat: Optional receipt number
Environment-aware:
  - Production: Calls CURB API
  - Dev/UAT: Local reconciliation only
```

### Posting Operations

**Post Trips**
```
POST /curb/post
Posts all reconciled but unposted trips to ledger
```

### Log Operations

**List Import Logs**
```
GET /curb/logs
Query Parameters:
  - log_id, import_source, imported_by
  - import_start_from, import_start_to
  - status
  - page, per_page, sort_by, sort_order
```

**Get Import Log**
```
GET /curb/logs/{log_id}
```

## Celery Tasks

### Scheduled Tasks

All tasks are configured in `app/worker/config.py`:

**fetch_and_import_curb_trips**
- Schedule: Daily at 2 AM
- Fetches trips from last 24 hours
- Imports new trips into database
- No reconciliation or posting

**reconcile_curb_trips**
- Schedule: Daily at 3 AM
- Reconciles unreconciled trips
- Environment-aware (local vs server)

**post_curb_trips**
- Schedule: Daily at 4 AM
- Posts reconciled trips to ledger
- Associates with active leases

**process_curb_trips_full**
- Not scheduled by default
- Runs complete workflow (fetch → reconcile → post)
- Useful for manual processing

**manual_fetch_curb_trips**
- Not scheduled
- Fetches trips for custom date range
- Useful for backfilling data

### Task Execution

```python
from app.curb.tasks import fetch_and_import_curb_trips, reconcile_curb_trips

# Run async (queued)
result = fetch_and_import_curb_trips.delay()

# Run sync (immediate)
result = fetch_and_import_curb_trips.apply()

# Get result
data = result.get()
```

## Configuration

### Environment Variables

Required environment variables in `.env`:

```env
# CURB API Configuration
CURB_URL=https://api.taxitronic.org/vts_service/taxi_service.asmx
CURB_MERCHANT=your_merchant_id
CURB_USERNAME=your_username
CURB_PASSWORD=your_password

# Environment (affects reconciliation behavior)
ENVIRONMENT=development  # development, uat, or production

# Database (async SQLAlchemy)
DATABASE_URL=postgresql+asyncpg://user:pass@host/db

# Redis (Celery)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_USERNAME=
REDIS_PASSWORD=
```

### Reconciliation Behavior

The module has environment-aware reconciliation:

**Development / UAT:**
- Reconciliation is LOCAL only
- No CURB API calls made
- Trips marked as reconciled in local database
- Useful for testing without affecting production data

**Production:**
- Reconciliation calls CURB API
- Trips marked as reconciled on CURB server
- Local database updated after successful API call
- Receipt numbers (recon_stat) must be unique

## Usage Examples

### Starting Workers

```bash
# Start Celery worker
celery -A app.core.celery_app worker --loglevel=info

# Start Celery beat (scheduler)
celery -A app.core.celery_app beat --loglevel=info
```

### Manual Import via API

```python
import httpx

# Import trips
response = httpx.post(
    "http://localhost:8000/curb/import",
    params={
        "from_date": "01/01/2025",
        "to_date": "01/31/2025"
    },
    headers={"Authorization": "Bearer <token>"}
)
result = response.json()
print(f"Imported {result['success_count']} trips")
```

### Manual Task Execution

```python
from app.curb.tasks import manual_fetch_curb_trips

# Fetch specific date range
result = manual_fetch_curb_trips.delay(
    from_date="01/01/2025",
    to_date="01/31/2025",
    driver_id="DRV123",
    import_by="admin"
)

# Wait for completion
data = result.get(timeout=300)
print(data)
```

### Querying Trips

```python
from app.curb.repository import CURBRepository
from app.curb.schemas import CURBTripFilters
from app.core.db import get_async_db

async def get_unreconciled_trips():
    async for db in get_async_db():
        repo = CURBRepository(db)
        
        filters = CURBTripFilters(
            is_reconciled=False,
            start_date_from=date(2025, 1, 1),
            page=1,
            per_page=100
        )
        
        trips, total = await repo.get_trips(filters)
        print(f"Found {total} unreconciled trips")
        return trips
```

## Error Handling

### Custom Exceptions

All operations use custom exceptions from `app/curb/exceptions.py`:

- `CURBTripNotFoundException`
- `CURBImportLogNotFoundException`
- `CURBFileValidationException`
- `CURBImportException`
- `CURBReconciliationException`
- `CURBAssociationException`
- `CURBPostingException`
- `CURBExportException`
- `CURBUpdateException`
- `CURBSOAPException`
- `CURBXMLParseException`
- `CURBDuplicateTripException`

### Error Logging

All operations include comprehensive logging:

```python
logger.info("Operation started", param1=value1)
logger.error("Operation failed", error=str(e), exc_info=True)
```

## Testing

### Unit Tests

```bash
pytest tests/curb/test_repository.py
pytest tests/curb/test_services.py
pytest tests/curb/test_soap_client.py
```

### Integration Tests

```bash
pytest tests/curb/test_integration.py
```

### Manual Testing

Use the Swagger UI at `http://localhost:8000/docs` to test API endpoints interactively.

## Monitoring

### Task Monitoring

Use Celery Flower for task monitoring:

```bash
celery -A app.core.celery_app flower
```

Access at: `http://localhost:5555`

### Database Queries

```sql
-- Check import logs
SELECT * FROM curb_import_logs ORDER BY import_start DESC LIMIT 10;

-- Check trip statistics
SELECT 
    status,
    COUNT(*) as count,
    SUM(total_amount) as total_revenue
FROM curb_trips
WHERE start_date >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY status;

-- Check reconciliation status
SELECT 
    is_reconciled,
    is_posted,
    COUNT(*) as count
FROM curb_trips
GROUP BY is_reconciled, is_posted;
```

## Migration from Old Module

If migrating from the old synchronous CURB module:

1. **Update imports**:
   ```python
   # Old
   from app.curb.services import curb_service
   
   # New
   from app.curb.services import CURBService
   from app.curb.repository import CURBRepository
   ```

2. **Update to async**:
   ```python
   # Old (sync)
   def process_trips():
       result = curb_service.import_curb_trips(db, xml_data)
   
   # New (async)
   async def process_trips():
       async for db in get_async_db():
           repo = CURBRepository(db)
           service = CURBService(repo)
           result = await service.import_trips(xml_data)
   ```

3. **Update task names**:
   ```python
   # Old
   from app.curb.tasks import fetch_and_reconcile_curb_trips
   
   # New
   from app.curb.tasks import fetch_and_import_curb_trips, reconcile_curb_trips
   ```

4. **Update Celery schedule** in `app/worker/config.py`

5. **Run database migrations** to update schema

## Troubleshooting

### Common Issues

**Issue: Tasks not running**
- Check Celery worker and beat are running
- Verify Redis connection
- Check task names in beat schedule

**Issue: SOAP API errors**
- Verify CURB credentials in `.env`
- Check API URL and network connectivity
- Review SOAP client logs for details

**Issue: Database errors**
- Check async database connection string
- Verify SQLAlchemy 2.x compatibility
- Review migration status

**Issue: Import failures**
- Check for duplicate records
- Verify XML parsing
- Review import log error_summary

**Issue: Reconciliation failures**
- Check environment variable (dev vs production)
- Verify CURB API access (production only)
- Review trip status before reconciliation

### Debug Mode

Enable debug logging in `.env`:

```env
LOG_LEVEL=DEBUG
```

Run tasks synchronously for debugging:

```python
from app.curb.tasks import fetch_and_import_curb_trips

result = fetch_and_import_curb_trips.apply()
print(result.get())
```

## Performance Optimization

### Bulk Operations

The module uses bulk operations for efficiency:

- `bulk_create_trips()`: Insert multiple trips in one transaction
- `bulk_create_reconciliations()`: Create multiple reconciliation records

### Database Indexes

Optimized indexes on:
- `record_id`, `period` (composite for uniqueness)
- `start_date`, `end_date` (date range queries)
- `cab_number`, `driver_id` (filtering)
- `is_reconciled`, `is_posted` (status queries)

### Connection Pooling

Async SQLAlchemy uses connection pooling by default. Configure in `app/core/db.py`:

```python
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=0
)
```

## Security

- **API Authentication**: All endpoints require authentication
- **Environment Variables**: Sensitive data not in code
- **SQL Injection Protection**: Parameterized queries via SQLAlchemy
- **Input Validation**: Pydantic schemas validate all inputs
- **Error Handling**: No sensitive data in error messages

## Contributing

When adding new features:

1. Follow the existing patterns (models → repository → services → router)
2. Use async/await consistently
3. Add type hints to all functions
4. Write comprehensive docstrings
5. Add logging for important operations
6. Include error handling with custom exceptions
7. Update schemas for API changes
8. Write tests for new functionality
9. Update this README

## References

- [CURB API Documentation](./CURB_API_Documentation.pdf)
- [SQLAlchemy 2.x Documentation](https://docs.sqlalchemy.org/en/20/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Celery Documentation](https://docs.celeryproject.org/)