# Vehicle Repairs Module

This module manages the full lifecycle of vehicle repair expenses charged to drivers in the BAT Connect system.

## Overview

The Repairs module handles:

1. **Invoice Capture**: Create and store detailed repair invoices for each vehicle/driver
2. **Payment Plan Creation**: Automatically generate weekly repayment schedules using the Repair Payment Matrix
3. **Installment Deduction**: Deduct only the scheduled weekly installment from the driver's DTR
4. **Balance Management**: Carry forward unpaid balances until the invoice is fully settled
5. **Driver Transparency**: Show only weekly deductions in driver-facing DTR while BAT tracks full invoice details

## Architecture

### Technology Stack

- **SQLAlchemy 2.x**: ORM with async support
- **FastAPI**: Async REST API endpoints
- **Celery**: Task queue for automated installment posting
- **Pydantic**: Schema validation

### Module Structure

```
app/repairs/
├── __init__.py              # Module exports
├── models.py                # SQLAlchemy 2.x models
├── schemas.py               # Pydantic schemas
├── repository.py            # Data access layer (async)
├── services.py              # Business logic layer (async)
├── router.py                # FastAPI endpoints (async)
├── tasks.py                 # Celery tasks
├── utils.py                 # Payment matrix and utilities
├── exceptions.py            # Custom exceptions
└── README.md                # This file
```

### Design Patterns

- **Repository Pattern**: Data access abstraction
- **Service Layer**: Business logic separation
- **Dependency Injection**: Clean dependencies between layers
- **Async/Await**: Non-blocking I/O operations
- **Task Queue**: Automated background processing

## Models

### RepairInvoice

Main invoice model representing the overall repair obligation:

**Identifiers:**
- `id`: Primary key
- `repair_id`: System-generated unique ID (e.g., RPR-2025-001)

**Invoice Details:**
- `invoice_number`: Workshop invoice number
- `invoice_date`: Date repair was billed
- `workshop_type`: Big Apple Workshop or External Workshop

**Vehicle & Driver:**
- `vin`: Vehicle Identification Number
- `plate_number`: Vehicle plate
- `medallion_number`: Associated medallion
- `hack_license_number`: Driver's TLC license
- `driver_id`, `vehicle_id`, `medallion_id`, `lease_id`: Foreign keys

**Financial:**
- `repair_amount`: Total repair cost
- `weekly_installment`: Calculated from payment matrix
- `balance`: Remaining unpaid amount

**Status & Lifecycle:**
- `status`: Draft, Open, Closed, Hold, Cancelled
- `start_week`: Current or Next Payment Period

### RepairInstallment

Individual weekly installments derived from invoice:

**Identifiers:**
- `id`: Primary key
- `installment_id`: Unique ID (e.g., RPR-2025-001-01)
- `repair_invoice_id`: Foreign key to invoice

**Payment Period:**
- `week_start_date`: Sunday 00:00:00
- `week_end_date`: Saturday 23:59:59

**Financial:**
- `payment_amount`: Installment due this week
- `prior_balance`: Carried forward balance
- `balance`: Remaining after this payment

**Ledger Integration:**
- `ledger_posting_ref`: Reference to ledger entry (null until posted)
- `status`: Scheduled, Due, Posted, Paid

## Payment Matrix

The system uses a tiered payment matrix to calculate weekly installments:

| Repair Amount | Weekly Installment |
|---------------|-------------------|
| $0 – $200 | Full amount (paid in full) |
| $201 – $500 | $100 per week |
| $501 – $1,000 | $200 per week |
| $1,001 – $3,000 | $250 per week |
| > $3,000 | $300 per week |

**Example:**
- Repair: $1,200
- Matrix: $250/week (since $1,001-$3,000)
- Schedule: $250, $250, $250, $250, $200 (final adjusted)

## Workflow

### 1. Create Invoice (Draft Status)

```python
POST /repairs/invoices
{
    "invoice_number": "EXT-4589",
    "invoice_date": "2025-10-01",
    "vin": "1HGBH41JXMN109186",
    "plate_number": "ABC123",
    "medallion_number": "2A34",
    "hack_license_number": "1234567",
    "driver_id": 42,
    "vehicle_id": 15,
    "medallion_id": 8,
    "workshop_type": "External Workshop",
    "repair_description": "Brake System Overhaul",
    "repair_amount": 1200.00,
    "start_week": "Current Payment Period"
}
```

**System Actions:**
1. Validates invoice data
2. Checks for duplicates
3. Generates unique `repair_id`
4. Calculates `weekly_installment` from matrix
5. Generates complete payment schedule
6. Creates invoice in DRAFT status
7. Creates all installment records in SCHEDULED status

### 2. Confirm Invoice (Open Status)

```python
POST /repairs/invoices/{invoice_id}/confirm
```

**System Actions:**
1. Transitions invoice from DRAFT → OPEN
2. Activates payment schedule
3. Installments become eligible for posting

### 3. Automated Posting (Sunday 05:00 AM)

**Celery Task:** `process_scheduled_repair_installments`

**System Actions:**
1. Finds installments with status=SCHEDULED and week_start_date ≤ today
2. For each installment:
   - Creates ledger entry (PLACEHOLDER - to be implemented)
   - Updates status to POSTED
   - Sets `ledger_posting_ref`
   - Updates invoice balance
3. Closes invoice if all installments posted and balance = 0

### 4. DTR Integration (Future)

When integrated with DTR:
- Weekly installment appears as "Repair - Invoice {number}"
- Shows: This Week's Deduction, Prior Balance, Remaining Balance
- Optional: Original Invoice Amount, Total Paid Till Date

## State Transitions

### Invoice States

```
Draft → Open → Closed
  ↓       ↓
Cancelled Hold → Open/Cancelled
```

**Valid Transitions:**
- Draft → Open (confirm invoice)
- Draft → Cancelled (cancel before confirmation)
- Open → Closed (all installments paid)
- Open → Hold (flag for review)
- Hold → Open (clear hold)
- Hold → Cancelled (if no postings)

### Installment States

```
Scheduled → Due → Posted → Paid
```

**Transitions:**
- Scheduled: Created but payment period not started
- Due: Payment period started (Sunday 00:00)
- Posted: Ledger entry created (Sunday 05:00)
- Paid: Fully reconciled in ledger

## API Endpoints

### Invoice Operations

- `POST /repairs/invoices` - Create new invoice
- `GET /repairs/invoices` - List invoices (paginated, filtered)
- `GET /repairs/invoices/{id}` - Get specific invoice
- `GET /repairs/invoices/repair-id/{repair_id}` - Get by repair_id
- `PUT /repairs/invoices/{id}` - Update invoice
- `POST /repairs/invoices/{id}/confirm` - Confirm draft
- `POST /repairs/invoices/{id}/hold` - Put on hold
- `POST /repairs/invoices/{id}/cancel` - Cancel invoice

### Installment Operations

- `GET /repairs/installments` - List installments (paginated, filtered)
- `GET /repairs/installments/{id}` - Get specific installment
- `GET /repairs/invoices/{id}/installments` - Get all installments for invoice

### Posting Operations

- `POST /repairs/post` - Manually trigger posting (admin)

### Statistics

- `GET /repairs/statistics` - Overall repair statistics
- `GET /repairs/drivers/{id}/summary` - Driver-specific summary

## Validation Rules

### Invoice Level

1. **Mandatory Fields**: invoice_number, invoice_date, workshop_type, repair_amount
2. **Unique Constraint**: invoice_number + vehicle_id + invoice_date must be unique
3. **Date Validation**: invoice_date must be ≤ today
4. **Amount Validation**: repair_amount must be ≥ $1
5. **State Transitions**: Must follow valid state transition rules

### Payment Schedule

1. **Matrix Compliance**: Installments follow payment matrix (except final)
2. **Continuity**: No gaps/overlaps in installment periods
3. **Balance Accuracy**: Sum of installments = repair_amount
4. **Period Alignment**: week_start = Sunday, week_end = Saturday

### Posting

1. **Timing**: Installments posted only when payment period starts
2. **Ledger Link**: Every posted installment has ledger_posting_ref
3. **Immutability**: Posted installments cannot be deleted
4. **Reconciliation**: Repairs in DTR must match ledger postings

## Error Handling

The module uses a custom exception hierarchy:

- `RepairBaseException`: Base for all repair errors
- `RepairNotFoundException`: Invoice/installment not found (404)
- `DuplicateInvoiceException`: Invoice already exists (409)
- `InvalidRepairAmountException`: Invalid amount (400)
- `InvalidPaymentScheduleException`: Schedule generation failed (400)
- `RepairStateException`: Invalid state transition (500)
- `RepairCancellationException`: Cannot cancel (500)

## Future Enhancements

### Ledger Integration

Currently, ledger posting is a placeholder. Future implementation will:

1. Create actual ledger entries with proper debit/credit structure
2. Link to driver accounts
3. Reconcile with DTR balances
4. Support payment reversals and adjustments

### OCR Processing

Future implementation for invoice upload:

1. Upload invoice PDF/image
2. OCR extracts: invoice_number, date, amount
3. Staff reviews and confirms extracted data
4. Auto-populates form fields

### Advanced Features

- **Payment Plans**: Custom payment schedules for special cases
- **Partial Payments**: Accept partial installment payments
- **Deferred Start**: Start payments after X weeks
- **Early Payoff**: Discount for paying full amount early
- **Dispute Management**: Workflow for challenging invoices
- **Reporting**: Detailed repair cost analytics

## Database Migration

To add this module to the database:

```bash
# Generate migration
alembic revision --autogenerate -m "Add vehicle repairs module"

# Review migration file
# Edit if needed

# Apply migration
alembic upgrade head
```

## Testing

### Unit Tests

Test individual components:

```python
# Test payment matrix calculation
assert calculate_weekly_installment(150) == 150  # Full amount
assert calculate_weekly_installment(350) == 100  # $100/week
assert calculate_weekly_installment(750) == 200  # $200/week

# Test schedule generation
schedule = generate_payment_schedule(1200, date(2025, 10, 1))
assert len(schedule) == 5  # 4x$250 + 1x$200
assert schedule[-1]["payment_amount"] == 200  # Final adjusted
```

### Integration Tests

Test API endpoints:

```python
# Create invoice
response = client.post("/repairs/invoices", json=invoice_data)
assert response.status_code == 201

# Confirm invoice
response = client.post(f"/repairs/invoices/{invoice_id}/confirm")
assert response.status_code == 200

# Post installments
response = client.post("/repairs/post")
assert response.json()["posted_count"] > 0
```

## Configuration

### Celery Schedule

Add to `celery_config.py`:

```python
CELERYBEAT_SCHEDULE = {
    'post-repair-installments': {
        'task': 'repairs.process_scheduled_installments',
        'schedule': crontab(day_of_week=0, hour=5, minute=0),  # Sunday 05:00
    },
    'close-paid-invoices': {
        'task': 'repairs.close_fully_paid_invoices',
        'schedule': crontab(hour=6, minute=0),  # Daily 06:00
    },
}
```

### Router Registration

Add to `app/main.py`:

```python
from app.repairs.router import router as repairs_routes

bat_app.include_router(repairs_routes)
```

## Best Practices

1. **Always create invoices in DRAFT** - Review before confirming
2. **Validate data thoroughly** - Check for duplicates and invalid amounts
3. **Monitor posting results** - Review daily posting logs
4. **Handle holds carefully** - Document reason for holds
5. **Don't delete posted installments** - Use reversals instead
6. **Keep audit trail** - Track all state changes

## Support

For questions or issues:
- Check logs: `/var/log/batm_app.log`
- Review Celery task results
- Contact development team

## License

Internal BAT Connect module - Proprietary