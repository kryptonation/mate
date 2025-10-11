# CURB Trip Processing System

This module handles the automated processing of CURB (taxi meter) trip data, including fetching trips from the CURB API, importing them into the database, reconciling them locally, and posting them to ledgers.

## Overview

The CURB system processes taxi trip data through the following workflow:

1. **Fetch**: Retrieve trip data from the CURB API for the last 24 hours
2. **Import**: Store new trips in the database, avoiding duplicates
3. **Reconcile**: Mark trips as reconciled locally in your database (no remote API calls)
4. **Post**: Associate trips with leases and create ledger entries

## Architecture

### Models

- `CURBTrip`: Main trip data model
- `CURBImportLog`: Tracks import operations
- `CURBTripReconcilation`: Tracks reconciliation operations

### Services

- `CURBService`: Main service class handling all CURB operations
- `curb_service`: Singleton instance of the service

### Tasks

- `fetch_and_reconcile_curb_trips`: Main task that runs every 24 hours
- `reconcile_curb_trips_only`: Task to reconcile existing trips only
- `post_curb_trips_only`: Task to post reconciled trips to ledgers only

## Configuration

### Environment Variables

The following environment variables must be set in your `.env` file:

```env
# CURB API Configuration
CURB_URL=https://api.curb.com/soap
CURB_MERCHANT=your_merchant_id
CURB_USERNAME=your_username
CURB_PASSWORD=your_password

# Redis Configuration (for Celery)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_USERNAME=
REDIS_PASSWORD=
```

### Celery Configuration

The CURB tasks are configured to run automatically via Celery Beat:

- **Main Task**: `fetch_and_reconcile_curb_trips` runs every 24 hours at 2 AM UTC
- **Worker**: Uses Redis as broker and result backend
- **Concurrency**: Configurable via worker settings

## Usage

### Automatic Execution

The main task runs automatically every 24 hours. To start the automated processing:

1. Start the Celery worker:
   ```bash
   celery -A app.core.celery_app worker --loglevel=info
   ```

2. Start the Celery beat scheduler:
   ```bash
   celery -A app.core.celery_app beat --loglevel=info
   ```

### Manual Execution

You can also run tasks manually:

```python
from app.curb.tasks import fetch_and_reconcile_curb_trips

# Run the main task
result = fetch_and_reconcile_curb_trips.delay()

# Check the result
print(result.get())
```

### Individual Tasks

```python
from app.curb.tasks import reconcile_curb_trips_only, post_curb_trips_only

# Reconcile trips only
reconcile_curb_trips_only.delay()

# Post trips only
post_curb_trips_only.delay()

# Reconcile with specific receipt number
reconcile_curb_trips_only.delay(recon_stat=12345)
```

## Task Details

### fetch_and_reconcile_curb_trips

**Purpose**: Main task that orchestrates the entire CURB processing workflow.

**Schedule**: Runs every 24 hours at 2 AM UTC

**Process**:
1. Fetches trips from CURB API for the last 24 hours
2. Imports new trips into the database (deduplicates by record_id and period)
3. Reconciles unreconciled trips with the CURB system
4. Associates trips with active leases and posts to ledgers

**Returns**: Summary of processing results including import and posting statistics

### reconcile_curb_trips_only

**Purpose**: Reconcile existing unreconciled trips locally without fetching new data or calling remote API.

**Parameters**:
- `recon_stat` (Optional[int]): Receipt number for reconciliation. If None, uses timestamp.

**Process**:
1. Queries for unreconciled trips in local database
2. Updates trip status as reconciled locally
3. Creates local reconciliation records
4. No remote API calls are made

### post_curb_trips_only

**Purpose**: Post already reconciled trips to ledgers without reconciliation.

**Process**:
1. Queries for reconciled but unposted trips
2. Associates trips with active leases
3. Creates ledger entries
4. Marks trips as posted

## Database Schema

### CURBTrip
- `id`: Primary key
- `record_id`: CURB record identifier
- `period`: Trip period
- `cab_number`: Vehicle plate number
- `driver_id`: Driver identifier
- `start_date`, `end_date`: Trip dates
- `start_time`, `end_time`: Trip times
- `total_amount`: Trip total amount
- `is_reconciled`: Reconciliation status
- `is_posted`: Posting status
- `recon_stat`: Reconciliation receipt number

### CURBImportLog
- `id`: Primary key
- `imported_by`: User who initiated import
- `import_start`, `import_end`: Import timestamps
- `import_source`: Source of import (SOAP, Upload, etc.)
- `total_records`: Number of records processed
- `status`: Import status

### CURBTripReconcilation
- `id`: Primary key
- `trip_id`: Reference to CURBTrip
- `recon_stat`: Reconciliation receipt number
- `reconciled_at`: Reconciliation timestamp
- `reconciled_by`: User who performed reconciliation

## Error Handling

The tasks include comprehensive error handling:

- **Database errors**: Logged and re-raised
- **API errors**: Logged with full stack traces
- **Validation errors**: Caught and logged
- **Network timeouts**: Handled with retry logic

## Monitoring

### Logs

All operations are logged with task IDs for tracking:

```
[Task ID: abc123] Starting CURB trip fetch and reconciliation process
[Task ID: abc123] Retrieved 150 trip records from CURB API
[Task ID: abc123] Imported 45 new trips, 105 total processed
[Task ID: abc123] Reconciled 45 trips
[Task ID: abc123] Posted 40 trips to ledgers
```

### Metrics

The tasks return detailed metrics:

```json
{
  "status": "success",
  "task_id": "abc123",
  "import_result": {
    "inserted": 45,
    "total": 105
  },
  "post_result": {
    "posted_count": 40,
    "skipped": [{"trip_id": 123, "reason": "Lease not found"}],
    "errors": []
  },
  "processed_at": "2024-01-15T02:00:00"
}
```

## Testing

Run the test script to verify the setup:

```bash
cd backend/src
python test_curb_tasks.py
```

This will test:
- Task imports
- Celery app configuration
- Service imports
- Model imports

## Troubleshooting

### Common Issues

1. **Task not running**: Check Celery worker and beat are running
2. **API errors**: Verify CURB credentials in environment variables
3. **Database errors**: Check database connection and permissions
4. **Import failures**: Check for duplicate records or validation errors

### Debug Mode

To run tasks in debug mode:

```python
from app.curb.tasks import fetch_and_reconcile_curb_trips

# Run synchronously for debugging
result = fetch_and_reconcile_curb_trips.apply()
print(result.get())
```

## Dependencies

- `celery`: Task queue framework
- `redis`: Message broker and result backend
- `sqlalchemy`: Database ORM
- `requests`: HTTP client for CURB API
- `lxml`: XML parsing for SOAP responses

## Security

- CURB credentials are stored in environment variables
- Database connections use connection pooling
- All API calls include timeout handling
- Error messages don't expose sensitive information 