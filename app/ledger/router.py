### app/ledger/router.py

import math
from datetime import datetime , date , time
from typing import Optional
from io import BytesIO


# Third party imports
from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Query
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# Local imports
from app.core.db import get_db
from app.utils.logger import get_logger
from app.audit_trail.services import audit_trail_service
from app.users.models import User
from app.users.utils import get_current_user
from app.ledger.services import ledger_service
from app.drivers.services import driver_service
from app.uploads.services import upload_service
from app.utils.exporter.excel_exporter import ExcelExporter
from app.utils.exporter.pdf_exporter import PDFExporter

logger = get_logger(__name__)
router = APIRouter(prefix="/ledger", tags=["Ledger"])

@router.get("/list" , summary = "List all ledgers")
def list_ledgers(
    db: Session = Depends(get_db),
    ledger_id: int = Query(None, description="Ledger ID"),
    amount_from: Optional[float] = Query(None, description="Minimum amount"),
    amount_to: Optional[float] = Query(None, description="Maximum amount"),
    driver_id: str = Query(None, description="Comma separated list of driver IDs"),
    driver_name : Optional[str] = Query(None, description="Comma separated list of driver names"),
    transaction_date_from : Optional[date] = Query(None, description="Transaction date from"),
    transaction_date_to : Optional[date] = Query(None, description="Transaction date to"),
    transaction_time_from: Optional[time] = Query(None, description="Transaction time from"),
    transaction_time_to: Optional[time] = Query(None, description="Transaction time to"),
    transaction_type: Optional[bool] = Query(None, description="Transaction type (e.g., 'CREDIT 0', 'DEBIT 1')"),
    vin: str = Query(None, description="Comma separated list of vehicle IDs"),
    medallion_number: str = Query(None, description="Comma separated list of medallion numbers"),
    source_type: str = Query(None, description="Source type (e.g., 'driver', 'vehicle')"),
    source_id: str = Query(None, description="Source ID (e.g., driver ID or vehicle ID)"),
    start_date: Optional[date] = Query(None, description="Start date for filtering"),
    end_date: Optional[date] = Query(None, description="End date for filtering"),
    start_time: Optional[time] = Query(None, description="Start time for filtering"),
    end_time: Optional[time] = Query(None, description="End time for filtering"),
    receipt_number: str = Query(None, description="Receipt number for filtering"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    per_page: int = Query(10, ge=1, le=100, description="Number of items per page"),
    sort_by: str = Query("created_on", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    current_user: User = Depends(get_current_user)

):
    """List all ledgers with pagination"""

    try:
        ledgers = ledger_service.search_ledger_entries(
            db,
            ledger_id=ledger_id,
            amount_from=amount_from,
            amount_to=amount_to,
            driver_id=driver_id,
            driver_name=driver_name,
            transaction_date_from=transaction_date_from,
            transaction_date_to=transaction_date_to,
            transaction_time_from=transaction_time_from,
            transaction_time_to=transaction_time_to,
            vin=vin,
            medallion_number=medallion_number,
            transaction_type=transaction_type,
            source_type=source_type,
            source_id=source_id,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            receipt_number=receipt_number,
            page=page,
            page_size=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        return ledgers
    except Exception as e:
        logger.error("Error listing ledgers: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.get("/export", summary="Export ledgers to Excel or PDF")
def export_ledgers(
    db: Session = Depends(get_db),
    format: str = Query("excel", enum = ["excel", "pdf"] , description="Export format (excel or pdf)"),
    ledger_id: int = Query(None, description="Ledger ID"),
    amount_from: Optional[float] = Query(None, description="Minimum amount"),
    amount_to: Optional[float] = Query(None, description="Maximum amount"),
    driver_id: str = Query(None, description="Comma separated list of driver IDs"),
    driver_name : Optional[str] = Query(None, description="Comma separated list of driver names"),
    transaction_date_from : Optional[date] = Query(None, description="Transaction date from"),
    transaction_date_to : Optional[date] = Query(None, description="Transaction date to"),
    transaction_time_from: Optional[time] = Query(None, description="Transaction time from"),
    transaction_time_to: Optional[time] = Query(None, description="Transaction time to"),
    transaction_type: Optional[bool] = Query(None, description="Transaction type (e.g., 'CREDIT 0', 'DEBIT 1')"),
    vin: str = Query(None, description="Comma separated list of vehicle IDs"),
    medallion_number: str = Query(None, description="Comma separated list of medallion numbers"),
    source_type: str = Query(None, description="Source type (e.g., 'driver', 'vehicle')"),
    source_id: str = Query(None, description="Source ID (e.g., driver ID or vehicle ID)"),
    start_date: Optional[date] = Query(None, description="Start date for filtering"),
    end_date: Optional[date] = Query(None, description="End date for filtering"),
    start_time: Optional[time] = Query(None, description="Start time for filtering"),
    end_time: Optional[time] = Query(None, description="End time for filtering"),
    receipt_number: str = Query(None, description="Receipt number for filtering"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    per_page: int = Query(10, ge=1, le=100, description="Number of items per page"),
    sort_by: str = Query("created_on", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc or desc)")
):
    """Export ledgers to Excel or PDF"""
    
    try:
        ledgers = ledger_service.search_ledger_entries(
           db,
            ledger_id=ledger_id,
            amount_from=amount_from,
            amount_to=amount_to,
            driver_id=driver_id,
            driver_name=driver_name,
            transaction_date_from=transaction_date_from,
            transaction_date_to=transaction_date_to,
            transaction_time_from=transaction_time_from,
            transaction_time_to=transaction_time_to,
            vin=vin,
            medallion_number=medallion_number,
            transaction_type=transaction_type,
            source_type=source_type,
            source_id=source_id,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            receipt_number=receipt_number,
            page=1,
            page_size=100000,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        results = [
            {
                "ID": entry["id"],
                "Ledger ID": entry["ledger_id"],
                "Amount": entry["amount"],
                "Description": entry["description"],
                "Transaction Type": entry["source_type"].name if hasattr(entry["source_type"], "name") else entry["source_type"],
                "Source ID": entry["source_id"],
                "Ledger_Date": datetime.fromisoformat(entry["created_on"]).strftime("%Y-%m-%d") if entry["created_on"] else "",
                "Ledger_Time": datetime.fromisoformat(entry["created_on"]).strftime("%H:%M:%S") if entry["created_on"] else "",
                "Receipt Number": entry["receipt_number"],
                "Dr/Cr": entry["transaction_type"],
                "Driver ID": entry["driver_id"],
                "VIN": entry["vin"],
                "Medallion Number": entry["medallion_number"],
                "Transaction Date": entry["transaction_date"],
                "Transaction Time": entry["transaction_time"],
                "Driver Name": entry["driver_name"]
            }
            for entry in ledgers["items"]
        ]
        
        file = None
        media_type = None
        headers = None

        if format == "excel":
            excel_exporter = ExcelExporter(results)
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            headers = {"Content-Disposition": "attachment; filename=ledgers_export.xlsx"}
        elif format == "pdf":
            pdf_exporter = PDFExporter(results)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            headers = {"Content-Disposition": "attachment; filename=ledgers_export.pdf"}
        else:
            raise HTTPException(status_code=400, detail="Invalid format")

        return StreamingResponse(
            file,
            media_type=media_type,
            headers=headers
        )
    
    except Exception as e:
        logger.error("Error exporting ledgers: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.get("/view/{ledger_id}", summary="View a specific ledger entry")
def view_ledger(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View a specific ledger entry"""
    try:
        if not ledger_id:
            raise HTTPException(status_code=400, detail="Ledger ID is required")
        
        ledger = ledger_service.get_ledger_entries(db=db , ledger_id=ledger_id)

        if not ledger:
            raise HTTPException(status_code=404, detail="Ledger not found")
        
        ledger_details = ledger.to_dict()
        documents = upload_service.get_documents(db=db , object_type="ledger" , object_id=ledger.id , multiple=True)
        history = audit_trail_service.get_related_audit_trail(db=db , ledger_id=ledger.id)

        ledger_details["documents"] = documents if documents else []
        ledger_details["history"] = history if history else []

        return ledger_details
    except Exception as e:
        logger.error("Error viewing ledger: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@router.put("/reassign-driver/{ledger_ids}", summary="Reassign driver for a ledger entry")
def reassign_driver(
    ledger_ids: str,
    new_driver_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reassign driver for a specific ledger entry"""
    
    try:
        if not new_driver_id:
            raise HTTPException(status_code=400, detail="New driver ID is required")
        
        driver = driver_service.get_drivers(db=db ,driver_id=new_driver_id)
        if not driver:
            raise HTTPException(status_code=404, detail="Driver not found")
        
        ledgers = [int(lid.strip()) for lid in ledger_ids.split(",") if lid.strip().isdigit()]
        if not ledgers:
            raise HTTPException(status_code=400, detail="Ledger IDs are required")
        
        updated_ledgers = []
        failed_ledgers = []
        for ledger_id in ledgers:
            ledger = ledger_service.get_ledger_entries(db=db , ledger_id=ledger_id)
            if not ledger:
                failed_ledgers.append(ledger_id)
                continue
            ledger = ledger_service.upsert_ledgers(db=db , ledger_data= {"id": ledger.id , "driver_id": driver.id})
            updated_ledgers.append(ledger.id)
        
        return {"message": "Driver reassigned successfully", "updated_ledgers": updated_ledgers, "failed_ledgers": failed_ledgers, "new_driver_id": new_driver_id}
    
    except Exception as e:
        logger.error("Error reassigning driver: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    
@router.post("/dtr/generate", summary="Generate a DTR for a specific driver and period")
def generate_on_demand_dtr(
    driver_id: str = Query(..., description="The internal database ID of the driver."),
    start_date: date = Query(..., description="The start date for the DTR period (YYYY-MM-DD)."),
    end_date: date = Query(..., description="The end date for the DTR period (YYYY-MM-DD)."),
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """
    Manually generates a Driver Transaction Receipt (DTR) for a given driver
    over a specified period. The generated reports (HTML, PDF, Excel) are
    uploaded to S3 and the record is saved to the database.
    """
    try:
        # Combine date with time to create datetime objects
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())

        if start_datetime > end_datetime:
            raise HTTPException(status_code=400, detail="Start date cannot be after end date.")

        logger.info(f"On-demand DTR generation requested for driver ID {driver_id} from {start_date} to {end_date}")

        new_receipt = ledger_service.create_and_generate_dtr_files(db, driver_id, start_datetime, end_datetime)

        return {
            "message": "DTR generated successfully.",
            "receipt_number": new_receipt.receipt_number,
            "driver_id": new_receipt.driver_id,
            "period_start": new_receipt.period_start,
            "period_end": new_receipt.period_end,
            "receipt_urls": {
                "html": new_receipt.receipt_html_url,
                "pdf": new_receipt.receipt_pdf_url,
                "excel": new_receipt.receipt_excel_url,
            }
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve)) from ve
    except Exception as e:
        logger.error(f"Error during on-demand DTR generation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An internal error occurred during DTR generation.") from e