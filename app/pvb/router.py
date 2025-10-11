### app/pvb/router.py

from typing import Optional
from datetime import datetime , time
import math
from io import BytesIO


# Third party imports
from fastapi import (
    APIRouter, UploadFile, File, Depends, HTTPException , Query
)
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# Local imports
from app.utils.logger import get_logger
from app.core.db import get_db
from app.pvb.services import pvb_service
from app.pvb.utils import valid_pvb_csv
from app.users.models import User
from app.users.utils import get_current_user
from app.utils.exporter.excel_exporter import ExcelExporter
from app.utils.exporter.pdf_exporter import PDFExporter

logger = get_logger(__name__)
router = APIRouter(prefix="/pvb", tags=["PVB"])

@router.post("/import", summary="Import PVB CSV")
def import_pvb_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Import PVB CSV"""
    try:
        rows = valid_pvb_csv(file)
        result = pvb_service.import_pvb(db, rows)
        return result
    except Exception as e:
        logger.error("Error importing PVB CSV: %s", str(e))
        raise HTTPException(status_code=500, detail="Error importing PVB CSV") from e
    
@router.get("/logs" , summary="Get PVB Logs")
def get_pvb_logs(
    db: Session = Depends(get_db),
    page: Optional[int] = Query(1, ge=1), 
    per_page: Optional[int] = Query(10, ge=1),
    log_id: int = Query(None, description="Log ID"),
    log_from_date: datetime = Query(None, description="Log from date"),
    log_to_date: datetime = Query(None, description="Log to date"),
    records_impacted: int = Query(None, description="No of records impacted"),
    success_count: int = Query(None, description="No of sucess records"),
    unidentified_count : int = Query(None, description="No of unidentified records"),
    log_status: str = Query(None, description="Comma separated statuses"),
    log_type: str = Query(None, description="Comma separated types"),
    sort_by: str = Query("log_date", description="Sort by"),
    sort_order: str = Query("desc", description="Sort order"),
    logged_in_user: User = Depends(get_current_user)
):
    """Get PVB Logs"""
    try:
        logs,total_items = pvb_service.get_pvb_log(db=db,page=page,per_page=per_page,multiple=True,
                                             log_id=log_id,
                                             log_from_date=log_from_date,
                                             log_to_date=log_to_date,
                                             records_impacted=records_impacted,
                                             success_count=success_count,
                                             unidentified_count=unidentified_count,
                                             log_status=log_status,
                                             log_type=log_type,
                                             sort_by=sort_by,
                                             sort_order=sort_order)
        
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
        logger.error("Error listing PVB logs: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list PVB logs: {str(e)}"
        ) from e
    

@router.get("/export/logs", summary = "Export PVB Logs")
def export_pvb_logs(
    db: Session = Depends(get_db),
    format : Optional[str] = Query("excel", enum=["excel", "pdf"]),
    page: Optional[int] = Query(1, ge=1), 
    per_page: Optional[int] = Query(10, ge=1),
    log_id: int = Query(None, description="Log ID"),
    log_from_date: datetime = Query(None, description="Log from date"),
    log_to_date: datetime = Query(None, description="Log to date"),
    records_impacted: int = Query(None, description="No of records impacted"),
    success_count: int = Query(None, description="No of sucess records"),
    unidentified_count : int = Query(None, description="No of unidentified records"),
    log_status: str = Query(None, description="Comma separated statuses"),
    log_type: str = Query(None, description="Comma separated types"),
    sort_by: str = Query("log_date", description="Sort by"),
    sort_order: str = Query("desc", description="Sort order"),
    logged_in_user: User = Depends(get_current_user)
):
    """Export PVB Logs"""
    try:
        logs,total_items = pvb_service.get_pvb_log(db=db,page=1,per_page=1000,multiple=True,
                                             log_id=log_id,
                                             log_from_date=log_from_date,
                                             log_to_date=log_to_date,
                                             records_impacted=records_impacted,
                                             success_count=success_count,
                                             unidentified_count=unidentified_count,
                                             log_status=log_status,
                                             log_type=log_type,
                                             sort_by=sort_by,
                                             sort_order=sort_order)
        
        log_data = [{
            "ID": log.id,
            "LOG_Date": log.log_date,
            "LOG_Type": log.log_type,
            "Records_Impacted": log.records_impacted,
            "Success": log.success_count,
            "Unidentified": log.unidentified_count,
            "Status": log.status
        } for log in logs]

        file = None
        media_type = None
        headers = None

        if format == "excel":
            excel_exporter = ExcelExporter(log_data)
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            headers = {"Content-Disposition": "attachment; filename=pvb_logs_export.xlsx"}
        elif format == "pdf":
            pdf_exporter = PDFExporter(log_data)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            headers = {"Content-Disposition": "attachment; filename=pvb_logs_export.pdf"}
        else:
            raise HTTPException(status_code=400, detail="Invalid format")
        
        return StreamingResponse(
            file,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        logger.error("Error exporting PVB logs: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error exporting PVB logs") from e
    
@router.get("/transactions" , summary="Get PVB Transactions")
def get_pvb_transactions(
    db: Session = Depends(get_db),
    transaction_id: int = Query(None, description="Transaction ID"),
    transaction_from_date: datetime = Query(None, description="Transaction from date"),
    transaction_to_date: datetime = Query(None, description="Transaction to date"),
    issue_time_from: time = Query(None, description="Issue time from"),
    issue_time_to: time = Query(None, description="Issue time to"),
    medallion_id: str = Query(None, description="Comma separated medallion IDs"),
    driver_id : str = Query(None, description="Comma separated driver IDs"),
    vehicle_id : str = Query(None, description="Comma separated vehicle IDs"),
    plate_number: str = Query(None, description="Plate Number"),
    state : str = Query(None, description="State"),
    type: str = Query(None, description="Vehicle Type"),
    summons_number : str = Query(None, description="Summons Number"),
    status : str = Query(None, description="Status"),
    page: Optional[int] = Query(1, ge=1), 
    per_page: Optional[int] = Query(10, ge=1),
    sort_by: str = Query("updated_on", description="Sort by"),
    sort_order: str = Query("desc", description="Sort order"),
    logged_in_user: User = Depends(get_current_user)
    ):
    """Get PVB Transactions"""

    try:
        transactions,total_items = pvb_service.get_pvb(db=db,page=page,per_page=per_page,multiple=True,
            violation_id = transaction_id,
            issue_from_date=transaction_from_date,
            issue_to_date=transaction_to_date,
            issue_time_from=issue_time_from,
            issue_time_to=issue_time_to,
            medallion_id=medallion_id,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            type=type,
            plate_number=plate_number,
            state=state,
            summons_number=summons_number,
            record_status=status,
            sort_by=sort_by,
            sort_order=sort_order
        )

        transaction_data = [{
            "id": transaction.id,
            "plate_number": transaction.plate_number,
            "state": transaction.state,
            "vehicle_type": transaction.vehicle_type,
            "summons_number": transaction.summons_number,
            "issue_date": transaction.issue_date,
            "issue_time": transaction.issue_time,
            "amount_due": transaction.amount_due,
            "amount_paid": transaction.amount_paid,
            "type": transaction.vehicle_type,
            "driver_id": transaction.driver_id,
            "medallion_id": transaction.medallion_id,
            "vehicle_id": transaction.vehicle_id,
            "status": transaction.status,
            "associated_failed_reason": transaction.associated_failed_reason,
            "post_failed_reason": transaction.post_failed_reason
        } for transaction in transactions]

        pvb_state , _ = pvb_service.get_pvb(db=db , multiple=True)
        state_seen = set()
        type_seen = set()

        unique_states = []
        unique_types = []

        for item in pvb_state:
            if item.state not in state_seen:
                state_seen.add(item.state)
                unique_states.append(item.state)

            if item.vehicle_type not in type_seen:
                type_seen.add(item.vehicle_type)
                unique_types.append(item.vehicle_type)

        return {
            "items": transaction_data,
            "total_items": total_items,
            "statuses": ["Imported", "Associated", "Posted", "Failed"],
            "types": unique_types,
            "states": unique_states,
            "page": page,
            "per_page": per_page,
            "total_pages": math.ceil(total_items / per_page)
        }
    except Exception as e:
        logger.error("Error listing PVB transactions: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list PVB transactions: {str(e)}"
        ) from e
    
@router.get("/export", summary = "Export PVB Data")
def export_pvb(
    db: Session = Depends(get_db),
    format : Optional[str] = Query("excel", enum=["excel", "pdf"]),
    transaction_id: int = Query(None, description="Transaction ID"),
    transaction_from_date: datetime = Query(None, description="Transaction from date"),
    transaction_to_date: datetime = Query(None, description="Transaction to date"),
    medallion_id: str = Query(None, description="Comma separated medallion IDs"),
    driver_id : str = Query(None, description="Comma separated driver IDs"),
    vehicle_id : str = Query(None, description="Comma separated vehicle IDs"),
    plate_number: str = Query(None, description="Plate Number"),
    state : str = Query(None, description="State"),
    summons_number : str = Query(None, description="Summons Number"),
    status : str = Query(None, description="Status"),
    page: Optional[int] = Query(1, ge=1), 
    per_page: Optional[int] = Query(10, ge=1),
    sort_by: str = Query("updated_on", description="Sort by"),
    sort_order: str = Query("desc", description="Sort order"),
    logged_in_user: User = Depends(get_current_user)
):
    """Export PVB Data"""

    try:
        transactions,total_items = pvb_service.get_pvb(db=db,page=1,per_page=1000,multiple=True,
            violation_id = transaction_id,
            issue_from_date=transaction_from_date,
            issue_to_date=transaction_to_date,
            medallion_id=medallion_id,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            plate_number = plate_number,
            state=state,
            summons_number=summons_number,
            record_status=status,
            sort_by=sort_by,
            sort_order=sort_order
        )

        transaction_data = [{
            "id": transaction.id,
            "plate_number": transaction.plate_number,
            "state": transaction.state,
            "vehicle_type": transaction.vehicle_type,
            "summons_number": transaction.summons_number,
            "issue_date": transaction.issue_date,
            "issue_time": transaction.issue_time,
            "amount_due": transaction.amount_due,
            "amount_paid": transaction.amount_paid,
            "driver_id": transaction.driver_id,
            "medallion_id": transaction.medallion_id,
            "vehicle_id": transaction.vehicle_id,
            "status": transaction.status,
            "associated_failed_reason": transaction.associated_failed_reason,
            "post_failed_reason": transaction.post_failed_reason
        } for transaction in transactions]

        file = None
        media_type = None
        headers = None

        if format == "excel":
            excel_exporter = ExcelExporter(transaction_data)
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            headers = {"Content-Disposition": "attachment; filename=pvb_export.xlsx"}
        elif format == "pdf":
            pdf_exporter = PDFExporter(transaction_data)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            headers = {"Content-Disposition": "attachment; filename=pvb_export.pdf"}
        else:
            raise HTTPException(status_code=400, detail="Invalid format")
        
        return StreamingResponse(
            file,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        logger.error("Error exporting pvb list: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error exporting PVB list") from e


    
@router.get("/transactions/{id}", summary="Get PVB Transaction by ID")
def get_pvb_transaction_by_id(
    id: int,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Get PVB Transaction by ID"""
    try:
        transaction = pvb_service.get_pvb(db, violation_id=id)
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        return {
            "id": transaction.id,
            "plate_number": transaction.plate_number,
            "state": transaction.state,
            "vehicle_type": transaction.vehicle_type,
            "summons_number": transaction.summons_number,
            "issue_date": transaction.issue_date,
            "issue_time": transaction.issue_time,
            "amount_due": transaction.amount_due,
            "amount_paid": transaction.amount_paid,
            "driver_id": transaction.driver_id,
            "medallion_id": transaction.medallion_id,
            "vehicle_id": transaction.vehicle_id,
            "status": transaction.status,
            "associated_failed_reason": transaction.associated_failed_reason,
            "post_failed_reason": transaction.post_failed_reason
        }
    except Exception as e:
        logger.error("Error fetching PVB transaction by ID: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching PVB transaction") from e
    
@router.put("/transactions/{id}", summary="Update PVB Transaction by ID")
def update_pvb_transaction_by_id(
    id: int,
    data: dict,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Update PVB Transaction by ID"""
    try:

        transaction = pvb_service.upsert_pvb_violation(db=db,violation_data={"id": id, **data})
        if not transaction:
            raise HTTPException(status_code=404, detail="Transaction not found")
        
        return {
            "id": transaction.id,
            "plate_number": transaction.plate_number,
            "state": transaction.state,
            "vehicle_type": transaction.vehicle_type,
            "summons_number": transaction.summons_number,
            "issue_date": transaction.issue_date,
            "issue_time": transaction.issue_time,
            "amount_due": transaction.amount_due,
            "amount_paid": transaction.amount_paid,
            "driver_id": transaction.driver_id,
            "medallion_id": transaction.medallion_id,
            "vehicle_id": transaction.vehicle_id,
            "status": transaction.status,
            "associated_failed_reason": transaction.associated_failed_reason,
            "post_failed_reason": transaction.post_failed_reason
        }
    except Exception as e:
        logger.error("Error updating PVB transaction by ID: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error updating PVB transaction") from e
    
@router.get("/logs/{id}", summary="Get PVB Log by ID")
def get_pvb_log_by_id(
    id: int,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Get PVB Log by ID"""
    try:
        log = pvb_service.get_pvb_log(db, log_id=id)
        if not log:
            raise HTTPException(status_code=404, detail="Log not found")
        
        return {
            "id": log.id,
            "log_date": log.log_date,
            "log_type": log.log_type,
            "records_impacted": log.records_impacted,
            "success_count": log.success_count,
            "unidentified_count": log.unidentified_count,
            "status": log.status
        }
    except Exception as e:
        logger.error("Error fetching PVB log by ID: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching PVB log") from e

    
@router.post("/associate", summary="Associate PVB")
def associate_pvb(
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Associate PVB"""
    try:
        result = pvb_service.associate_pvb(db)
        return result
    except Exception as e:
        logger.error("Error associating PVB: %s", str(e))
        raise HTTPException(status_code=500, detail="Error associating PVB") from e
    
@router.post("/post", summary="Post PVB to central ledger")
def post_pvb(
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Post PVB to central ledger"""
    try:
        result = pvb_service.post_pvb(db)
        return result
    except Exception as e:
        logger.error("Error posting PVB: %s", str(e))
        raise HTTPException(status_code=500, detail="Error posting PVB") from e
    
    
