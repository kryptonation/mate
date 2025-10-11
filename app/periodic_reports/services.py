### app/periodic_reports/services.py

# Standard library imports
import os
import json
from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any, Union
import traceback

# Third party imports
from sqlalchemy import desc, asc, func, and_, or_
from sqlalchemy.orm import Session

# Local imports
from app.periodic_reports.models import (
    ReportConfiguration, GeneratedReport, ReportRecipient, ReportTemplate,
    ReportType, ReportFrequency, ReportStatus, ReportFormat
)
from app.periodic_reports.schemas import (
    ReportConfigurationCreate, ReportConfigurationUpdate,
    GenerateReportRequest, ReportRecipientCreate
)
from app.users.models import User
from app.utils.logger import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class PeriodicReportsService:
    """Service for managing periodic reports"""

    def create_report_configuration(
        self,
        db: Session,
        config_data: ReportConfigurationCreate,
        user: User
    ) -> ReportConfiguration:
        """Create a new report configuration"""
        try:
            # Validate schedule based on frequency
            self._validate_schedule(config_data.frequency, config_data.schedule_time, 
                                  config_data.schedule_day_of_week, config_data.schedule_day_of_month)
            
            # Create the configuration
            config = ReportConfiguration(
                name=config_data.name,
                description=config_data.description,
                report_type=config_data.report_type,
                frequency=config_data.frequency,
                schedule_time=config_data.schedule_time,
                schedule_day_of_week=config_data.schedule_day_of_week,
                schedule_day_of_month=config_data.schedule_day_of_month,
                parameters=config_data.parameters or {},
                output_format=config_data.output_format,
                email_recipients=config_data.email_recipients or [],
                auto_email=config_data.auto_email,
                output_directory=config_data.output_directory,
                filename_template=config_data.filename_template,
                created_by=user.id
            )
            
            db.add(config)
            db.commit()
            db.refresh(config)
            
            logger.info(f"Created report configuration: {config.name} (ID: {config.id})")
            return config
            
        except Exception as e:
            logger.error(f"Error creating report configuration: {str(e)}")
            db.rollback()
            raise e

    def get_report_configurations(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        report_type: Optional[ReportType] = None,
        is_active: Optional[bool] = None,
        frequency: Optional[ReportFrequency] = None
    ) -> List[ReportConfiguration]:
        """Get report configurations with optional filters"""
        try:
            query = db.query(ReportConfiguration)
            
            if report_type:
                query = query.filter(ReportConfiguration.report_type == report_type)
            if is_active is not None:
                query = query.filter(ReportConfiguration.is_active == is_active)
            if frequency:
                query = query.filter(ReportConfiguration.frequency == frequency)
            
            return query.offset(skip).limit(limit).all()
            
        except Exception as e:
            logger.error(f"Error fetching report configurations: {str(e)}")
            raise e

    def get_report_configuration(
        self,
        db: Session,
        config_id: int
    ) -> Optional[ReportConfiguration]:
        """Get a specific report configuration"""
        try:
            return db.query(ReportConfiguration).filter(
                ReportConfiguration.id == config_id
            ).first()
        except Exception as e:
            logger.error(f"Error fetching report configuration {config_id}: {str(e)}")
            raise e

    def update_report_configuration(
        self,
        db: Session,
        config_id: int,
        update_data: ReportConfigurationUpdate,
        user: User
    ) -> Optional[ReportConfiguration]:
        """Update a report configuration"""
        try:
            config = self.get_report_configuration(db, config_id)
            if not config:
                return None
            
            # Update fields if provided
            update_dict = update_data.model_dump(exclude_unset=True)
            
            # Validate schedule if frequency is being updated
            if 'frequency' in update_dict:
                schedule_time = update_dict.get('schedule_time', config.schedule_time)
                schedule_day_of_week = update_dict.get('schedule_day_of_week', config.schedule_day_of_week)
                schedule_day_of_month = update_dict.get('schedule_day_of_month', config.schedule_day_of_month)
                self._validate_schedule(update_dict['frequency'], schedule_time, 
                                      schedule_day_of_week, schedule_day_of_month)
            
            for key, value in update_dict.items():
                setattr(config, key, value)
            
            config.modified_by = user.id
            db.commit()
            db.refresh(config)
            
            logger.info(f"Updated report configuration: {config.name} (ID: {config.id})")
            return config
            
        except Exception as e:
            logger.error(f"Error updating report configuration {config_id}: {str(e)}")
            db.rollback()
            raise e

    def delete_report_configuration(
        self,
        db: Session,
        config_id: int,
        user: User
    ) -> bool:
        """Soft delete a report configuration"""
        try:
            config = self.get_report_configuration(db, config_id)
            if not config:
                return False
            
            config.is_active = False
            config.modified_by = user.id
            db.commit()
            
            logger.info(f"Deactivated report configuration: {config.name} (ID: {config.id})")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting report configuration {config_id}: {str(e)}")
            db.rollback()
            raise e

    def generate_report(
        self,
        db: Session,
        request: GenerateReportRequest,
        user: User
    ) -> GeneratedReport:
        """Generate a report on-demand"""
        try:
            config = self.get_report_configuration(db, request.configuration_id)
            if not config:
                raise ValueError(f"Report configuration {request.configuration_id} not found")
            
            if not config.is_active:
                raise ValueError(f"Report configuration {request.configuration_id} is not active")
            
            # Create the generated report record
            generated_report = GeneratedReport(
                configuration_id=config.id,
                report_name=self._generate_report_name(config, request.report_period_start, request.report_period_end),
                generation_date=datetime.utcnow(),
                report_period_start=request.report_period_start,
                report_period_end=request.report_period_end,
                status=ReportStatus.PENDING,
                created_by=user.id
            )
            
            db.add(generated_report)
            db.commit()
            db.refresh(generated_report)
            
            # Queue the report generation task
            from app.periodic_reports.tasks import generate_report_task
            generate_report_task.delay(
                generated_report.id, 
                request.override_parameters or {},
                request.send_email
            )
            
            logger.info(f"Queued report generation: {generated_report.report_name} (ID: {generated_report.id})")
            return generated_report
            
        except Exception as e:
            logger.error(f"Error generating report: {str(e)}")
            db.rollback()
            raise e

    def get_generated_reports(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        configuration_id: Optional[int] = None,
        status: Optional[ReportStatus] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[GeneratedReport]:
        """Get generated reports with optional filters"""
        try:
            query = db.query(GeneratedReport)
            
            if configuration_id:
                query = query.filter(GeneratedReport.configuration_id == configuration_id)
            if status:
                query = query.filter(GeneratedReport.status == status)
            if start_date:
                query = query.filter(GeneratedReport.generation_date >= start_date)
            if end_date:
                query = query.filter(GeneratedReport.generation_date <= end_date)
            
            return query.order_by(desc(GeneratedReport.generation_date)).offset(skip).limit(limit).all()
            
        except Exception as e:
            logger.error(f"Error fetching generated reports: {str(e)}")
            raise e

    def get_generated_report(
        self,
        db: Session,
        report_id: int
    ) -> Optional[GeneratedReport]:
        """Get a specific generated report"""
        try:
            return db.query(GeneratedReport).filter(
                GeneratedReport.id == report_id
            ).first()
        except Exception as e:
            logger.error(f"Error fetching generated report {report_id}: {str(e)}")
            raise e

    def get_report_types_summary(self, db: Session) -> List[Dict[str, Any]]:
        """Get summary of all report types with statistics"""
        try:
            report_types = []
            for report_type in ReportType:
                # Get configuration count
                config_count = db.query(ReportConfiguration).filter(
                    ReportConfiguration.report_type == report_type
                ).count()
                
                active_config_count = db.query(ReportConfiguration).filter(
                    ReportConfiguration.report_type == report_type,
                    ReportConfiguration.is_active == True
                ).count()
                
                # Get generated report statistics
                generated_count = db.query(GeneratedReport).join(ReportConfiguration).filter(
                    ReportConfiguration.report_type == report_type
                ).count()
                
                successful_count = db.query(GeneratedReport).join(ReportConfiguration).filter(
                    ReportConfiguration.report_type == report_type,
                    GeneratedReport.status == ReportStatus.COMPLETED
                ).count()
                
                failed_count = db.query(GeneratedReport).join(ReportConfiguration).filter(
                    ReportConfiguration.report_type == report_type,
                    GeneratedReport.status == ReportStatus.FAILED
                ).count()
                
                # Get last generation date
                last_report = db.query(GeneratedReport).join(ReportConfiguration).filter(
                    ReportConfiguration.report_type == report_type,
                    GeneratedReport.status == ReportStatus.COMPLETED
                ).order_by(desc(GeneratedReport.generation_date)).first()
                
                report_types.append({
                    "report_type": report_type.value,
                    "name": self._get_report_type_name(report_type),
                    "description": self._get_report_type_description(report_type),
                    "total_configurations": config_count,
                    "active_configurations": active_config_count,
                    "total_generated_reports": generated_count,
                    "successful_reports": successful_count,
                    "failed_reports": failed_count,
                    "last_generation_date": last_report.generation_date if last_report else None
                })
            
            return report_types
            
        except Exception as e:
            logger.error(f"Error fetching report types summary: {str(e)}")
            raise e

    def get_scheduled_reports_due(self, db: Session) -> List[ReportConfiguration]:
        """Get reports that are due for generation based on their schedule"""
        try:
            now = datetime.utcnow()
            current_time = now.time().strftime("%H:%M")
            current_weekday = now.weekday()  # 0 = Monday
            current_day = now.day
            
            due_reports = []
            
            # Get all active configurations
            configs = db.query(ReportConfiguration).filter(
                ReportConfiguration.is_active == True
            ).all()
            
            for config in configs:
                if self._is_report_due(config, now, current_time, current_weekday, current_day):
                    # Check if already generated today/this period
                    if not self._already_generated_in_period(db, config, now):
                        due_reports.append(config)
            
            return due_reports
            
        except Exception as e:
            logger.error(f"Error fetching scheduled reports due: {str(e)}")
            raise e

    def _validate_schedule(
        self,
        frequency: ReportFrequency,
        schedule_time: Optional[str],
        schedule_day_of_week: Optional[int],
        schedule_day_of_month: Optional[int]
    ):
        """Validate schedule configuration based on frequency"""
        if frequency == ReportFrequency.WEEKLY and schedule_day_of_week is None:
            raise ValueError("schedule_day_of_week is required for weekly reports")
        
        if frequency == ReportFrequency.MONTHLY and schedule_day_of_month is None:
            raise ValueError("schedule_day_of_month is required for monthly reports")
        
        if schedule_time and not self._is_valid_time_format(schedule_time):
            raise ValueError("schedule_time must be in HH:MM format")

    def _is_valid_time_format(self, time_str: str) -> bool:
        """Check if time string is in valid HH:MM format"""
        try:
            datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False

    def _generate_report_name(
        self,
        config: ReportConfiguration,
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> str:
        """Generate a report name based on configuration and dates"""
        if config.filename_template:
            # Use custom template
            template = config.filename_template
            template = template.replace("{report_type}", config.report_type.value)
            template = template.replace("{date}", datetime.utcnow().strftime("%Y%m%d"))
            if start_date:
                template = template.replace("{start_date}", start_date.strftime("%Y%m%d"))
            if end_date:
                template = template.replace("{end_date}", end_date.strftime("%Y%m%d"))
            return template
        else:
            # Default naming
            date_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            return f"{config.report_type.value}_{date_str}"

    def _get_report_type_name(self, report_type: ReportType) -> str:
        """Get human-readable name for report type"""
        names = {
            ReportType.DRIVER_SUMMARY: "Driver Summary Report",
            ReportType.MEDALLION_STATUS: "Medallion Status Report",
            ReportType.VEHICLE_INSPECTION: "Vehicle Inspection Report",
            ReportType.FINANCIAL_SUMMARY: "Financial Summary Report",
            ReportType.LEASE_EXPIRY: "Lease Expiry Report",
            ReportType.VIOLATION_SUMMARY: "Violation Summary Report",
            ReportType.EZPASS_TRANSACTIONS: "EZPass Transactions Report",
            ReportType.TRIP_ANALYTICS: "Trip Analytics Report",
            ReportType.SLA_PERFORMANCE: "SLA Performance Report",
            ReportType.AUDIT_TRAIL_SUMMARY: "Audit Trail Summary Report"
        }
        return names.get(report_type, report_type.value.replace("_", " ").title())

    def _get_report_type_description(self, report_type: ReportType) -> str:
        """Get description for report type"""
        descriptions = {
            ReportType.DRIVER_SUMMARY: "Summary of driver registrations, status changes, and activities",
            ReportType.MEDALLION_STATUS: "Current status and ownership information for all medallions",
            ReportType.VEHICLE_INSPECTION: "Vehicle inspection schedules, results, and compliance status",
            ReportType.FINANCIAL_SUMMARY: "Financial transactions, payments, and outstanding balances",
            ReportType.LEASE_EXPIRY: "Upcoming lease expirations and renewal requirements",
            ReportType.VIOLATION_SUMMARY: "Traffic violations, assignments, and payment status",
            ReportType.EZPASS_TRANSACTIONS: "EZPass toll transactions and reconciliation data",
            ReportType.TRIP_ANALYTICS: "Trip data analysis and driver performance metrics",
            ReportType.SLA_PERFORMANCE: "Service level agreement compliance and performance metrics",
            ReportType.AUDIT_TRAIL_SUMMARY: "System activity and audit trail summary"
        }
        return descriptions.get(report_type, "")

    def _is_report_due(
        self,
        config: ReportConfiguration,
        current_time: datetime,
        time_str: str,
        weekday: int,
        day: int
    ) -> bool:
        """Check if a report is due for generation"""
        if config.frequency == ReportFrequency.ON_DEMAND:
            return False
        
        # Check time if specified
        if config.schedule_time and config.schedule_time != time_str:
            return False
        
        if config.frequency == ReportFrequency.DAILY:
            return True
        elif config.frequency == ReportFrequency.WEEKLY:
            return config.schedule_day_of_week == weekday
        elif config.frequency == ReportFrequency.MONTHLY:
            return config.schedule_day_of_month == day
        elif config.frequency == ReportFrequency.QUARTERLY:
            # First day of quarter
            return day == 1 and current_time.month in [1, 4, 7, 10]
        elif config.frequency == ReportFrequency.YEARLY:
            # First day of year
            return day == 1 and current_time.month == 1
        
        return False

    def _already_generated_in_period(
        self,
        db: Session,
        config: ReportConfiguration,
        current_time: datetime
    ) -> bool:
        """Check if report was already generated in the current period"""
        try:
            # Determine period start based on frequency
            if config.frequency == ReportFrequency.DAILY:
                period_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            elif config.frequency == ReportFrequency.WEEKLY:
                days_since_monday = current_time.weekday()
                period_start = (current_time - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
            elif config.frequency == ReportFrequency.MONTHLY:
                period_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                # For quarterly and yearly, check if generated in last 24 hours
                period_start = current_time - timedelta(hours=24)
            
            # Check if any successful report exists in this period
            existing_report = db.query(GeneratedReport).filter(
                GeneratedReport.configuration_id == config.id,
                GeneratedReport.generation_date >= period_start,
                GeneratedReport.status == ReportStatus.COMPLETED
            ).first()
            
            return existing_report is not None
            
        except Exception as e:
            logger.error(f"Error checking if report already generated: {str(e)}")
            return False


# Create service instance
periodic_reports_service = PeriodicReportsService()
