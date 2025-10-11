### app/periodic_reports/models.py

# Third party imports
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, JSON,
    ForeignKey, Enum as SQLEnum, Date
)
from sqlalchemy.orm import relationship
from enum import Enum

# Local imports
from app.core.db import Base
from app.users.models import AuditMixin , User


class ReportType(str, Enum):
    """Enum for report types"""
    DRIVER_SUMMARY = "driver_summary"
    MEDALLION_STATUS = "medallion_status"
    VEHICLE_INSPECTION = "vehicle_inspection"
    FINANCIAL_SUMMARY = "financial_summary"
    LEASE_EXPIRY = "lease_expiry"
    VIOLATION_SUMMARY = "violation_summary"
    EZPASS_TRANSACTIONS = "ezpass_transactions"
    TRIP_ANALYTICS = "trip_analytics"
    SLA_PERFORMANCE = "sla_performance"
    AUDIT_TRAIL_SUMMARY = "audit_trail_summary"
    PAYMENT_SUMMARY = "payment_summary"


class ReportFrequency(str, Enum):
    """Enum for report frequency"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    ON_DEMAND = "on_demand"


class ReportStatus(str, Enum):
    """Enum for report generation status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReportFormat(str, Enum):
    """Enum for report output formats"""
    PDF = "pdf"
    EXCEL = "excel"
    CSV = "csv"
    JSON = "json"


class ReportConfiguration(Base, AuditMixin):
    """
    Report Configuration model for defining periodic reports
    """
    __tablename__ = "report_configurations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, comment="Human-readable name for the report")
    description = Column(Text, nullable=True, comment="Description of what the report contains")
    
    report_type = Column(SQLEnum(ReportType), nullable=False, comment="Type of report to generate")
    frequency = Column(SQLEnum(ReportFrequency), nullable=False, comment="How often the report should be generated")
    
    # Scheduling information
    schedule_time = Column(String(10), nullable=True, comment="Time of day to run report (HH:MM format)")
    schedule_day_of_week = Column(Integer, nullable=True, comment="Day of week for weekly reports (0=Monday)")
    schedule_day_of_month = Column(Integer, nullable=True, comment="Day of month for monthly reports")
    
    # Report parameters and filters
    parameters = Column(JSON, nullable=True, comment="JSON object containing report parameters and filters")
    
    # Output configuration
    output_format = Column(SQLEnum(ReportFormat), nullable=False, default=ReportFormat.EXCEL)
    email_recipients = Column(JSON, nullable=True, comment="List of email addresses to send the report to")
    
    # Control flags
    is_active = Column(Boolean, default=True, comment="Whether this report configuration is active")
    auto_email = Column(Boolean, default=True, comment="Whether to automatically email the report")
    
    # File storage information
    output_directory = Column(String(500), nullable=True, comment="Directory path where reports are stored")
    filename_template = Column(String(255), nullable=True, comment="Template for generated filenames")
    
    # Relationships
    generated_reports = relationship("GeneratedReport", back_populates="configuration")
    recipients = relationship("ReportRecipient", back_populates="configuration")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "report_type": self.report_type.value if self.report_type else None,
            "frequency": self.frequency.value if self.frequency else None,
            "schedule_time": self.schedule_time,
            "schedule_day_of_week": self.schedule_day_of_week,
            "schedule_day_of_month": self.schedule_day_of_month,
            "parameters": self.parameters,
            "output_format": self.output_format.value if self.output_format else None,
            "email_recipients": self.email_recipients,
            "is_active": self.is_active,
            "auto_email": self.auto_email,
            "created_on": self.created_on,
            "updated_on": self.updated_on
        }


class GeneratedReport(Base, AuditMixin):
    """
    Model for tracking generated reports
    """
    __tablename__ = "generated_reports"

    id = Column(Integer, primary_key=True, index=True)
    configuration_id = Column(Integer, ForeignKey("report_configurations.id"), nullable=False)
    
    # Generation details
    report_name = Column(String(255), nullable=False, comment="Name of the generated report")
    generation_date = Column(DateTime, nullable=False, comment="When the report was generated")
    report_period_start = Column(Date, nullable=True, comment="Start date of the reporting period")
    report_period_end = Column(Date, nullable=True, comment="End date of the reporting period")
    
    # Status and file information
    status = Column(SQLEnum(ReportStatus), nullable=False, default=ReportStatus.PENDING)
    file_path = Column(String(1000), nullable=True, comment="Path to the generated report file")
    file_size = Column(Integer, nullable=True, comment="Size of the generated file in bytes")
    
    # Execution details
    execution_time_seconds = Column(Integer, nullable=True, comment="Time taken to generate the report")
    error_message = Column(Text, nullable=True, comment="Error message if generation failed")
    
    # Email details
    email_sent = Column(Boolean, default=False, comment="Whether the report was emailed")
    email_sent_at = Column(DateTime, nullable=True, comment="When the email was sent")
    email_error = Column(Text, nullable=True, comment="Email error message if sending failed")
    
    # Relationships
    configuration = relationship("ReportConfiguration", back_populates="generated_reports")

    def to_dict(self):
        return {
            "id": self.id,
            "configuration_id": self.configuration_id,
            "report_name": self.report_name,
            "generation_date": self.generation_date,
            "report_period_start": self.report_period_start,
            "report_period_end": self.report_period_end,
            "status": self.status.value if self.status else None,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "execution_time_seconds": self.execution_time_seconds,
            "error_message": self.error_message,
            "email_sent": self.email_sent,
            "email_sent_at": self.email_sent_at,
            "email_error": self.email_error,
            "created_on": self.created_on
        }


class ReportRecipient(Base, AuditMixin):
    """
    Model for managing report recipients with more detailed configuration
    """
    __tablename__ = "report_recipients"

    id = Column(Integer, primary_key=True, index=True)
    configuration_id = Column(Integer, ForeignKey("report_configurations.id"), nullable=False)
    
    # Recipient details
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="User ID if recipient is a system user")
    email_address = Column(String(255), nullable=True, comment="Email address for external recipients")
    name = Column(String(255), nullable=True, comment="Name of the recipient")
    
    # Delivery preferences
    delivery_method = Column(String(50), default="email", comment="How to deliver the report")
    is_active = Column(Boolean, default=True, comment="Whether this recipient is active")
    
    # Relationships
    configuration = relationship("ReportConfiguration", back_populates="recipients")
    user = relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        return {
            "id": self.id,
            "configuration_id": self.configuration_id,
            "user_id": self.user_id,
            "email_address": self.email_address,
            "name": self.name,
            "delivery_method": self.delivery_method,
            "is_active": self.is_active,
            "user": self.user.to_dict() if self.user else None
        }


class ReportTemplate(Base, AuditMixin):
    """
    Model for storing report templates
    """
    __tablename__ = "report_templates"

    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(SQLEnum(ReportType), nullable=False, unique=True)
    
    # Template details
    template_name = Column(String(255), nullable=False, comment="Name of the template")
    template_content = Column(Text, nullable=True, comment="Template content (HTML, etc.)")
    css_styles = Column(Text, nullable=True, comment="CSS styles for the template")
    
    # Configuration
    default_parameters = Column(JSON, nullable=True, comment="Default parameters for this report type")
    required_parameters = Column(JSON, nullable=True, comment="List of required parameters")
    
    def to_dict(self):
        return {
            "id": self.id,
            "report_type": self.report_type.value if self.report_type else None,
            "template_name": self.template_name,
            "template_content": self.template_content,
            "css_styles": self.css_styles,
            "default_parameters": self.default_parameters,
            "required_parameters": self.required_parameters
        }
