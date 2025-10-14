# app/pvb/router.py

"""
FastAPI router for PVB (Parking Violations Bureau) operations with async endpoints.
"""

import math
from datetime import datetime, date
from typing import Optional
from io import BytesIO

from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Query,
    status,
)
from fastapi.responses import StreamingResponse

from app.pvb.services import PVBService
from app.pvb.schemas import (
    PVBViolationResponse, PaginatedPVBViolationResponse,
    PVBLogResponse, PaginatedPVBLogResponse,
    PVBViolationUpdate, PVBViolationFilters, PVBLogFilters,
    PVBImportResult, PVBAssociationResult, PVBPostingResult,
)
from app.pvb.exceptions import (
    PVBBaseException, convert_to_http_exception,
    PVBFileValidationException
)
from app.pvb.utils import validate_pvb_file
from app.users.models import User
from app.users.utils import get_current_user
from app.utils.logger import get_logger
from app.utils.exporter_utils import ExporterFactory

logger = get_logger(__name__)
router = APIRouter(tags=["PVB"], prefix="/pvb")


# ===================== Import Operations =====================

@router.post("/import", response_model=PVBImportResult, status_code=status.HTTP_201_CREATED)
async def import_pvb(
    file: UploadFile = File(...),
    pvb_service: PVBService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Import PVB violations from an uploaded file.

    The file should be in CSV or Excel format with the required columns matching
    the PVB data structure.
    """
    logger.info(
        "PVB import request received",
        filename=file.filename,
        user_id=current_user.id
    )

    try:
        # Validate and parse file
        rows = validate_pvb_file(file)
        logger.info("File validated successfully", row_count=len(rows))

        # Process data
        result = await pvb_service.import_violations(rows)

        logger.info(
            "PVB import completed",
            log_id=result.log_id,
            success_count=result.success_count,
        )

        return result

    except PVBFileValidationException as e:
        logger.warning("File validation failed", error=str(e))
        raise convert_to_http_exception(e) from e
    except PVBBaseException as e:
        logger.error("PVB import failed", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error during import", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import PVB data: {str(e)}"
        ) from e


# ===================== Violation Operations =====================

@router.get("/violations", response_model=PaginatedPVBViolationResponse)
async def list_violations(
    violation_id: Optional[int] = Query(None, description="Violation ID"),
    plate_number: Optional[str] = Query(None, description="Comma-separated plate numbers"),
    summons_number: Optional[str] = Query(None, description="Comma-separated summons numbers"),
    state: Optional[str] = Query(None, description="Comma-separated states"),
    vehicle_type: Optional[str] = Query(None, description="Comma-separated vehicle types"),
    record_status: Optional[str] = Query(None, description="Comma-separated statuses"),
    vehicle_id: Optional[str] = Query(None, description="Comma-separated vehicle IDs"),
    driver_id: Optional[str] = Query(None, description="Comma-separated driver IDs"),
    medallion_id: Optional[str] = Query(None, description="Comma-separated medallion IDs"),
    issue_from_date: Optional[date] = Query(None, description="Issue date from"),
    issue_to_date: Optional[date] = Query(None, description="Issue date to"),
    issue_time_from: Optional[str] = Query(None, description="Issue time from"),
    issue_time_to: Optional[str] = Query(None, description="Issue time to"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("updated_on", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    pvb_service: PVBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    List PVB violations with optional filters, sorting, and pagination.
    """
    logger.info("List violations request received", page=page, per_page=per_page)

    try:
        filters = PVBViolationFilters(
            violation_id=violation_id,
            plate_number=plate_number,
            summons_number=summons_number,
            state=state,
            vehicle_type=vehicle_type,
            record_status=record_status,
            vehicle_id=vehicle_id,
            driver_id=driver_id,
            medallion_id=medallion_id,
            issue_from_date=issue_from_date,
            issue_to_date=issue_to_date,
            issue_time_from=issue_time_from,
            issue_time_to=issue_time_to,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )

        violations, total_count = await pvb_service.get_violations(filters)

        violations_data = [
            PVBViolationResponse.model_validate(v) for v in violations
        ]

        response = PaginatedPVBViolationResponse(
            items=violations_data,
            total_items=total_count,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total_count / per_page)
        )

        logger.info("Violations listed successfully", count=len(violations_data))
        return response

    except PVBBaseException as e:
        logger.error("Error listing violations", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error listing violations", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list violations: {str(e)}"
        ) from e


@router.get("/violation/{violation_id}", response_model=PVBViolationResponse)
async def get_violation(
    violation_id: int,
    pvb_service: PVBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific PVB violation by ID.
    """
    logger.info("Get violation request", violation_id=violation_id)

    try:
        violation = await pvb_service.get_violation_by_id(violation_id)
        response = PVBViolationResponse.model_validate(violation)

        logger.info("Violation retrieved successfully", violation_id=violation_id)
        return response

    except PVBBaseException as e:
        logger.error("Error retrieving violation", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error retrieving violation", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve violation: {str(e)}"
        ) from e


@router.put("/violation/{violation_id}", response_model=PVBViolationResponse)
async def update_violation(
    violation_id: int,
    update_data: PVBViolationUpdate,
    pvb_service: PVBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Update a specific PVB violation by ID.
    """
    logger.info("Update violation request", violation_id=violation_id)

    try:
        violation = await pvb_service.update_violation(violation_id, update_data)
        response = PVBViolationResponse.model_validate(violation)

        logger.info("Violation updated successfully", violation_id=violation_id)
        return response

    except PVBBaseException as e:
        logger.error("Error updating violation", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error updating violation", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update violation: {str(e)}"
        ) from e


@router.delete("/violation/{violation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_violation(
    violation_id: int,
    pvb_service: PVBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Delete (archive) a specific PVB violation by ID.
    """
    logger.info("Delete violation request", violation_id=violation_id)

    try:
        await pvb_service.delete_violation(violation_id)
        logger.info("Violation deleted successfully", violation_id=violation_id)

    except PVBBaseException as e:
        logger.error("Error deleting violation", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error deleting violation", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete violation: {str(e)}"
        ) from e


@router.post("/associate", response_model=PVBAssociationResult)
async def associate_violations(
    pvb_service: PVBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Associate imported PVB violations with drivers, medallions, and vehicles.

    This process matches violations to existing records in the system based on
    plate numbers and vehicle registrations.
    """
    logger.info("Associate violations request received", user_id=current_user.id)

    try:
        result = await pvb_service.associate_violations()
        logger.info(
            "Violations association completed",
            associated_count=result.associated_count,
            failed_count=result.failed_count
        )
        return result

    except PVBBaseException as e:
        logger.error("Error associating violations", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error associating violations", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to associate violations: {str(e)}"
        ) from e


@router.post("/post", response_model=PVBPostingResult)
async def post_violations(
    pvb_service: PVBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Post associated PVB violations to the central ledger.

    This creates ledger entries for all associated violations.
    """
    logger.info("Post violations request received", user_id=current_user.id)

    try:
        result = await pvb_service.post_violations()
        logger.info(
            "Violations posting completed",
            posted_count=result.posted_count,
            failed_count=result.failed_count
        )
        return result

    except PVBBaseException as e:
        logger.error("Error posting violations", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error posting violations", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to post violations: {str(e)}"
        ) from e


@router.get("/export")
async def export_violations(
    format: str = Query("excel", description="Export format: excel, csv, pdf"),
    violation_id: Optional[int] = Query(None),
    plate_number: Optional[str] = Query(None),
    summons_number: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    record_status: Optional[str] = Query(None),
    pvb_service: PVBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Export PVB violations to Excel, CSV, or PDF.
    """
    logger.info("Export violations request", format=format)

    try:
        # Get violations with filters
        filters = PVBViolationFilters(
            violation_id=violation_id,
            plate_number=plate_number,
            summons_number=summons_number,
            state=state,
            record_status=record_status,
            page=1,
            per_page=10000  # Export up to 10k records
        )

        violations, _ = await pvb_service.get_violations(filters)

        if not violations:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No violations found for export"
            )

        # Convert to dictionaries
        data = []
        for v in violations:
            data.append({
                "ID": v.id,
                "Plate Number": v.plate_number,
                "State": v.state,
                "Vehicle Type": v.vehicle_type,
                "Summons Number": v.summons_number,
                "Issue Date": str(v.issue_date),
                "Issue Time": v.issue_time,
                "Amount Due": v.amount_due,
                "Amount Paid": v.amount_paid,
                "Status": v.status,
                "Driver ID": v.driver_id,
                "Medallion ID": v.medallion_id,
                "Vehicle ID": v.vehicle_id,
            })

        # Export using ExporterFactory
        exporter = ExporterFactory.get_exporter(format, data)
        file_bytes: BytesIO = exporter.export()

        # Determine content type and filename
        content_types = {
            "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "csv": "text/csv",
            "pdf": "application/pdf"
        }
        extensions = {
            "excel": "xlsx",
            "csv": "csv",
            "pdf": "pdf"
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"pvb_violations_{timestamp}.{extensions.get(format, 'xlsx')}"
        content_type = content_types.get(format, content_types["excel"])

        logger.info("Export completed", format=format, record_count=len(data))

        return StreamingResponse(
            file_bytes,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error exporting violations", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting violations"
        ) from e


# ===================== Log Operations =====================

@router.get("/logs", response_model=PaginatedPVBLogResponse)
async def list_logs(
    log_id: Optional[int] = Query(None, description="Log ID"),
    log_from_date: Optional[datetime] = Query(None, description="Log date from"),
    log_to_date: Optional[datetime] = Query(None, description="Log date to"),
    log_type: Optional[str] = Query(None, description="Comma-separated types"),
    log_status: Optional[str] = Query(None, description="Comma-separated statuses"),
    records_impacted: Optional[int] = Query(None, description="Records impacted"),
    success_count: Optional[int] = Query(None, description="Success count"),
    unidentified_count: Optional[int] = Query(None, description="Unidentified count"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("log_date", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    pvb_service: PVBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    List PVB logs with optional filters, sorting, and pagination.
    """
    logger.info("List logs request received", page=page, per_page=per_page)

    try:
        filters = PVBLogFilters(
            log_id=log_id,
            log_from_date=log_from_date,
            log_to_date=log_to_date,
            log_type=log_type,
            log_status=log_status,
            records_impacted=records_impacted,
            success_count=success_count,
            unidentified_count=unidentified_count,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )

        logs, total_count = await pvb_service.get_logs(filters)

        logs_data = [PVBLogResponse.model_validate(log) for log in logs]

        response = PaginatedPVBLogResponse(
            items=logs_data,
            total_items=total_count,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total_count / per_page)
        )

        logger.info("Logs listed successfully", count=len(logs_data))
        return response

    except PVBBaseException as e:
        logger.error("Error listing logs", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error listing logs", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list logs: {str(e)}"
        ) from e


@router.get("/log/{log_id}", response_model=PVBLogResponse)
async def get_log(
    log_id: int,
    pvb_service: PVBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific PVB log by ID.
    """
    logger.info("Get log request", log_id=log_id)

    try:
        log = await pvb_service.get_log_by_id(log_id)
        response = PVBLogResponse.model_validate(log)

        logger.info("Log retrieved successfully", log_id=log_id)
        return response

    except PVBBaseException as e:
        logger.error("Error retrieving log", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error retrieving log", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve log: {str(e)}"
        ) from e