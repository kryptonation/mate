### app/periodic_reports/utils.py

# Standard library imports
from typing import Dict, Any, List
from datetime import date, timedelta

# Local imports
from app.periodic_reports.models import ReportType, ReportFrequency, ReportFormat
from app.periodic_reports.schemas import ReportConfigurationCreate


class ReportConfigurationManager:
    """Utility class for managing report configurations"""
    
    @staticmethod
    def create_default_configurations() -> List[ReportConfigurationCreate]:
        """Create default report configurations for common use cases"""
        configurations = []
        
        # Daily Driver Summary Report
        configurations.append(ReportConfigurationCreate(
            name="Daily Driver Summary",
            description="Daily summary of driver activities, new registrations, and status changes",
            report_type=ReportType.DRIVER_SUMMARY,
            frequency=ReportFrequency.DAILY,
            schedule_time="08:00",
            output_format=ReportFormat.EXCEL,
            auto_email=True,
            parameters={
                "include_inactive": False,
                "summary_period_days": 1
            }
        ))
        
        # Weekly Medallion Status Report
        configurations.append(ReportConfigurationCreate(
            name="Weekly Medallion Status",
            description="Weekly report on medallion status, ownership changes, and storage activities",
            report_type=ReportType.MEDALLION_STATUS,
            frequency=ReportFrequency.WEEKLY,
            schedule_time="09:00",
            schedule_day_of_week=1,  # Monday
            output_format=ReportFormat.EXCEL,
            auto_email=True
        ))
        
        # Monthly Vehicle Inspection Report
        configurations.append(ReportConfigurationCreate(
            name="Monthly Vehicle Inspection",
            description="Monthly report on vehicle inspections, upcoming due dates, and compliance",
            report_type=ReportType.VEHICLE_INSPECTION,
            frequency=ReportFrequency.MONTHLY,
            schedule_time="07:00",
            schedule_day_of_month=1,
            output_format=ReportFormat.EXCEL,
            auto_email=True,
            parameters={
                "inspection_due_days": 30,
                "include_compliant": True
            }
        ))
        
        # Weekly Financial Summary Report
        configurations.append(ReportConfigurationCreate(
            name="Weekly Financial Summary",
            description="Weekly financial summary including transactions, payments, and outstanding amounts",
            report_type=ReportType.FINANCIAL_SUMMARY,
            frequency=ReportFrequency.WEEKLY,
            schedule_time="10:00",
            schedule_day_of_week=1,  # Monday
            output_format=ReportFormat.EXCEL,
            auto_email=True
        ))
        
        # Daily Lease Expiry Report
        configurations.append(ReportConfigurationCreate(
            name="Daily Lease Expiry Alert",
            description="Daily report of leases expiring in the next 30 days",
            report_type=ReportType.LEASE_EXPIRY,
            frequency=ReportFrequency.DAILY,
            schedule_time="08:30",
            output_format=ReportFormat.EXCEL,
            auto_email=True,
            parameters={
                "expiry_warning_days": 30
            }
        ))
        
        # Weekly Violation Summary Report
        configurations.append(ReportConfigurationCreate(
            name="Weekly Violation Summary",
            description="Weekly summary of parking violations, assignments, and payment status",
            report_type=ReportType.VIOLATION_SUMMARY,
            frequency=ReportFrequency.WEEKLY,
            schedule_time="11:00",
            schedule_day_of_week=2,  # Tuesday
            output_format=ReportFormat.CSV,
            auto_email=True
        ))
        
        # Monthly EZPass Transactions Report
        configurations.append(ReportConfigurationCreate(
            name="Monthly EZPass Transactions",
            description="Monthly report of EZPass toll transactions and reconciliation",
            report_type=ReportType.EZPASS_TRANSACTIONS,
            frequency=ReportFrequency.MONTHLY,
            schedule_time="08:00",
            schedule_day_of_month=5,
            output_format=ReportFormat.EXCEL,
            auto_email=True
        ))
        
        # Weekly Trip Analytics Report
        configurations.append(ReportConfigurationCreate(
            name="Weekly Trip Analytics",
            description="Weekly analysis of trip data, driver performance, and revenue metrics",
            report_type=ReportType.TRIP_ANALYTICS,
            frequency=ReportFrequency.WEEKLY,
            schedule_time="09:30",
            schedule_day_of_week=1,  # Monday
            output_format=ReportFormat.EXCEL,
            auto_email=True
        ))
        
        # Monthly SLA Performance Report
        configurations.append(ReportConfigurationCreate(
            name="Monthly SLA Performance",
            description="Monthly report on SLA compliance, case processing times, and performance metrics",
            report_type=ReportType.SLA_PERFORMANCE,
            frequency=ReportFrequency.MONTHLY,
            schedule_time="07:30",
            schedule_day_of_month=2,
            output_format=ReportFormat.EXCEL,
            auto_email=True
        ))
        
        # Weekly Audit Trail Summary
        configurations.append(ReportConfigurationCreate(
            name="Weekly Audit Trail Summary",
            description="Weekly summary of system activities, user actions, and audit trail events",
            report_type=ReportType.AUDIT_TRAIL_SUMMARY,
            frequency=ReportFrequency.WEEKLY,
            schedule_time="12:00",
            schedule_day_of_week=5,  # Friday
            output_format=ReportFormat.CSV,
            auto_email=True
        ))
        
        return configurations
    
    @staticmethod
    def get_common_parameters(report_type: ReportType) -> Dict[str, Any]:
        """Get common parameters for a report type"""
        common_params = {
            ReportType.DRIVER_SUMMARY: {
                "include_inactive": False,
                "summary_period_days": 7,
                "include_additional_drivers": True
            },
            ReportType.MEDALLION_STATUS: {
                "include_storage": True,
                "include_ownership_details": True,
                "status_filter": "all"
            },
            ReportType.VEHICLE_INSPECTION: {
                "inspection_due_days": 30,
                "include_compliant": True,
                "include_overdue": True
            },
            ReportType.FINANCIAL_SUMMARY: {
                "include_pending": True,
                "include_completed": True,
                "currency": "USD"
            },
            ReportType.LEASE_EXPIRY: {
                "expiry_warning_days": 30,
                "include_auto_renewal": True,
                "lease_types": ["driver", "medallion"]
            },
            ReportType.VIOLATION_SUMMARY: {
                "include_paid": False,
                "include_pending": True,
                "include_disputed": True
            },
            ReportType.EZPASS_TRANSACTIONS: {
                "include_unreconciled": True,
                "include_disputed": True,
                "group_by_driver": True
            },
            ReportType.TRIP_ANALYTICS: {
                "include_revenue": True,
                "include_performance_metrics": True,
                "minimum_trips": 1
            },
            ReportType.SLA_PERFORMANCE: {
                "include_breached": True,
                "include_warnings": True,
                "performance_threshold": 0.95
            },
            ReportType.AUDIT_TRAIL_SUMMARY: {
                "include_system_actions": False,
                "include_user_actions": True,
                "activity_threshold": 1
            }
        }
        
        return common_params.get(report_type, {})
    
    @staticmethod
    def validate_parameters(report_type: ReportType, parameters: Dict[str, Any]) -> Dict[str, str]:
        """Validate parameters for a report type and return any errors"""
        errors = {}
        
        if not parameters:
            return errors
        
        # Common validations
        if 'start_date' in parameters:
            try:
                if isinstance(parameters['start_date'], str):
                    date.fromisoformat(parameters['start_date'])
            except ValueError:
                errors['start_date'] = "Invalid date format. Use YYYY-MM-DD"
        
        if 'end_date' in parameters:
            try:
                if isinstance(parameters['end_date'], str):
                    date.fromisoformat(parameters['end_date'])
            except ValueError:
                errors['end_date'] = "Invalid date format. Use YYYY-MM-DD"
        
        # Report-specific validations
        if report_type == ReportType.VEHICLE_INSPECTION:
            if 'inspection_due_days' in parameters:
                try:
                    days = int(parameters['inspection_due_days'])
                    if days < 0 or days > 365:
                        errors['inspection_due_days'] = "Must be between 0 and 365"
                except (ValueError, TypeError):
                    errors['inspection_due_days'] = "Must be a valid number"
        
        elif report_type == ReportType.LEASE_EXPIRY:
            if 'expiry_warning_days' in parameters:
                try:
                    days = int(parameters['expiry_warning_days'])
                    if days < 1 or days > 365:
                        errors['expiry_warning_days'] = "Must be between 1 and 365"
                except (ValueError, TypeError):
                    errors['expiry_warning_days'] = "Must be a valid number"
        
        elif report_type == ReportType.SLA_PERFORMANCE:
            if 'performance_threshold' in parameters:
                try:
                    threshold = float(parameters['performance_threshold'])
                    if threshold < 0 or threshold > 1:
                        errors['performance_threshold'] = "Must be between 0 and 1"
                except (ValueError, TypeError):
                    errors['performance_threshold'] = "Must be a valid decimal number"
        
        return errors
    
    @staticmethod
    def get_filename_templates() -> Dict[ReportType, str]:
        """Get default filename templates for each report type"""
        return {
            ReportType.DRIVER_SUMMARY: "driver_summary_{date}",
            ReportType.MEDALLION_STATUS: "medallion_status_{date}",
            ReportType.VEHICLE_INSPECTION: "vehicle_inspection_{date}",
            ReportType.FINANCIAL_SUMMARY: "financial_summary_{start_date}_to_{end_date}",
            ReportType.LEASE_EXPIRY: "lease_expiry_alert_{date}",
            ReportType.VIOLATION_SUMMARY: "violation_summary_{start_date}_to_{end_date}",
            ReportType.EZPASS_TRANSACTIONS: "ezpass_transactions_{start_date}_to_{end_date}",
            ReportType.TRIP_ANALYTICS: "trip_analytics_{start_date}_to_{end_date}",
            ReportType.SLA_PERFORMANCE: "sla_performance_{start_date}_to_{end_date}",
            ReportType.AUDIT_TRAIL_SUMMARY: "audit_trail_summary_{start_date}_to_{end_date}"
        }


# Create instance
report_config_manager = ReportConfigurationManager()
