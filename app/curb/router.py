# app/curb/router.py

"""
FastAPI router for CURB (Taxi Fleet) operations with async endpoints.
"""

import math
from datetime import datetime, date
from typing import Optional
from io import BytesIO

from fastapi import (
    APIRouter, Depends, HTTPException, Query, status
)
from fastapi.responses import StreamingResponse

from app.core.config import settings
from app.curb.services import CURBService
from app.curb.schemas import (
    CURBTripResponse, PaginatedCURBTripResponse,
    CURBImportLogResponse, PaginatedCURBImportLogResponse,
    CURBTripUpdate, CURBTripFilters, CURBImportLogFilters,
    CURBImportResult, CURBReconciliationResult,
    CURBPostingResult,
)
from app.curb.exceptions import (
    CURBBaseException, convert_to_http_exception,
)
from app.curb.soap_client import fetch_trips_log10, fetch_trans_by_date_cab12
from app.users.models import User
from app.users.utils import get_current_user
from app.utils.logger import get_logger
from app.utils.exporter_utils import ExporterFactory

logger = get_logger(__name__)
router = APIRouter(tags=["CURB"], prefix="/curb")


# ===================== Import Operations =====================

@router.post("/import", response_model=CURBImportResult, status_code=status.HTTP_201_CREATED)
async def import_trips(
    from_date: str = Query(..., description="Start date in MM/DD/YYYY format"),
    to_date: str = Query(..., description="End date in MM/DD/YYYY format"),
    driver_id: Optional[str] = Query("", description="Driver ID filter"),
    cab_number: Optional[str] = Query("", description="Cab number filter"),
    recon_stat: int = Query(-1, description="Reconciliation status filter"),
    curb_service: CURBService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Import CURB trips from the CURB API for a specified date range.
    
    Fetches both card transactions and cash trips, merges them, and imports into database.
    """
    logger.info(
        "CURB import request received",
        from_date=from_date,
        to_date=to_date,
        user_id=current_user.id
    )

    try:
        # Fetch card transactions
        card_xml = fetch_trans_by_date_cab12(
            from_datetime=from_date,
            to_datetime=to_date,
            cab_number=cab_number
        )
        
        # Fetch cash trips
        cash_xml = fetch_trips_log10(
            from_date=from_date,
            to_date=to_date,
            recon_stat=recon_stat,
            cab_number=cab_number,
            driver_id=driver_id
        )

        if not card_xml and not cash_xml:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No trip data found for the specified date range"
            )

        # Import trips
        result = await curb_service.import_trips(
            xml_data=card_xml,
            cash_xml_data=cash_xml,
            import_source="SOAP",
            import_by=current_user.username if hasattr(current_user, 'username') else str(current_user.id)
        )

        logger.info(
            "CURB import completed",
            log_id=result.log_id,
            success_count=result.success_count,
        )

        return result

    except CURBBaseException as e:
        logger.error("CURB import failed", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error during import", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import CURB data: {str(e)}"
        ) from e


# ===================== Trip Operations =====================

@router.get("/trips", response_model=PaginatedCURBTripResponse)
async def list_trips(
    trip_id: Optional[int] = Query(None, description="Trip ID"),
    record_id: Optional[str] = Query(None, description="Record ID"),
    period: Optional[str] = Query(None, description="Period"),
    driver_id: Optional[str] = Query(None, description="Comma-separated driver IDs"),
    cab_number: Optional[str] = Query(None, description="Comma-separated cab numbers"),
    start_date_from: Optional[date] = Query(None, description="Start date from"),
    start_date_to: Optional[date] = Query(None, description="Start date to"),
    end_date_from: Optional[date] = Query(None, description="End date from"),
    end_date_to: Optional[date] = Query(None, description="End date to"),
    payment_type: Optional[str] = Query(None, description="Comma-separated payment types (T,P,C)"),
    is_reconciled: Optional[bool] = Query(None, description="Reconciliation status"),
    is_posted: Optional[bool] = Query(None, description="Posting status"),
    status: Optional[str] = Query(None, description="Comma-separated statuses"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("updated_on", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    curb_service: CURBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    List CURB trips with optional filters, sorting, and pagination.
    """
    logger.info("Listing CURB trips", page=page, per_page=per_page)

    try:
        filters = CURBTripFilters(
            trip_id=trip_id,
            record_id=record_id,
            period=period,
            driver_id=driver_id,
            cab_number=cab_number,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            end_date_from=end_date_from,
            end_date_to=end_date_to,
            payment_type=payment_type,
            is_reconciled=is_reconciled,
            is_posted=is_posted,
            status=status,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        trips, total_count = await curb_service.get_trips(filters)

        return PaginatedCURBTripResponse(
            items=[CURBTripResponse.model_validate(trip) for trip in trips],
            total_items=total_count,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total_count / per_page) if total_count > 0 else 0,
        )

    except CURBBaseException as e:
        logger.error("Failed to list trips", error=str(e))
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error listing trips", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list trips: {str(e)}"
        ) from e


@router.get("/trips/{trip_id}", response_model=CURBTripResponse)
async def get_trip(
    trip_id: int,
    curb_service: CURBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific CURB trip by ID.
    """
    logger.info("Getting CURB trip", trip_id=trip_id)

    try:
        trip = await curb_service.get_trip_by_id(trip_id)
        return CURBTripResponse.model_validate(trip)

    except CURBBaseException as e:
        logger.error("Failed to get trip", trip_id=trip_id, error=str(e))
        raise convert_to_http_exception(e) from e


@router.patch("/trips/{trip_id}", response_model=CURBTripResponse)
async def update_trip(
    trip_id: int,
    trip_data: CURBTripUpdate,
    curb_service: CURBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Update a CURB trip.
    """
    logger.info("Updating CURB trip", trip_id=trip_id)

    try:
        trip = await curb_service.update_trip(trip_id, trip_data)
        return CURBTripResponse.model_validate(trip)

    except CURBBaseException as e:
        logger.error("Failed to update trip", trip_id=trip_id, error=str(e))
        raise convert_to_http_exception(e) from e


@router.get("/trips/export/{format}")
async def export_trips(
    format: str,
    trip_id: Optional[int] = Query(None),
    record_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    driver_id: Optional[str] = Query(None),
    cab_number: Optional[str] = Query(None),
    start_date_from: Optional[date] = Query(None),
    start_date_to: Optional[date] = Query(None),
    payment_type: Optional[str] = Query(None),
    is_reconciled: Optional[bool] = Query(None),
    is_posted: Optional[bool] = Query(None),
    sort_by: str = Query("updated_on"),
    sort_order: str = Query("desc"),
    curb_service: CURBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Export CURB trips to Excel or PDF format.
    """
    logger.info("Exporting CURB trips", format=format)

    try:
        # Get trips with filters
        filters = CURBTripFilters(
            trip_id=trip_id,
            record_id=record_id,
            period=period,
            driver_id=driver_id,
            cab_number=cab_number,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            payment_type=payment_type,
            is_reconciled=is_reconciled,
            is_posted=is_posted,
            page=1,
            per_page=10000,  # Large limit for export
            sort_by=sort_by,
            sort_order=sort_order,
        )

        trips, _ = await curb_service.get_trips(filters)

        if not trips:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No trips available to export"
            )

        # Prepare export data
        trips_data = [
            {
                "Trip ID": trip.id,
                "Record ID": trip.record_id,
                "Period": trip.period,
                "Driver ID": trip.driver_id,
                "Cab Number": trip.cab_number,
                "Start Date": trip.start_date,
                "End Date": trip.end_date,
                "Start Time": trip.start_time,
                "End Time": trip.end_time,
                "Trip Amount": trip.trip_amount,
                "Tips": trip.tips,
                "Extras": trip.extras,
                "Tolls": trip.tolls,
                "Tax": trip.tax,
                "Total Amount": trip.total_amount,
                "Payment Type": trip.payment_type,
                "Is Reconciled": trip.is_reconciled,
                "Is Posted": trip.is_posted,
                "Status": trip.status,
            }
            for trip in trips
        ]

        # Export using factory
        exporter = ExporterFactory.get_exporter(format, trips_data)
        exported_data: BytesIO = exporter.export()

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

        logger.info("Export completed", format=format, record_count=len(trips_data))

        return StreamingResponse(
            exported_data,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error exporting trips", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting trips"
        ) from e


# ===================== Reconciliation Operations =====================

@router.post("/reconcile", response_model=CURBReconciliationResult)
async def reconcile_trips(
    trip_ids: list[int] = Query(..., description="List of trip IDs to reconcile"),
    recon_stat: Optional[int] = Query(None, description="Reconciliation receipt number"),
    curb_service: CURBService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Reconcile CURB trips.
    
    For dev/uat: reconciles locally without calling CURB API.
    For production: calls CURB API to reconcile on server.
    """
    logger.info("Reconciliation request received", trip_count=len(trip_ids))

    try:
        # Determine environment
        is_production = settings.environment.lower() == "production"
        
        if is_production:
            # Production: reconcile on server
            if not recon_stat:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="recon_stat is required for production reconciliation"
                )
            
            result = await curb_service.reconcile_trips_on_server(
                trip_ids=trip_ids,
                recon_stat=recon_stat,
                recon_by=current_user.first_name if hasattr(current_user, 'first_name') else str(current_user.id)
            )
        else:
            # Dev/UAT: reconcile locally
            result = await curb_service.reconcile_trips_locally(
                trip_ids=trip_ids,
                recon_stat=recon_stat,
                recon_by=current_user.first_name if hasattr(current_user, 'first_name') else str(current_user.id)
            )

        logger.info("Reconciliation completed", reconciled=result.reconciled_count)
        return result

    except CURBBaseException as e:
        logger.error("Reconciliation failed", error=str(e))
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error during reconciliation", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation failed: {str(e)}"
        ) from e


# ===================== Posting Operations =====================

@router.post("/post", response_model=CURBPostingResult)
async def post_trips(
    curb_service: CURBService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Post reconciled CURB trips to ledger.
    
    Processes all reconciled but unposted trips.
    """
    logger.info("Posting request received")

    try:
        result = await curb_service.associate_and_post_trips(
            posted_by=current_user.first_name if hasattr(current_user, 'first_name') else str(current_user.id)
        )

        logger.info("Posting completed", posted=result.posted_count)
        return result

    except CURBBaseException as e:
        logger.error("Posting failed", error=str(e))
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error during posting", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Posting failed: {str(e)}"
        ) from e


# ===================== Import Log Operations =====================

@router.get("/logs", response_model=PaginatedCURBImportLogResponse)
async def list_import_logs(
    log_id: Optional[int] = Query(None, description="Log ID"),
    import_source: Optional[str] = Query(None, description="Import source"),
    imported_by: Optional[str] = Query(None, description="Imported by"),
    import_start_from: Optional[datetime] = Query(None, description="Import start from"),
    import_start_to: Optional[datetime] = Query(None, description="Import start to"),
    status: Optional[str] = Query(None, description="Comma-separated statuses"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("import_start", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    curb_service: CURBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    List CURB import logs with optional filters, sorting, and pagination.
    """
    logger.info("Listing CURB import logs", page=page, per_page=per_page)

    try:
        filters = CURBImportLogFilters(
            log_id=log_id,
            import_source=import_source,
            imported_by=imported_by,
            import_start_from=import_start_from,
            import_start_to=import_start_to,
            status=status,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        logs, total_count = await curb_service.get_import_logs(filters)

        return PaginatedCURBImportLogResponse(
            items=[CURBImportLogResponse.model_validate(log) for log in logs],
            total_items=total_count,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total_count / per_page) if total_count > 0 else 0,
        )

    except CURBBaseException as e:
        logger.error("Failed to list import logs", error=str(e))
        raise convert_to_http_exception(e) from e


@router.get("/logs/{log_id}", response_model=CURBImportLogResponse)
async def get_import_log(
    log_id: int,
    curb_service: CURBService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific CURB import log by ID.
    """
    logger.info("Getting CURB import log", log_id=log_id)

    try:
        log = await curb_service.get_import_log_by_id(log_id)
        return CURBImportLogResponse.model_validate(log)

    except CURBBaseException as e:
        logger.error("Failed to get import log", log_id=log_id, error=str(e))
        raise convert_to_http_exception(e) from e