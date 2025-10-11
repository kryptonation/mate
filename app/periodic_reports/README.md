# Periodic Reports Module

## Overview

The Periodic Reports module provides a comprehensive system for configuring, generating, and managing automated reports in the Big Apple Taxi (BAT) management system. This module supports various report types, flexible scheduling, multiple output formats, and automated distribution via email.

## Features

### Report Configuration
- **Multiple Report Types**: Driver summaries, medallion status, vehicle inspections, financial reports, and more
- **Flexible Scheduling**: Daily, weekly, monthly, quarterly, yearly, or on-demand generation
- **Customizable Parameters**: Filter and configure reports with custom parameters
- **Multiple Output Formats**: Excel (primary format with enhanced formatting), PDF, CSV, and JSON support
- **Email Distribution**: Automated email delivery to configured recipients

### Report Management
- **Status Tracking**: Monitor report generation status and execution time
- **Error Handling**: Automatic retry mechanisms for failed reports
- **File Management**: Organized storage and cleanup of generated reports
- **Audit Trail**: Complete audit logging of all report activities

### Background Processing
- **Celery Integration**: Asynchronous report generation using Celery workers
- **Scheduled Execution**: Automatic execution based on configured schedules
- **Resource Management**: Efficient handling of large report generation tasks

## API Endpoints

### Report Configuration Management

#### Get Report Types
```http
GET /reports/types
```
Returns all available report types with metadata, supported formats, and parameters.

#### Create Report Configuration
```http
POST /reports/configurations
```
Create a new report configuration with scheduling and parameters.

#### Get Report Configurations
```http
GET /reports/configurations?report_type=driver_summary&is_active=true
```
Retrieve report configurations with optional filtering.

#### Update Report Configuration
```http
PUT /reports/configurations/{config_id}
```
Update an existing report configuration.

#### Delete Report Configuration
```http
DELETE /reports/configurations/{config_id}
```
Deactivate a report configuration.

### Report Generation

#### Generate Report On-Demand
```http
POST /reports/generate
```
Generate a report immediately based on a configuration.

#### Execute Report Immediately
```http
POST /reports/execute
```
Execute a report without a saved configuration (temporary execution).

#### Bulk Generate Reports
```http
POST /reports/bulk-generate
```
Generate multiple reports in bulk.

### Generated Report Management

#### Get Generated Reports
```http
GET /reports/generated?status=completed&start_date=2025-01-01
```
Retrieve generated reports with filtering options.

#### Download Report
```http
GET /reports/generated/{report_id}/download
```
Download a generated report file.

## Report Types

### Available Report Types

1. **Driver Summary** (`driver_summary`)
   - New driver registrations
   - Driver status changes
   - Driver activity summaries

2. **Medallion Status** (`medallion_status`)
   - Current medallion ownership
   - Storage activities
   - Status changes

3. **Vehicle Inspection** (`vehicle_inspection`)
   - Upcoming inspection due dates
   - Compliance status
   - Inspection history

4. **Financial Summary** (`financial_summary`)
   - Transaction summaries
   - Payment status
   - Outstanding balances

5. **Lease Expiry** (`lease_expiry`)
   - Upcoming lease expirations
   - Renewal requirements
   - Lease status

6. **Violation Summary** (`violation_summary`)
   - Parking violations
   - Payment status
   - Driver assignments

7. **EZPass Transactions** (`ezpass_transactions`)
   - Toll transactions
   - Reconciliation status
   - Driver associations

8. **Trip Analytics** (`trip_analytics`)
   - Trip data analysis
   - Driver performance metrics
   - Revenue analytics

9. **SLA Performance** (`sla_performance`)
   - SLA compliance metrics
   - Case processing times
   - Performance trends

10. **Audit Trail Summary** (`audit_trail_summary`)
    - System activity summaries
    - User action logs
    - Security events

## Configuration Examples

### Daily Driver Summary Report
```json
{
  "name": "Daily Driver Summary",
  "description": "Daily summary of driver activities",
  "report_type": "driver_summary",
  "frequency": "daily",
  "schedule_time": "08:00",
  "output_format": "pdf",
  "email_recipients": ["manager@company.com"],
  "auto_email": true,
  "parameters": {
    "include_inactive": false,
    "summary_period_days": 1
  }
}
```

### Weekly Financial Report
```json
{
  "name": "Weekly Financial Summary",
  "description": "Weekly financial overview",
  "report_type": "financial_summary",
  "frequency": "weekly",
  "schedule_time": "09:00",
  "schedule_day_of_week": 1,
  "output_format": "excel",
  "email_recipients": ["finance@company.com", "accounting@company.com"],
  "auto_email": true
}
```

### Monthly Vehicle Inspection Report
```json
{
  "name": "Monthly Vehicle Inspection",
  "description": "Vehicle compliance and inspection status",
  "report_type": "vehicle_inspection",
  "frequency": "monthly",
  "schedule_time": "07:00",
  "schedule_day_of_month": 1,
  "output_format": "pdf",
  "parameters": {
    "inspection_due_days": 30,
    "include_compliant": true
  }
}
```

## Setup and Configuration

### 1. Database Migration
Run the database migration to create the required tables:
```bash
alembic upgrade add_periodic_reports
```

### 2. Celery Worker Setup
Start Celery workers for report processing:
```bash
celery -A app.periodic_reports.tasks worker --loglevel=info --queue=reports
```

### 3. Celery Beat Scheduler
Start the Celery beat scheduler for automatic report execution:
```bash
celery -A app.periodic_reports.tasks beat --loglevel=info
```

### 4. Environment Configuration
Configure the following environment variables:
```env
# Report storage
DOCUMENT_STORAGE_DIR=/path/to/reports

# Email configuration
AWS_SES_SENDER_EMAIL=reports@company.com
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# Redis configuration (for Celery)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_USERNAME=
REDIS_PASSWORD=
```

## Usage Examples

### Creating a Report Configuration
```python
from app.periodic_reports.schemas import ReportConfigurationCreate
from app.periodic_reports.models import ReportType, ReportFrequency, ReportFormat

config_data = ReportConfigurationCreate(
    name="Daily Driver Activity",
    description="Daily report of driver registrations and status changes",
    report_type=ReportType.DRIVER_SUMMARY,
    frequency=ReportFrequency.DAILY,
    schedule_time="08:00",
    output_format=ReportFormat.PDF,
    email_recipients=["manager@company.com"],
    parameters={
        "include_inactive": False,
        "summary_period_days": 1
    }
)
```

### Generating a Report On-Demand
```python
from app.periodic_reports.schemas import GenerateReportRequest
from datetime import date

request = GenerateReportRequest(
    configuration_id=1,
    report_period_start=date(2025, 1, 1),
    report_period_end=date(2025, 1, 31),
    send_email=True
)
```

## Monitoring and Maintenance

### Celery Tasks
The module includes several Celery tasks for maintenance:

1. **Report Generation** (`generate_report_task`)
   - Generates individual reports
   - Handles retries on failure
   - Sends email notifications

2. **Scheduled Reports** (`generate_scheduled_reports_task`)
   - Checks for due reports every 15 minutes
   - Queues report generation tasks

3. **Cleanup** (`cleanup_old_reports_task`)
   - Removes old report files (90+ days)
   - Runs daily at 2 AM

4. **Weekly Summary** (`send_weekly_summary_task`)
   - Sends summary of report activities
   - Runs weekly on Mondays

5. **Retry Failed Reports** (`retry_failed_reports_task`)
   - Retries failed report generations
   - Runs periodically for recovery

### Monitoring
Monitor the system using:
- Celery Flower for task monitoring
- Database queries for report status
- Log files for error tracking
- Email notifications for failures

## Troubleshooting

### Common Issues

1. **Reports Not Generating**
   - Check Celery worker status
   - Verify database connections
   - Check configuration validity

2. **Email Not Sending**
   - Verify AWS SES configuration
   - Check recipient email addresses
   - Review email service logs

3. **File Storage Issues**
   - Verify directory permissions
   - Check available disk space
   - Ensure storage path configuration

4. **Performance Issues**
   - Monitor Celery queue length
   - Optimize report parameters
   - Consider worker scaling

### Debugging
Enable debug logging:
```python
import logging
logging.getLogger("Periodic Reports").setLevel(logging.DEBUG)
```

## Security Considerations

- **Access Control**: Reports are protected by user authentication and authorization
- **Data Filtering**: Reports respect user permissions and data access rules
- **File Security**: Generated reports are stored securely with appropriate permissions
- **Audit Logging**: All report activities are logged for compliance and security monitoring

## Performance Optimization

- **Background Processing**: All report generation is asynchronous
- **Database Optimization**: Efficient queries with proper indexing
- **File Management**: Automatic cleanup of old reports
- **Resource Management**: Configurable worker pools and task limits

## Future Enhancements

- **Advanced Scheduling**: Support for complex scheduling patterns
- **Custom Templates**: User-defined report templates
- **Data Visualization**: Charts and graphs in reports
- **Real-time Reports**: Live data streaming for dynamic reports
- **Report Sharing**: Secure report sharing with external users

## Integration Status ✅

### Celery Integration
- **✅ Worker Integration**: Uses shared Celery app from `app.worker.app`
- **✅ Task Discovery**: Added to autodiscover_tasks in worker configuration
- **✅ Beat Schedule**: Automated scheduling configured in `app.worker.config`
  - `scheduled-reports`: Runs every 15 minutes to check for due reports
  - `cleanup-old-reports`: Daily cleanup at 2 AM UTC
  - `weekly-summary`: Weekly summary emails on Mondays at 9 AM UTC

### S3 Integration
- **✅ File Upload**: Reports uploaded to S3 using `app.utils.s3_utils`
- **✅ File Download**: Presigned URLs for secure access
- **✅ File Cleanup**: Old reports deleted from S3 during cleanup
- **✅ Email Distribution**: Download links sent via email for S3-stored files

### Database Integration
- **✅ Models**: Integrated with existing SQLAlchemy setup
- **✅ Migration**: Alembic migration script created
- **✅ Audit Trail**: Report generation and downloads logged

### API Integration
- **✅ FastAPI Router**: Added to main application
- **✅ Authentication**: Uses existing user authentication
- **✅ Error Handling**: Consistent with application patterns

## Deployment Verification

### Pre-deployment Checklist
1. **✅ Dependencies**: All imports verified and working
2. **✅ Database Migration**: Run `alembic upgrade head` 
3. **✅ Environment Variables**: S3 and email configuration required
4. **✅ Celery Worker**: Restart workers to register new tasks
5. **✅ Beat Scheduler**: Restart beat scheduler for new schedule

### Testing Commands
```bash
# Test imports
python -c "from app.periodic_reports import tasks, models, services"

# Test Celery task registration
celery -A app.worker.app inspect registered

# Test S3 connectivity (if configured)
python -c "from app.utils.s3_utils import s3_utils; print(s3_utils.bucket_name)"
```

### Excel Report Features
- **Professional Formatting**: Headers with corporate styling, borders, and color schemes
- **Multiple Worksheets**: Summary sheet plus dedicated data sheets for each report section
- **Auto-sizing Columns**: Automatically adjusted column widths for optimal viewing
- **Data Visualization**: Automatic chart generation for numerical data when applicable
- **Summary Dashboard**: Dedicated analytics worksheet with key metrics visualization
- **Business-friendly Layout**: Clean, printable format suitable for stakeholder distribution
