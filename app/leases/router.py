### app/leases/router.py

import base64
from datetime import date
from io import BytesIO
from typing import Any, Dict, Optional

import aiohttp
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.audit_trail.services import audit_trail_service
from app.core.config import settings
from app.core.db import get_db
from app.leases.schemas import LeasePresetCreate, LeasePresetResponse, LeasePresetUpdate
from app.leases.search_service import format_lease_export, format_lease_response

# from app.esign.docusign_client import client
from app.leases.services import lease_service
from app.leases.utils import (
    calculate_short_term_lease_schedule,
    calculate_weekly_lease_schedule,
)
from app.uploads.services import upload_service
from app.users.models import User
from app.users.utils import get_current_user
from app.utils.exporter.excel_exporter import ExcelExporter
from app.utils.exporter.pdf_exporter import PDFExporter
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Leases"])


@router.get("/can_lease", summary="List Of vehicle can Create Lease")
def can_lease(
    db: Session = Depends(get_db),
    vin: Optional[str] = Query(None, description="Filter by VIN number"),
    medallion_number: Optional[str] = Query(
        None, description="Filter by medallion number"
    ),
    plate_number: Optional[str] = Query(None, description="Filter by plate number"),
    page: int = Query(1, description="Page number"),
    per_page: int = Query(10, description="Number of leases per page"),
    sort_by: Optional[str] = Query("created_on", description="Sort by field"),
    sort_order: Optional[str] = Query("desc", description="Sort order"),
):
    """List Of vehicle can Create Lease"""

    try:
        results, total_count = lease_service.get_can_lease(
            db=db,
            vin=vin,
            medallion_number=medallion_number,
            plate_number=plate_number,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
            multiple=True,
        )

        return {
            "items": results,
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "total_pages": total_count // per_page + 1
            if total_count % per_page
            else total_count // per_page,
        }
    except Exception as e:
        logger.error("Error retrieving can lease list: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500, detail="Error retrieving can lease list"
        ) from e


@router.get("/lease/{lease_id}/documents/preview", tags=["Leases"])
async def get_lease_documents_preview(
    lease_id: str, db: Session = Depends(get_db), _: User = Depends(get_current_user)
):
    """Get preview of all documents associated with a lease from DocuSign"""
    try:
        # Get the lease
        lease = lease_service.get_lease(db, lease_id=lease_id)

        if not lease:
            raise HTTPException(status_code=404, detail="Lease not found")

        # Get all active lease driver documents
        lease_driver_docs = []
        for lease_driver in lease.lease_driver:
            if not lease_driver.is_active:
                continue

            doc = lease_service.get_lease_driver_documents(
                db, lease_driver_id=lease_driver.id, status=True
            )

            if doc and doc.document_envelope_id:
                lease_driver_docs.append(doc)

        if not lease_driver_docs:
            return []
        # Initialize DocuSign client
        # access_token = client.get_access_token()
        access_token = "1234567890"

        # Get document previews
        previews = []
        for doc in lease_driver_docs:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/pdf",
            }

            # Using DocuSign's combined PDF endpoint
            url = (
                f"{settings.docusign_base_url}/restapi/v2.1/accounts/{settings.docusign_account_id}"
                f"/envelopes/{doc.document_envelope_id}/documents/combined"
            )

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        content = await response.read()
                        base64_pdf = base64.b64encode(content).decode("utf-8")
                        previews.append(
                            {
                                "lease_driver_id": doc.lease_driver_id,
                                "envelope_id": doc.document_envelope_id,
                                "has_frontend_signed": doc.has_frontend_signed,
                                "has_driver_signed": doc.has_driver_signed,
                                "preview_base64": base64_pdf,
                                "content_type": "application/pdf",
                                "filename": f"lease_doc_{doc.lease_driver_id}.pdf",
                            }
                        )
                    else:
                        error_text = await response.text()
                        logger.error(
                            "Failed to get document preview for envelope %s: %s",
                            doc.document_envelope_id,
                            error_text,
                        )
                        continue

        return previews

    except Exception as e:
        logger.error("Error getting lease document previews: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/leases", summary="List all the leases", tags=["Leases"])
def list_leases(
    db: Session = Depends(get_db),
    page: int = Query(1, description="Page number"),
    per_page: int = Query(10, description="Number of leases per page"),
    lease_id: Optional[str] = Query(None, description="Filter by lease ID"),
    medallion_no: Optional[str] = Query(None, description="Filter by medallion number"),
    driver_id: Optional[str] = Query(None, description="Filter by driver ID"),
    driver_name: Optional[str] = Query(None, description="Filter by driver name"),
    vin_no: Optional[str] = Query(None, description="Filter by VIN number"),
    lease_type: Optional[str] = Query(None, description="Filter by lease type"),
    plate_no: Optional[str] = Query(None, description="Filter by plate number"),
    lease_start_date: Optional[date] = Query(
        None, description="Filter by lease start date"
    ),
    lease_end_date: Optional[date] = Query(
        None, description="Filter by lease end date"
    ),
    status: Optional[str] = Query(None, description="Filter by lease status"),
    sort_by: Optional[str] = Query("created_on", description="Sort by field"),
    sort_order: Optional[str] = Query("desc", description="Sort order"),
    logged_in_user: User = Depends(get_current_user),
):
    """List all the leases"""
    try:
        leases, total_count = lease_service.get_lease(
            db=db,
            page=page,
            per_page=per_page,
            lease_id=lease_id,
            is_lease_list=True,
            medallion_number=medallion_no,
            lease_type=lease_type,
            driver_id=driver_id,
            driver_name=driver_name,
            vin_number=vin_no,
            plate_number=plate_no,
            lease_start_date=lease_start_date,
            lease_end_date=lease_end_date,
            status=status,
            sort_by=sort_by,
            sort_order=sort_order,
            multiple=True,
        )

        lease_info = [format_lease_response(db, lease) for lease in leases]
        lease_types = ["long-term", "dov", "short-term", "medallion-only"]

        return {
            "items": lease_info,
            "total_count": total_count,
            "lease_types": lease_types,
            "page": page,
            "per_page": per_page,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
    except Exception as e:
        logger.exception("Error retrieving lease list")
        raise HTTPException(status_code=500, detail="Error retrieving leases") from e


@router.get("/view/lease/{leaseId}", summary="View a lease details", tags=["Leases"])
def view_lease(
    leaseId: str,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user),
):
    """View a lease details"""
    try:
        if not leaseId:
            raise HTTPException(status_code=400, detail="Lease ID is required")
        lease = lease_service.get_lease(db=db, lease_id=leaseId)
        if not lease:
            raise HTTPException(status_code=404, detail="Lease not found")

        lease_drivers = lease_service.get_lease_drivers(
            db=db, lease_id=lease.id, multiple=True
        )
        main_drivers = (
            [
                lease.driver.to_dict()
                for lease in lease_drivers
                if int(lease.co_lease_seq or 0) == 0
            ]
            if lease_drivers
            else []
        )
        additional_drivers = (
            [
                lease.driver.to_dict()
                for lease in lease_drivers
                if int(lease.co_lease_seq or 0) > 0
            ]
            if lease_drivers
            else []
        )
        documents = upload_service.get_documents(
            db=db, object_type="lease", object_id=lease.id, multiple=True
        )
        history = audit_trail_service.get_related_audit_trail(db=db, lease_id=lease.id)

        lease_details = lease.to_dict()
        lease_details["drivers"] = main_drivers
        lease_details["additional_drivers"] = additional_drivers
        lease_details["documents"] = documents or []
        lease_details["history"] = history or []

        return lease_details
    except Exception as e:
        logger.error("Error retrieving lease details: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500, detail="Error retrieving lease details"
        ) from e


@router.get("/lease/export", summary="Export all the leases", tags=["Leases"])
def export_leases(
    db: Session = Depends(get_db),
    format: Optional[str] = Query("excel", enum=["excel", "pdf"]),
    page: int = Query(None, description="Page number"),
    per_page: int = Query(None, description="Number of leases per page"),
    lease_id: Optional[str] = Query(None, description="Filter by lease ID"),
    medallion_no: Optional[str] = Query(None, description="Filter by medallion number"),
    driver_id: Optional[str] = Query(None, description="Filter by driver ID"),
    driver_name: Optional[str] = Query(None, description="Filter by driver name"),
    vin_no: Optional[str] = Query(None, description="Filter by VIN number"),
    lease_type: Optional[str] = Query(None, description="Filter by lease type"),
    plate_no: Optional[str] = Query(None, description="Filter by plate number"),
    lease_start_date: Optional[date] = Query(
        None, description="Filter by lease start date"
    ),
    lease_end_date: Optional[date] = Query(
        None, description="Filter by lease end date"
    ),
    status: Optional[str] = Query(None, description="Filter by lease status"),
    logged_in_user: User = Depends(get_current_user),
):
    """Export all the leases"""

    try:
        leases, total_count = lease_service.get_lease(
            db=db,
            page=1,
            per_page=1000,
            lease_id=lease_id,
            medallion_number=medallion_no,
            lease_type=lease_type,
            driver_id=driver_id,
            driver_name=driver_name,
            vin_number=vin_no,
            plate_number=plate_no,
            lease_start_date=lease_start_date,
            lease_end_date=lease_end_date,
            status=status,
            multiple=True,
        )

        lease_info = [format_lease_export(db, lease) for lease in leases]

        file = None
        media_type = None
        headers = None

        if format == "excel":
            excel_exporter = ExcelExporter(lease_info)
            file: BytesIO = excel_exporter.export()
            media_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            headers = {"Content-Disposition": "attachment; filename=lease_export.xlsx"}
        elif format == "pdf":
            pdf_exporter = PDFExporter(lease_info)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            headers = {"Content-Disposition": "attachment; filename=lease_export.pdf"}
        else:
            raise HTTPException(status_code=400, detail="Invalid format")

        return StreamingResponse(file, media_type=media_type, headers=headers)
    except Exception as e:
        logger.error("Error exporting lease list: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500, detail="Error exporting Leases list"
        ) from e


@router.get("/lease/{lease_id}/documents", summary="Get lease with documents")
def get_lease_with_documents(
    lease_id: str,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user),
):
    """
    Get lease with documents
    """
    try:
        lease = lease_service.get_lease(db, lease_id=lease_id)
        lease_details = format_lease_response(db, lease)

        if not lease:
            raise HTTPException(
                status_code=404, detail=f"Lease with lease_id {lease_id} not found"
            )

        documents = {
            "documents": upload_service.get_documents(
                db, object_type="lease", object_id=lease.id, multiple=True
            ),
            "lease_details": lease_details,
        }
        return documents

    except Exception as e:
        logger.error("Error in get_medallions_with_documents: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/lease/config", summary="post lease configuration")
def post_lease_configuration(
    db: Session = Depends(get_db),
    config_data: Dict[str, Any] = Body(...),
    logged_in_user: User = Depends(get_current_user),
):
    """Post lease configuration"""
    try:
        for config_type, values in config_data.items():
            lease_service.upsert_lease_payment_configuration(
                db=db, lease_payment_config_data={"config_type": config_type, **values}
            )

        return {"message": "Lease configuration saved successfully"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to save configuration: {str(e)}"
        )


@router.get("/lease/config", summary="get lease configuration")
def get_lease_configuration(
    db: Session = Depends(get_db), logged_in_user: User = Depends(get_current_user)
):
    """Get lease configuration"""
    try:
        config = lease_service.get_lease_payment_configuration(db)
        return config
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get configuration: {str(e)}"
        )


@router.get("/lease/schedule", summary="get lease schedule")
def get_lease_schedule(
    db: Session = Depends(get_db),
    lease_id: str = None,
    logged_in_user: User = Depends(get_current_user),
):
    """Get lease schedule"""

    try:
        lease = lease_service.get_lease(db, lease_id=lease_id)
        if not lease:
            raise HTTPException(status_code=404, detail="Lease not found")

        lease_amount = 0

        if lease.lease_type == "short-term":
            lease_config = lease_service.get_lease_configurations(
                db=db, lease_id=lease.id, multiple=True
            )
            for config in lease_config:
                lease_amount += config.lease_limit

            return calculate_short_term_lease_schedule(
                lease.lease_start_date, 6, lease_amount
            )

        else:
            lease_config = lease_service.get_lease_configurations(
                db=db,
                lease_id=lease.id,
                lease_breakup_type="lease_amount",
                sort_order="desc",
            )
            if lease_config:
                lease_amount = lease_config.lease_limit

            return calculate_weekly_lease_schedule(
                lease.lease_start_date,
                lease.duration_in_weeks,
                lease.lease_pay_day if lease.lease_pay_day else "mon",
                lease_amount,
            )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get schedule: {str(e)}"
        ) from e


# --- LEASE PRESET CRUD ENDPOINTS ---


@router.post(
    "/presets",
    response_model=LeasePresetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new lease price preset",
)
def create_lease_preset(
    preset_data: LeasePresetCreate,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user),
):
    """Creates a new default pricing rule for a combination of lease type and vehicle."""
    try:
        return lease_service.create_lease_preset(db, preset_data)
    except Exception as e:
        logger.error(f"Error creating lease preset: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Could not create lease preset."
        ) from e


@router.get(
    "/presets/{preset_id}",
    response_model=LeasePresetResponse,
    summary="Get a specific lease price preset",
)
def get_lease_preset(
    preset_id: int,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user),
):
    """Retrieves a single lease preset by its ID."""
    preset = lease_service.get_lease_preset(db, preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Lease preset not found.")
    return preset


@router.get("/presets", summary="List all lease price presets")
def list_lease_presets(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    sort_by: str = Query("created_on", description="Field to sort by"),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    lease_type: Optional[str] = Query(None),
    vehicle_make: Optional[str] = Query(None),
    vehicle_model: Optional[str] = Query(None),
    vehicle_year: Optional[int] = Query(None),
    logged_in_user: User = Depends(get_current_user),
):
    """Lists all lease presets with filtering, sorting, and pagination."""
    presets, total_items = lease_service.list_lease_presets(
        db,
        page,
        per_page,
        sort_by,
        sort_order,
        lease_type,
        vehicle_make,
        vehicle_model,
        vehicle_year,
    )
    return {
        "items": [p.to_dict() for p in presets],
        "total_items": total_items,
        "page": page,
        "per_page": per_page,
        "total_pages": (total_items + per_page - 1) // per_page,
    }


@router.put(
    "/presets/{preset_id}",
    response_model=LeasePresetResponse,
    summary="Update a lease price preset",
)
def update_lease_preset(
    preset_id: int,
    preset_data: LeasePresetUpdate,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user),
):
    """Updates an existing lease preset."""
    try:
        return lease_service.update_lease_preset(db, preset_id, preset_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error updating lease preset {preset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Could not update lease preset."
        ) from e


@router.delete(
    "/presets/{preset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a lease price preset",
)
def delete_lease_preset(
    preset_id: int,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user),
):
    """Deletes a lease preset."""
    try:
        lease_service.delete_lease_preset(db, preset_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger.error(f"Error deleting lease preset {preset_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Could not delete lease preset."
        ) from e
