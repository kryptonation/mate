## app/drivers/router.py

# Standard library imports
import csv
from io import StringIO , BytesIO
from typing import Optional
from datetime import date
import math

# Third party imports
from fastapi import (
    APIRouter, Depends, HTTPException, Query
)
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

# Local imports
from app.core.db import get_db
from app.utils.logger import get_logger
from app.users.utils import get_current_user
from app.users.models import User
from app.drivers.services import driver_service
from app.audit_trail.services import audit_trail_service
from app.drivers.utils import format_driver_response
from app.drivers.search_service import (
    build_driver_query, get_total_items, get_paginated_results , driver_lease_report,
    get_formatted_drivers
)
from app.uploads.services import upload_service
from app.leases.services import lease_service
from app.ledger.services import ledger_service
from app.utils.exporter.excel_exporter import ExcelExporter
from app.utils.exporter.pdf_exporter import PDFExporter
from app.drivers.schemas import DriverStatus

logger = get_logger(__name__)
router = APIRouter(tags=["Driver"])

@router.get(
    "/driver/{driver_id}/documents",
    summary="List all documents associated with the driver id"
)
def get_driver_documents(
    driver_id: str,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """
    Fetches documents associated with the specified driver id.
    """
    try:
        # Find the vehicle by vehicle vin
        driver = driver_service.get_drivers(db, driver_id=driver_id)

        if not driver:
            raise HTTPException(
                status_code=404, detail=f"Driver with driver id {driver_id} not found"
            )

        return {
            "driver_details": driver.to_dict(),
            "documents": upload_service.get_documents(
                db, object_type="driver", object_id=driver.id, multiple=True
            )
        }
    except Exception as e:
        logger.error("Error fetching driver documents: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    
@router.get("/drivers", summary="List all drivers with detailed information", tags=["Drivers"])
def search_drivers(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query(None),

    # Filters
    driver_lookup_id: Optional[str] = None,
    tlc_license_number: Optional[str] = None,
    dmv_license_number: Optional[str] = None,
    vin : Optional[str] = None,
    medallion_number : Optional[str] = None,
    ssn: Optional[str] = None,
    driver_name : Optional[str] = None,
    driver_type: Optional[str] = None,
    driver_status: Optional[str] = None,
    tlc_license_expiry_from: Optional[date] = None,
    tlc_license_expiry_to: Optional[date] = None,
    dmv_license_expiry_from: Optional[date] = None,
    dmv_license_expiry_to: Optional[date] = None,
    has_documents: Optional[bool] = None,
    has_vehicle: Optional[bool] = None,
    has_active_lease: Optional[bool] = None,
    is_drive_locked: Optional[bool] = None,
    lease_type: Optional[str] = None,
    is_archived: Optional[bool] = None,
):
    """Search for drivers based on the provided filters"""
    try:
        filters = {
            "driver_lookup_id": driver_lookup_id,
            "tlc_license_number": tlc_license_number,
            "dmv_license_number": dmv_license_number,
            "ssn": ssn,
            "vin": vin,
            "medallion_number": medallion_number,
            "driver_name": driver_name,
            "driver_type": driver_type,
            "driver_status": driver_status,
            "tlc_license_expiry_from": tlc_license_expiry_from,
            "tlc_license_expiry_to": tlc_license_expiry_to,
            "dmv_license_expiry_from": dmv_license_expiry_from,
            "dmv_license_expiry_to": dmv_license_expiry_to,
            "has_documents": has_documents,
            "has_vehicle": has_vehicle,
            "has_active_lease": has_active_lease,
            "is_drive_locked": is_drive_locked,
            "lease_type": lease_type,
            "is_archived": is_archived,
        }

        query, matched_filters = build_driver_query(db, filters, sort_by, sort_order)
        total_items = get_total_items(db, query)
        drivers = get_paginated_results(query, page, per_page)

        driver_status_list = [key.value for key in DriverStatus if key.value != "In Progress"]
        driver_type_list = ["Regular", "WAV"]
        lease_type_list = ["short-term", "long-term", "dov", "medallion-only"]

        items = get_formatted_drivers(drivers, db) if drivers else []

        return {
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "items": items,
            "matched_filters": matched_filters,
            "driver_status_list": driver_status_list,
            "driver_type_list": driver_type_list,
            "lease_type_list": lease_type_list,
        }

    except Exception as e:
        logger.exception("Error listing drivers")
        raise HTTPException(
            status_code=500, detail="Internal error while retrieving drivers"
        ) from e
@router.get("/view/driver/{driver_id}", summary="View driver details")
def view_driver_details(
    driver_id:str,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    trip_start_date: Optional[date] = None,
    trip_end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """View Driver Details"""
    try:
        if not driver_id:
            raise HTTPException(status_code=400, detail="Driver ID is required")
        
        driver = driver_service.get_drivers(db=db , driver_id=driver_id)

        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        driver_details = format_driver_response(driver)

        lease_drivers = lease_service.get_lease_drivers(db=db , driver_id=driver_id , multiple=True)
        leases = [driver.lease.to_dict() for driver in lease_drivers] if lease_drivers else []
        trips = []
        revenue = 0.0
        documents = upload_service.get_documents(db=db , object_type="driver" , object_id=driver.id , multiple=True)
        driver_history = audit_trail_service.get_related_audit_trail(db=db , driver_id=driver.id)
        ledgers = ledger_service.get_ledger_entries(db=db , driver_id=driver.id , multiple=True)

        driver_details["leases"] = leases
        driver_details["documents"] = documents or []
        driver_details["driver_history"] = driver_history or []
        driver_details["ledgers"] = ledgers or []
        driver_details["trips"]= {
            "items": trips,
            "page": page,
            "per_page": per_page,
            "total_items": len(trips),
            "total_pages": math.ceil(len(trips) / per_page),
            "total_revenue": revenue
        }

        return driver_details
    except Exception as e:
        logger.exception("Error viewing driver details")
        raise HTTPException(status_code=500, detail="Internal error while viewing driver details") from e
    
@router.get("/driver/lease_expiry", summary="List of all driver dmv and tlc lincense expiry notifications")
def get_driver_license_expiry(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Page number, starts from 1"),
    per_page: int = Query(10, ge=1, le=100, description="Number of items per page, maximum 100"),

    #filters
    license_type:Optional[str] = Query(enum=["dmv_license","tlc_license"]),
    day_in_advance:Optional[int] = Query(30, description="Filter by day in advance"),
    driver_id:Optional[str] = Query(None, description="Filter by driver id"),
    tlc_license_number:Optional[str] = Query(None, description="Filter by tlc license number"),
    dmv_license_number:Optional[str] = Query(None, description="Filter by dmv license number"),

    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
) : 
    """
    List of all driver dmv and tlc lincense expiry notifications
    """

    try:
        filters = {
            "license_type": license_type,
            "day_in_advance": day_in_advance,
            "driver_id": driver_id,
            "tlc_license_number": tlc_license_number,
            "dmv_license_number": dmv_license_number
        }

        query, matched_filters ,check_date = driver_lease_report(db, filters, sort_by, sort_order)
        total_items = get_total_items(db, query)
        drivers = get_paginated_results(query, page, per_page)

        driver_status_list = [key.value for key in DriverStatus]
        driver_type_list = ["Regular", "WAV"]
        lease_type_list = ["short-term", "long-term", "dov", "medallion-only"]

        items = [format_driver_license(driver) for driver in drivers]

        return {
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "day_in_advance": day_in_advance,
            "license_type": license_type,
            "date_before": check_date,
            "items": items,
            "matched_filters": matched_filters,
            "driver_status_list": driver_status_list,
            "driver_type_list": driver_type_list,
            "lease_type_list": lease_type_list,
        }

    except Exception as e:
        logger.exception("Error listing drivers")
        raise HTTPException(
            status_code=500, detail="Internal error while retrieving drivers"
        ) from e

def format_driver_license(driver):
    """Format driver license details"""
    logger.info("Driver license details: %s", dir(driver.tlc_license))

    return {
        "driver_details": {
            "driver_id": driver.id,
            "driver_lookup_id": driver.driver_id,
            "first_name": driver.first_name,
            "middle_name": driver.middle_name,
            "last_name": driver.last_name,
            "driver_type": driver.driver_type,
            "driver_status": driver.driver_status,
            "driver_ssn": f"XXX-XX-{driver.ssn[-4:]}",
            "dob": driver.dob,
            "phone_number_1": driver.phone_number_1,
            "phone_number_2": driver.phone_number_2,
            "email_address": driver.email_address,
            "primary_emergency_contact_person": driver.primary_emergency_contact_person,
            "primary_emergency_contact_relationship": driver.primary_emergency_contact_relationship,
            "primary_emergency_contact_number": driver.primary_emergency_contact_number,
            "additional_emergency_contact_person": driver.additional_emergency_contact_person,
            "additional_emergency_contact_relationship": driver.additional_emergency_contact_relationship,
            "additional_emergency_contact_number": driver.additional_emergency_contact_number,
            "violation_due_at_registration": driver.violation_due_at_registration,
            "is_drive_locked": driver.drive_locked,
            "has_audit_trail": True,  # Default to True as requested
        },
        "dmv_license_details": {
            "is_dmv_license_active": True if driver.dmv_license else False,
            "dmv_license_number": driver.dmv_license.dmv_license_number if driver.dmv_license else None,
            "dmv_license_issued_state": driver.dmv_license.dmv_license_issued_state if driver.dmv_license else None,
            "dmv_license_expiry_date": driver.dmv_license.dmv_license_expiry_date if driver.dmv_license else None,
        },
        "tlc_license_details": {
            "is_tlc_license_active": True if driver.tlc_license else False,
            "tlc_license_number": driver.tlc_license.tlc_license_number if driver.tlc_license else None,
            "tlc_license_expiry_date": driver.tlc_license.tlc_license_expiry_date if driver.tlc_license else None,
        },
        "primary_address_details": {
            "address_line_1": driver.primary_driver_address.address_line_1 if driver.primary_driver_address else None,
            "address_line_2": driver.primary_driver_address.address_line_2 if driver.primary_driver_address else None,
            "city": driver.primary_driver_address.city if driver.primary_driver_address else None,
            "state": driver.primary_driver_address.state if driver.primary_driver_address else None,
            "zip": driver.primary_driver_address.zip if driver.primary_driver_address else None,
            "latitude": driver.primary_driver_address.latitude if driver.primary_driver_address else None,
            "longitude": driver.primary_driver_address.longitude if driver.primary_driver_address else None
        },
        "secondary_address_details": {
            "latitude": driver.secondary_driver_address.latitude if driver.secondary_driver_address else None,
            "longitude": driver.secondary_driver_address.longitude if driver.secondary_driver_address else None
        },
        "payee_details": {
            "pay_to_mode": driver.pay_to_mode,
            "bank_name": driver.driver_bank_account.bank_name if driver.driver_bank_account else None,
            "bank_account_number": driver.driver_bank_account.bank_account_number if driver.driver_bank_account else None,
            "address_line_1": "",
            "address_line_2": "",
            "city": "",
            "state": "",
            "zip": "",
            "pay_to": driver.pay_to,
        },
        "lease_info": {
            "has_active_lease": has_active_lease,
            "lease_type": driver.lease_drivers[0].lease.lease_type if driver.lease_drivers else None,
        },
        "has_documents": has_documents,
        "has_vehicle": has_vehicle,
        "is_archived": driver.is_archived
    }

    
@router.get("/drivers/export", summary="Export driver search results to CSV", tags=["Driver"])
def export_drivers_to_csv(
    db: Session = Depends(get_db),
    format : Optional[str] = Query("excel", enum=["excel", "pdf"]),
    driver_id: Optional[str] = Query(None, description="Filter by Driver ID (comma-separated)"),
    tlc_license_number: Optional[str] = Query(None, description="Filter by TLC License Number (comma-separated)"),
    dmv_license_number: Optional[str] = Query(None, description="Filter by DMV License Number (comma-separated)"),
    ssn: Optional[str] = Query(None, description="Exact match for SSN"),
    driver_name : Optional[str] = Query(None , description="driver name search"),
    driver_type: Optional[str] = Query(None, description="Filter by driver type"),
    driver_status: Optional[str] = Query(None, description="Filter by driver status"),
    tlc_license_expiry_from: Optional[date] = Query(None, description="TLC License expiry from"),
    tlc_license_expiry_to: Optional[date] = Query(None, description="TLC License expiry to"),
    dmv_license_expiry_from: Optional[date] = Query(None, description="DMV License expiry from"),
    dmv_license_expiry_to: Optional[date] = Query(None, description="DMV License expiry to"),
    has_documents: Optional[bool] = Query(None, description="Filter by document existence"),
    has_vehicle: Optional[bool] = Query(None, description="Filter by vehicle association"),
    has_active_lease: Optional[bool] = Query(None, description="Filter by active lease status"),
    is_drive_locked: Optional[bool] = Query(None, description="Filter by drive locked status"),
    lease_type: Optional[str] = Query(None, description="Filter by lease type"),
    is_archived: Optional[bool] = Query(None, description="Filter by archived status"),

    sort_by: Optional[str] = Query(None, enum=["first_name", "last_name", "driver_type", "tlc_license_number",
                                               "dmv_license_number", "driver_status", "created_on"]),
    sort_order: Optional[str] = Query("asc", enum=["asc", "desc"]),
    logged_in_user: User = Depends(get_current_user)
):
    """
    Export driver search results as a CSV file. Uses the same filtering and sorting as `search_driver`.
    """
    try:
        drivers = search_drivers(
            db=db, page=1, per_page=100000,
            driver_lookup_id=driver_id,
            tlc_license_number=tlc_license_number,
            dmv_license_number=dmv_license_number,
            ssn=ssn,
            driver_name=driver_name,
            driver_type=driver_type,
            driver_status=driver_status,
            tlc_license_expiry_from=tlc_license_expiry_from,
            tlc_license_expiry_to=tlc_license_expiry_to,
            dmv_license_expiry_from=dmv_license_expiry_from,
            dmv_license_expiry_to=dmv_license_expiry_to,
            has_documents=has_documents,
            has_vehicle=has_vehicle,
            has_active_lease=has_active_lease,
            is_drive_locked=is_drive_locked,
            lease_type=lease_type,
            is_archived=is_archived,
            sort_by=sort_by,
            sort_order=sort_order
        )["items"]
        

        driver_list = [{
                    "driver_id": formatted_driver["driver_details"]["driver_id"],
                    "driver_lookup_id": formatted_driver["driver_details"]["driver_lookup_id"],
                    "first_name": formatted_driver["driver_details"]["first_name"],
                    "last_name": formatted_driver["driver_details"]["last_name"],
                    "driver_type": formatted_driver["driver_details"]["driver_type"],
                    "driver_status": formatted_driver["driver_details"]["driver_status"],
                    "driver_ssn": formatted_driver["driver_details"]["driver_ssn"],
                    "is_drive_locked": formatted_driver["driver_details"]["is_drive_locked"],
                    "has_audit_trail": formatted_driver["driver_details"]["has_audit_trail"],
                    "tlc_license_number": formatted_driver["tlc_license_details"]["tlc_license_number"],
                    "tlc_license_expiry_date": formatted_driver["tlc_license_details"]["tlc_license_expiry_date"],
                    "dmv_license_number": formatted_driver["dmv_license_details"]["dmv_license_number"],
                    "dmv_license_expiry_date": formatted_driver["dmv_license_details"]["dmv_license_expiry_date"],
                    "has_documents": formatted_driver["has_documents"],
                    "has_vehicle": formatted_driver["has_vehicle"],
                    "is_archived": formatted_driver["is_archived"],
                    "pay_to_mode": formatted_driver["payee_details"]["pay_to_mode"],
                    "bank_name": formatted_driver["payee_details"]["bank_name"],
                    "bank_account_number": formatted_driver["payee_details"]["bank_account_number"],
                    "address_line_1": formatted_driver["primary_address_details"].get("address_line_1", ""),
                    "address_line_2": formatted_driver["primary_address_details"].get("address_line_2", ""),
                    "city": formatted_driver["primary_address_details"].get("city", ""),
                    "state": formatted_driver["primary_address_details"].get("state", ""),
                    "zip": formatted_driver["primary_address_details"].get("zip", ""),
                    "latitude": formatted_driver["secondary_address_details"].get("latitude", ""),
                    "longitude": formatted_driver["secondary_address_details"].get("longitude", "")
                } for formatted_driver in drivers]


        file = None
        media_type = None
        headers = None
        
        if format == "excel":
            excel_exporter = ExcelExporter(driver_list)
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            headers = {"Content-Disposition": "attachment; filename=driver_export.xlsx"}
        elif format == "pdf":
            pdf_exporter = PDFExporter(driver_list)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            headers = {"Content-Disposition": "attachment; filename=driver_export.pdf"}
        else:
            raise HTTPException(status_code=400, detail="Invalid format")
        
        return StreamingResponse(
            file,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        logger.error("Error exporting drivers: %s", str(e))
        raise HTTPException(status_code=500, detail="Error exporting driver list") from e
    
@router.post("/lock-driver")
def lock_driver(
    driver_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Lock or unlock a driver"""
    try:
        driver = driver_service.get_drivers(db, driver_id=driver_id)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        driver = driver_service.upsert_driver(db, {
            "id": driver.id,
            "drive_locked": not driver.drive_locked
        })

        return JSONResponse({"driver_status": "locked" if driver.drive_locked else "unlocked"})
    except ValueError as e:
        logger.error(e)

@router.post("/remove-additional-driver")
def remove_addition_driver(
    driver_lease_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user)
):
    """Remove an additional driver from a lease"""
    try:
        driver = lease_service.get_lease_drivers(db, lease_driver_id=driver_lease_id)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        driver = lease_service.upsert_lease_driver(db, {
            "id": driver.id,
            "is_active": False
        })

        return JSONResponse({"additional_driver_removal_status": "removed"})
    except Exception as e:
        logger.error("Error removing additional driver: %s", str(e))
        raise HTTPException(status_code=500, detail="Error removing additional driver") from e
    
@router.get("/balances", summary="Get drivers balances")
def get_drivers_balances(
    db: Session = Depends(get_db),
    driver_id: Optional[str] = Query(None, description="Comman separated filter by driver ids"),
    logged_in_user: User = Depends(get_current_user)
):
    """Get drivers balances"""
    try:
        if driver_id:
            driver_ids = driver_id.split(",")
            ledgers = ledger_service.get_ledger_entries(db, driver_id=driver_ids, multiple=True)
        else:
            ledgers = ledger_service.get_ledger_entries(db, multiple=True)

        return JSONResponse({"ledgers": ledgers})
    except Exception as e:
        logger.error("Error getting drivers balances: %s", str(e))
        raise HTTPException(status_code=500, detail="Error getting drivers balances") from e

