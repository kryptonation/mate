### app/periodic_reports/router.py

# Standard library imports
from datetime import date
from typing import List, Optional

# Third party imports
from fastapi import (
    APIRouter, Depends, HTTPException, Query, Path, BackgroundTasks
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

# Local imports
from app.core.db import get_db
from app.utils.logger import get_logger
from app.users.models import User
from app.users.utils import get_current_user
from app.periodic_reports.models import ReportType, ReportFrequency, ReportStatus, ReportFormat
from app.periodic_reports.schemas import (
    ReportConfigurationCreate, ReportConfigurationUpdate, ReportConfigurationResponse,
    GenerateReportRequest, GeneratedReportResponse, ReportRecipientCreate,
    ReportRecipientResponse, ReportTypeInfo, ReportSummary, ReportExecutionRequest,
    BulkReportGenerationRequest
)
from app.periodic_reports.services import periodic_reports_service
from app.audit_trail.services import audit_trail_service
from app.audit_trail.schemas import AuditTrailType

router = APIRouter(prefix="/reports", tags=["Periodic Reports"])
logger = get_logger(__name__)


@router.get("/types", response_model=List[dict])
async def get_report_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all available report types with their metadata
    """
    try:
        report_types_summary = periodic_reports_service.get_report_types_summary(db)
        
        # Add metadata for each report type
        for report_info in report_types_summary:
            report_type = ReportType(report_info['report_type'])
            report_info.update({
                'supported_formats': [format.value for format in ReportFormat],
                'supported_frequencies': [freq.value for freq in ReportFrequency],
                'required_parameters': _get_required_parameters(report_type),
                'optional_parameters': _get_optional_parameters(report_type)
            })
        
        return report_types_summary
        
    except Exception as e:
        logger.error(f"Error fetching report types: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configurations", response_model=ReportConfigurationResponse)
async def create_report_configuration(
    config_data: ReportConfigurationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new report configuration
    """
    try:
        config = periodic_reports_service.create_report_configuration(
            db, config_data, current_user
        )
        
        return ReportConfigurationResponse.model_validate(config)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Error creating report configuration: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/configurations", response_model=List[ReportConfigurationResponse])
async def get_report_configurations(
    skip: int = Query(0, ge=0, description="Number of configurations to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of configurations to return"),
    report_type: Optional[ReportType] = Query(None, description="Filter by report type"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    frequency: Optional[ReportFrequency] = Query(None, description="Filter by frequency"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get report configurations with optional filters
    """
    try:
        configs = periodic_reports_service.get_report_configurations(
            db, skip=skip, limit=limit, report_type=report_type,
            is_active=is_active, frequency=frequency
        )
        
        return [ReportConfigurationResponse.model_validate(config) for config in configs]
        
    except Exception as e:
        logger.error("Error fetching report configurations: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/configurations/{config_id}", response_model=ReportConfigurationResponse)
async def get_report_configuration(
    config_id: int = Path(..., description="Report configuration ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific report configuration
    """
    try:
        config = periodic_reports_service.get_report_configuration(db, config_id)
        if not config:
            raise HTTPException(status_code=404, detail="Report configuration not found")
        
        return ReportConfigurationResponse.model_validate(config)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching report configuration %d: %s", config_id, str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/configurations/{config_id}", response_model=ReportConfigurationResponse)
async def update_report_configuration(
    config_id: int = Path(..., description="Report configuration ID"),
    update_data: ReportConfigurationUpdate = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a report configuration
    """
    try:
        config = periodic_reports_service.update_report_configuration(
            db, config_id, update_data, current_user
        )
        
        if not config:
            raise HTTPException(status_code=404, detail="Report configuration not found")
                
        return ReportConfigurationResponse.model_validate(config)
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Error updating report configuration %d: %s", config_id, str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.delete("/configurations/{config_id}")
async def delete_report_configuration(
    config_id: int = Path(..., description="Report configuration ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Deactivate a report configuration
    """
    try:
        success = periodic_reports_service.delete_report_configuration(
            db, config_id, current_user
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Report configuration not found")
        
        return {"message": "Report configuration deactivated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting report configuration %d: %s", config_id, str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/generate", response_model=GeneratedReportResponse)
async def generate_report(
    request: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate a report on-demand
    """
    try:
        generated_report = periodic_reports_service.generate_report(
            db, request, current_user
        )
                
        return GeneratedReportResponse.model_validate(generated_report)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        logger.error("Error generating report: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/execute", response_model=GeneratedReportResponse)
async def execute_report_immediately(
    request: ReportExecutionRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Execute a report immediately without a saved configuration
    """
    try:
        # Create a temporary configuration
        from app.periodic_reports.schemas import ReportConfigurationCreate
        
        temp_config_data = ReportConfigurationCreate(
            name=f"Temp {request.report_type.value} Report",
            description="Temporary report configuration for immediate execution",
            report_type=request.report_type,
            frequency=ReportFrequency.ON_DEMAND,
            parameters=request.parameters or {},
            output_format=request.output_format,
            auto_email=False
        )
        
        # Create temporary configuration
        temp_config = periodic_reports_service.create_report_configuration(
            db, temp_config_data, current_user
        )
        
        # Generate report
        generate_request = GenerateReportRequest(
            configuration_id=temp_config.id,
            report_period_start=request.report_period_start,
            report_period_end=request.report_period_end,
            send_email=False
        )
        
        generated_report = periodic_reports_service.generate_report(
            db, generate_request, current_user
        )
        
        # Mark temp configuration as inactive
        temp_config.is_active = False
        db.commit()
        
        return GeneratedReportResponse.model_validate(generated_report)
        
    except Exception as e:
        logger.error("Error executing immediate report: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/generated", response_model=List[GeneratedReportResponse])
async def get_generated_reports(
    skip: int = Query(0, ge=0, description="Number of reports to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of reports to return"),
    configuration_id: Optional[int] = Query(None, description="Filter by configuration ID"),
    status: Optional[ReportStatus] = Query(None, description="Filter by status"),
    start_date: Optional[date] = Query(None, description="Filter by generation start date"),
    end_date: Optional[date] = Query(None, description="Filter by generation end date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get generated reports with optional filters
    """
    try:
        reports = periodic_reports_service.get_generated_reports(
            db, skip=skip, limit=limit, configuration_id=configuration_id,
            status=status, start_date=start_date, end_date=end_date
        )
        
        return [GeneratedReportResponse.model_validate(report) for report in reports]
        
    except Exception as e:
        logger.error("Error fetching generated reports: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/generated/{report_id}", response_model=GeneratedReportResponse)
async def get_generated_report(
    report_id: int = Path(..., description="Generated report ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific generated report
    """
    try:
        report = periodic_reports_service.get_generated_report(db, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Generated report not found")
        
        return GeneratedReportResponse.model_validate(report)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error fetching generated report %d: %s", report_id, str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/generated/{report_id}/download")
async def download_generated_report(
    report_id: int = Path(..., description="Generated report ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Download a generated report file
    """
    try:
        report = periodic_reports_service.get_generated_report(db, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Generated report not found")
        
        if not report.file_path:
            raise HTTPException(status_code=404, detail="Report file not found")
                
        # Check if file is stored in S3 (S3 keys start with "reports/")
        if report.file_path.startswith("reports/"):
            # Generate presigned URL for S3 files and redirect
            from app.utils.s3_utils import s3_utils
            from fastapi.responses import RedirectResponse
            
            presigned_url = s3_utils.generate_presigned_url(
                report.file_path, 
                expiration=3600  # 1 hour for download
            )
            
            if presigned_url:
                return RedirectResponse(url=presigned_url)
            else:
                raise HTTPException(status_code=500, detail="Could not generate download link")
        
        # Handle local files (fallback)
        else:
            import os
            if not os.path.exists(report.file_path):
                raise HTTPException(status_code=404, detail="Report file not found on disk")
            
            filename = os.path.basename(report.file_path)
            return FileResponse(
                path=report.file_path,
                filename=filename,
                media_type='application/octet-stream'
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error downloading report %d: %s", report_id, str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/bulk-generate")
async def bulk_generate_reports(
    request: BulkReportGenerationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate multiple reports in bulk
    """
    try:
        generated_reports = []
        
        for config_id in request.configuration_ids:
            try:
                generate_request = GenerateReportRequest(
                    configuration_id=config_id,
                    override_parameters=request.override_parameters
                )
                
                generated_report = periodic_reports_service.generate_report(
                    db, generate_request, current_user
                )
                generated_reports.append(generated_report.id)
                
            except Exception as e:
                logger.error("Error generating report for config %d: %s", config_id, str(e))
                continue
        
        return {
            "message": f"Successfully queued {len(generated_reports)} reports for generation",
            "generated_report_ids": generated_reports
        }
        
    except Exception as e:
        logger.error("Error in bulk report generation: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


def _get_required_parameters(report_type: ReportType) -> List[str]:
    """Get required parameters for a report type"""
    # This would typically come from a configuration or metadata table
    return []  # Most reports don't have strictly required parameters


def _get_optional_parameters(report_type: ReportType) -> List[str]:
    """Get optional parameters for a report type"""
    common_params = ["start_date", "end_date"]
    
    specific_params = {
        ReportType.DRIVER_SUMMARY: ["driver_status", "driver_type"],
        ReportType.MEDALLION_STATUS: ["medallion_status", "owner_type"],
        ReportType.VEHICLE_INSPECTION: ["vehicle_status", "inspection_due_days"],
        ReportType.FINANCIAL_SUMMARY: ["account_type", "transaction_type"],
        ReportType.LEASE_EXPIRY: ["lease_type", "expiry_days"],
        ReportType.VIOLATION_SUMMARY: ["violation_type", "status"],
        ReportType.EZPASS_TRANSACTIONS: ["agency", "transaction_status"],
        ReportType.TRIP_ANALYTICS: ["driver_id", "vehicle_id"],
        ReportType.SLA_PERFORMANCE: ["case_type", "sla_status"],
        ReportType.AUDIT_TRAIL_SUMMARY: ["audit_type", "user_id"]
    }
    
    return common_params + specific_params.get(report_type, [])
