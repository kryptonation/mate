# Excel Reports - Technical Documentation

## Overview
The periodic reports module prioritizes Excel as the primary output format, providing enhanced business reporting capabilities with professional formatting, multiple worksheets, and data visualization.

## Excel Generation Features

### 1. Professional Formatting
- **Corporate Styling**: Blue header backgrounds (#366092) with white text
- **Borders and Alignment**: Consistent cell borders and center alignment for headers
- **Auto-sizing**: Automatic column width adjustment based on content
- **Font Styling**: Bold headers and clear data presentation

### 2. Multi-Worksheet Structure
- **Summary Sheet**: Report metadata and key statistics
- **Data Sheets**: Dedicated worksheets for each data table
- **Analytics Dashboard**: Charts and visualizations (when applicable)

### 3. Data Visualization
- **Automatic Charts**: Bar charts for numerical data (datasets ≤50 rows)
- **Summary Metrics**: Visual representation of key performance indicators
- **Chart Positioning**: Smart placement to the right of data tables

### 4. Technical Implementation

#### Dependencies
```python
pandas>=2.2.3           # Data manipulation and Excel writing
openpyxl>=3.1.5         # Excel file format support
```

#### Key Function: `_create_excel_report()`
Located in: `app/periodic_reports/tasks.py`

**Features:**
- Creates workbook with multiple sheets
- Applies professional styling
- Handles datetime formatting
- Generates charts for numerical data
- Error handling for chart creation

#### Content Type
- MIME Type: `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`
- File Extension: `.xlsx`

### 5. Worksheet Layout

#### Summary Sheet
```
Row 1: "Report Information" (title)
Row 2: Report Name | [Configuration Name]
Row 3: Report Type | [Type Name]
Row 4: Generated On | [Timestamp]
Row 5: Period Start | [Start Date]
Row 6: Period End | [End Date]
Row 7: (empty)
Row 8: "Summary Statistics" (section header)
Row 9+: [Statistic Name] | [Value]
```

#### Data Sheets
```
Row 1: [Sheet Title]
Row 2: (empty)
Row 3: [Column Headers] (formatted)
Row 4+: [Data Rows]
[Chart positioned to the right if applicable]
```

### 6. Default Configurations
All default report configurations now use Excel format:
- Daily Driver Summary → Excel
- Weekly Medallion Status → Excel
- Monthly Vehicle Inspection → Excel
- Daily Lease Expiry Alert → Excel
- Weekly Trip Analytics → Excel
- Monthly SLA Performance → Excel

### 7. S3 Integration
- **Upload Path**: `reports/{report_type}/{year}/{month}/{day}/{filename}.xlsx`
- **Content Type**: Properly set for Excel files
- **Download**: Presigned URLs for secure access

### 8. API Response
Excel reports are served via:
- **Direct Download**: Redirect to S3 presigned URL
- **Email Delivery**: Download links sent via email
- **Content-Type**: Correct MIME type for browser handling

## Usage Examples

### Creating an Excel Report Configuration
```python
configuration = ReportConfigurationCreate(
    name="Weekly Sales Report",
    report_type=ReportType.FINANCIAL_SUMMARY,
    frequency=ReportFrequency.WEEKLY,
    output_format=ReportFormat.EXCEL,  # Primary format
    auto_email=True
)
```

### Manual Excel Generation
```python
# Reports are generated automatically via Celery tasks
generate_report_task.delay(
    report_id=123,
    override_parameters={"include_charts": True}
)
```

## Best Practices

1. **Data Size**: Charts are only generated for datasets with ≤50 rows to maintain performance
2. **Sheet Names**: Limited to 31 characters (Excel constraint)
3. **Memory Management**: Large datasets are processed in chunks
4. **Error Handling**: Chart generation failures don't affect report creation
5. **File Cleanup**: Local files are removed after S3 upload

## Troubleshooting

### Common Issues
1. **Large Files**: Excel files may be larger than other formats due to formatting
2. **Chart Errors**: Non-critical; report generation continues without charts
3. **Memory Usage**: Large datasets may require increased worker memory

### Performance Optimization
- Chart generation is optional and skipped for large datasets
- Column auto-sizing is limited to prevent excessive width
- Worksheet creation is optimized for typical business report sizes

## Future Enhancements
- Conditional formatting based on data values
- Custom chart types for specific report types
- Advanced pivot table generation
- Template-based styling customization
