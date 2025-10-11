# app/ezpass/router.py

import uuid
import math
from datetime import datetime
from typing import Optional
from io import BytesIO
from pathlib import Path

from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Query
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.utils.logger import get_logger
from app.ezpass.services import ezpass_service
from app.ezpass.utils import validate_ezpass_file
from app.users.models import User
from app.users.utils import get_current_user
from app.utils.exporter.excel_exporter import ExcelExporter
from app.utils.exporter.pdf_exporter import PDFExporter
from app.ezpass.tasks import process_report_from_s3

logger = get_logger(__name__)
router = APIRouter(tags=["EZPass"], prefix="/ezpass")

@router.post("/import")
def import_ezpass(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Import EZPass data from a file"""
    try:
        rows = validate_ezpass_file(file)
        result = ezpass_service.process_ezpass_data(db, rows)
        return result
    except Exception as e:
        logger.error("Error importing EZPass data: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to import EZPass data: {str(e)}"
        ) from e
    
@router.get("/logs", summary="View EZPass logs")
def list_ezpass_logs(
    db: Session = Depends(get_db), 
    page: Optional[int] = Query(1, ge=1), 
    per_page: Optional[int] = Query(10, ge=1),
    log_id: int = Query(None, description="Log ID"),
    log_from_date: datetime = Query(None, description="Log from date"),
    log_to_date: datetime = Query(None, description="Log to date"),
    records_impacted: int = Query(None, description="No of records impacted"),
    success_count: int = Query(None, description="No of unidentified records"),
    unidentified_count: int = Query(None, description="No of unidentified records"),
    log_status: str = Query(None, description="Comma separated statuses"),
    log_type: str = Query(None, description="Comma separated types"),
    sort_by: str = Query("log_date", description="Sort by"),
    sort_order: str = Query("desc", description="Sort order"),
    logged_in_user: User = Depends(get_current_user)
):
    """List EZPass logs"""
    try:
        logs, total_items = ezpass_service.get_ezpass_log(
            db, multiple=True, page=page, per_page=per_page,
            log_id=log_id,
            log_from_date=log_from_date,
            log_to_date=log_to_date,
            records_impacted=records_impacted,
            success_count=success_count,
            unidentified_count=unidentified_count,
            log_status=log_status,
            log_type=log_type,
            sort_by=sort_by,
            sort_order=sort_order
        )
        log_data = [{
            "id": log.id,
            "log_date": log.log_date,
            "log_type": log.log_type,
            "records_impacted": log.records_impacted,
            "success": log.success_count,
            "unidentified": log.unidentified_count,
            "status": log.status
        } for log in logs]
        return {
            "items": log_data,
            "total_items": total_items,
            "page": page,
            "per_page": per_page,
            "statuses": ["Success", "Failure", "Partial"],
            "types": ["Import", "Associate", "Post"],
            "total_pages": math.ceil(total_items / per_page)
        }
    except Exception as e:
        logger.error("Error listing EZPass logs: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list EZPass logs: {str(e)}"
        ) from e
    
@router.get("/export/logs", summary="Export EZPass logs")
def export_ezpass_logs(
    db: Session = Depends(get_db),
    format: Optional[str] = Query("excel", enum=["excel", "pdf"]),
    log_id: int = Query(None, description="Log ID"),
    log_from_date: datetime = Query(None, description="Log from date"),
    log_to_date: datetime = Query(None, description="Log to date"),
    records_impacted: int = Query(None, description="No of records impacted"),
    success_count: int = Query(None, description="No of unidentified records"),
    unidentified_count: int = Query(None, description="No of unidentified records"),
    log_status: str = Query(None, description="Comma separated statuses"),
    log_type: str = Query(None, description="Comma separated types"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(1000, ge=1, description="Items per page"),
    sort_by: str = Query("log_date", description="Sort by"),
    sort_order: str = Query("desc", description="Sort order"),
    logged_in_user: User = Depends(get_current_user)
):
    """Export EZPass logs"""
    try:
        logs, total_items = ezpass_service.get_ezpass_log(
            db, multiple=True, page=page, per_page=per_page,
            log_id=log_id,
            log_from_date=log_from_date,
            log_to_date=log_to_date,
            records_impacted=records_impacted,
            success_count=success_count,
            unidentified_count=unidentified_count,
            log_status=log_status,
            log_type=log_type,
            sort_by=sort_by,
            sort_order=sort_order
        )
        log_data = [{
            "ID": log.id,
            "Log Date": log.log_date,
            "Log Type": log.log_type,
            "Records Impacted": log.records_impacted,
            "Success": log.success_count,
            "Unidentified": log.unidentified_count,
            "Status": log.status
        } for log in logs]

        if not log_data:
            logger.info("No EZPass logs found for export")
            raise HTTPException(status_code=404, detail="No EZPass logs found for export")

        file = None
        media_type = None
        headers = None

        if format == "excel":
            excel_exporter = ExcelExporter(log_data)
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            headers = {"Content-Disposition": "attachment; filename=ezpass_log_export.xlsx"}
        elif format == "pdf":
            pdf_exporter = PDFExporter(log_data)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            headers = {"Content-Disposition": "attachment; filename=ezpass_log_export.pdf"}
        else:
            raise HTTPException(status_code=400, detail="Invalid format")

        return StreamingResponse(
            file,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        logger.error(f"Error exporting EZPass logs: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/transactions", summary="List EZPass transactions")
def list_transactions(
    db: Session = Depends(get_db),
    transaction_id: int = Query(None, description="Transaction ID"),
    transaction_from_date: datetime = Query(None, description="Transaction date from"),
    transaction_to_date: datetime = Query(None, description="Transaction date to"),
    medallion_no: str = Query(None, description="Comma separated list of medallion numbers"),
    driver_id: str = Query(None, description="Comma separated list of driver IDs"),
    plate_no: str = Query(None, description="Comma separated list of plate numbers"),
    posting_from_date: datetime = Query(None, description="Posting date from"),
    posting_to_date: datetime = Query(None, description="Posting date to"),
    transaction_status: str = Query(None, description="Comma separated statuses"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, description="Items per page"),
    sort_by: str = Query("updated_on", description="Sort by"),
    sort_order: str = Query("desc", description="Sort order"),
    logged_in_user: User = Depends(get_current_user)
):
    """List EZPass transactions"""
    try:
        transactions, total_items = ezpass_service.get_ezpass_transaction(
            db, multiple=True, page=page, per_page=per_page,
            transaction_id=transaction_id,
            transaction_from_date=transaction_from_date,
            transaction_to_date=transaction_to_date,
            medallion_no=medallion_no,
            driver_id=driver_id,
            plate_no=plate_no,
            posting_from_date=posting_from_date,
            posting_to_date=posting_to_date,
            transaction_status=transaction_status,
            sort_by=sort_by,
            sort_order=sort_order
        )
        transactions_data = [{
            "id": transaction.id,
            "log_id": transaction.log_id,
            "plate_no": transaction.plate_no,
            "medallion_no": transaction.medallion_no,
            "driver_id": transaction.driver_id,
            "vehicle_id": transaction.vehicle_id,
            "amount": transaction.amount,
            "agency": transaction.agency,
            "entry_plaza": transaction.entry_plaza,
            "posting_date": transaction.posting_date,
            "transaction_date": transaction.transaction_date,
            "transaction_time": transaction.transaction_time,
            "status": transaction.status,
            "created_on": transaction.created_on
        } for transaction in transactions]
        return {
            "items": transactions_data,
            "total_items": total_items,
            "page": page,
            "per_page": per_page,
            "statuses": ["Imported", "Associated", "Posted", "Failed"],
            "total_pages": math.ceil(total_items / per_page)
        }
    except Exception as e:
        logger.error("Error listing EZPass transactions: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list EZPass transactions: {str(e)}"
        ) from e
    
@router.get("/export", summary="Export EZPass data")
def export_ezpass(
    db: Session = Depends(get_db),
    format: Optional[str] = Query("excel", enum=["excel", "pdf"]),
    transaction_id: int = Query(None, description="Transaction ID"),
    transaction_from_date: datetime = Query(None, description="Transaction date from"),
    transaction_to_date: datetime = Query(None, description="Transaction date to"),
    medallion_no: str = Query(None, description="Comma separated list of medallion numbers"),
    driver_id: str = Query(None, description="Comma separated list of driver IDs"),
    plate_no: str = Query(None, description="Comma separated list of plate numbers"),
    posting_from_date: datetime = Query(None, description="Posting date from"),
    posting_to_date: datetime = Query(None, description="Posting date to"),
    transaction_status: str = Query(None, description="Comma separated statuses"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, description="Items per page"),
    sort_by: str = Query("updated_on", description="Sort by"),
    sort_order: str = Query("desc", description="Sort order"),
    logged_in_user: User = Depends(get_current_user)
):
    """Export EZPass data"""
    try:

        transactions, total_items = ezpass_service.get_ezpass_transaction(
                db, multiple=True, page=1, per_page=1000,
                transaction_id=transaction_id,
                transaction_from_date=transaction_from_date,
                transaction_to_date=transaction_to_date,
                medallion_no=medallion_no,
                driver_id=driver_id,
                plate_no=plate_no,
                posting_from_date=posting_from_date,
                posting_to_date=posting_to_date,
                transaction_status=transaction_status,
                sort_by=sort_by,
                sort_order=sort_order
            )
        
        transactions_data = [{
            "id": transaction.id,
            "transaction_date": transaction.transaction_date,
            "log_id": transaction.log_id,
            "plate_no": transaction.plate_no,
            "medallion_no": transaction.medallion_no,
            "driver_id": transaction.driver_id,
            "vehicle_id": transaction.vehicle_id,
            "vehicle_type_code": transaction.vehicle_type_code,
            "prepaid": transaction.prepaid,
            "amount": transaction.amount,
            "agency": transaction.agency,
            "activity": transaction.activity,
            "entry_time": transaction.entry_time,
            "exit_time": transaction.exit_time,
            "entry_plaza": transaction.entry_plaza,
            "posting_date": transaction.posting_date,
            "status": transaction.status,
            "created_on": transaction.created_on
        } for transaction in transactions]
        
        if not transactions_data:
            logger.warning("No transactions available to export.")
            raise HTTPException(status_code=400, detail="No transactions available to export.")

        file = None
        media_type = None
        headers = None

        if format == "excel":
            excel_exporter = ExcelExporter(transactions_data)
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            headers = {"Content-Disposition": "attachment; filename=ezpass_export.xlsx"}
        elif format == "pdf":
            pdf_exporter = PDFExporter(transactions_data)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            headers = {"Content-Disposition": "attachment; filename=ezpass_export.pdf"}
        else:
            raise HTTPException(status_code=400, detail="Invalid format")
        
        return StreamingResponse(
            file,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        logger.error("Error exporting ezpass list: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error exporting Ezpass list") from e


    
@router.put("/transaction/{id}", summary="Edit EZPass Transaction")
def update_transaction(
    transaction_id: int, data: dict, db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Update EZPass transaction"""
    try:
        transaction = ezpass_service.get_ezpass_transaction(db, transaction_id=transaction_id)
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        transaction_data = {
            "id": transaction_id,
            **data
        }
        transaction = ezpass_service.upsert_ezpass_transaction(db, transaction_data)
        return transaction
    except Exception as e:
        logger.error("Error updating EZPass transaction: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update EZPass transaction: {str(e)}"
        ) from e
    
@router.get("/transaction", summary="View EZPass Transaction")
def view_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """View EZPass transaction"""
    try:
        transaction = ezpass_service.get_ezpass_transaction(db, transaction_id=transaction_id)
        return transaction
    except Exception as e:
        logger.error("Error viewing EZPass transaction: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to view EZPass transaction: {str(e)}"
        ) from e
    
@router.get("/log/{id}", summary="View EZPass Log")
def view_log(
    log_id: int,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """View EZPass log"""
    try:
        log = ezpass_service.get_ezpass_log(db, log_id=log_id)
        return log
    except Exception as e:
        logger.error("Error viewing EZPass log: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to view EZPass log: {str(e)}"
        ) from e
    
@router.post("/associate", summary="Associate EZPass with BATM")
def associate_ezpass_transactions(
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Associate EZPass with BATM"""
    try:
        result = ezpass_service.associate_records(db)
        return result
    except Exception as e:
        logger.error("Error associating EZPass with BATM: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to associate EZPass with BATM: {str(e)}"
        ) from e
    
@router.post("/post", summary="Post EZPass to central ledger")
def post_ezpass_transactions(
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Post EZPass to central ledger"""
    try:
        result = ezpass_service.post_ezpass(db)
        return result
    except Exception as e:
        logger.error("Error posting EZPass to central ledger: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to post EZPass to central ledger: {str(e)}"
        ) from e