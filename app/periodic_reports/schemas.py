### app/periodic_reports/schemas.py

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from enum import Enum

from app.periodic_reports.models import (
    ReportType, ReportFrequency, ReportStatus, ReportFormat
)


class ReportConfigurationCreate(BaseModel):
    """Schema for creating a new report configuration"""
    name: str = Field(..., description="Human-readable name for the report")
    description: Optional[str] = Field(None, description="Description of what the report contains")
    report_type: ReportType = Field(..., description="Type of report to generate")
    frequency: ReportFrequency = Field(..., description="How often the report should be generated")
    schedule_time: Optional[str] = Field(None, description="Time of day to run report (HH:MM format)")
    schedule_day_of_week: Optional[int] = Field(None, ge=0, le=6, description="Day of week for weekly reports (0=Monday)")
    schedule_day_of_month: Optional[int] = Field(None, ge=1, le=31, description="Day of month for monthly reports")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Report parameters and filters")
    output_format: ReportFormat = Field(ReportFormat.PDF, description="Output format for the report")
    email_recipients: Optional[List[str]] = Field(None, description="List of email addresses")
    auto_email: bool = Field(True, description="Whether to automatically email the report")
    output_directory: Optional[str] = Field(None, description="Directory path where reports are stored")
    filename_template: Optional[str] = Field(None, description="Template for generated filenames")


class ReportConfigurationUpdate(BaseModel):
    """Schema for updating a report configuration"""
    name: Optional[str] = None
    description: Optional[str] = None
    report_type: Optional[ReportType] = None
    frequency: Optional[ReportFrequency] = None
    schedule_time: Optional[str] = None
    schedule_day_of_week: Optional[int] = Field(None, ge=0, le=6)
    schedule_day_of_month: Optional[int] = Field(None, ge=1, le=31)
    parameters: Optional[Dict[str, Any]] = None
    output_format: Optional[ReportFormat] = None
    email_recipients: Optional[List[str]] = None
    is_active: Optional[bool] = None
    auto_email: Optional[bool] = None
    output_directory: Optional[str] = None
    filename_template: Optional[str] = None


class ReportConfigurationResponse(BaseModel):
    """Schema for report configuration response"""
    id: int
    name: str
    description: Optional[str]
    report_type: ReportType
    frequency: ReportFrequency
    schedule_time: Optional[str]
    schedule_day_of_week: Optional[int]
    schedule_day_of_month: Optional[int]
    parameters: Optional[Dict[str, Any]]
    output_format: ReportFormat
    email_recipients: Optional[List[str]]
    is_active: bool
    auto_email: bool
    created_on: datetime
    updated_on: Optional[datetime]

    class Config:
        from_attributes = True


class GenerateReportRequest(BaseModel):
    """Schema for on-demand report generation"""
    configuration_id: int = Field(..., description="ID of the report configuration to use")
    report_period_start: Optional[date] = Field(None, description="Start date for the report period")
    report_period_end: Optional[date] = Field(None, description="End date for the report period")
    override_parameters: Optional[Dict[str, Any]] = Field(None, description="Parameters to override from configuration")
    send_email: Optional[bool] = Field(None, description="Override auto_email setting")


class GeneratedReportResponse(BaseModel):
    """Schema for generated report response"""
    id: int
    configuration_id: int
    report_name: str
    generation_date: datetime
    report_period_start: Optional[date]
    report_period_end: Optional[date]
    status: ReportStatus
    file_path: Optional[str]
    file_size: Optional[int]
    execution_time_seconds: Optional[int]
    error_message: Optional[str]
    email_sent: bool
    email_sent_at: Optional[datetime]
    email_error: Optional[str]
    created_on: datetime

    class Config:
        from_attributes = True


class ReportRecipientCreate(BaseModel):
    """Schema for creating a report recipient"""
    configuration_id: int
    user_id: Optional[int] = None
    email_address: Optional[str] = None
    name: Optional[str] = None
    delivery_method: str = "email"


class ReportRecipientResponse(BaseModel):
    """Schema for report recipient response"""
    id: int
    configuration_id: int
    user_id: Optional[int]
    email_address: Optional[str]
    name: Optional[str]
    delivery_method: str
    is_active: bool

    class Config:
        from_attributes = True


class ReportTypeInfo(BaseModel):
    """Schema for report type information"""
    type: ReportType
    name: str
    description: str
    required_parameters: List[str]
    optional_parameters: List[str]
    supported_formats: List[ReportFormat]


class ReportSummary(BaseModel):
    """Schema for report summary statistics"""
    report_type: ReportType
    total_configurations: int
    active_configurations: int
    total_generated_reports: int
    successful_reports: int
    failed_reports: int
    last_generation_date: Optional[datetime]


class ReportExecutionRequest(BaseModel):
    """Schema for immediate report execution"""
    report_type: ReportType
    parameters: Optional[Dict[str, Any]] = None
    output_format: ReportFormat = ReportFormat.PDF
    report_period_start: Optional[date] = None
    report_period_end: Optional[date] = None


class BulkReportGenerationRequest(BaseModel):
    """Schema for bulk report generation"""
    configuration_ids: List[int] = Field(..., description="List of configuration IDs to generate")
    override_parameters: Optional[Dict[str, Any]] = Field(None, description="Parameters to apply to all reports")
    force_generation: bool = Field(False, description="Force generation even if recently generated")
