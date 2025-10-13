# app/ezpass/router.py

"""
FastAPI router for EZPass operations with async endpoints.
"""

import math
from datetime import datetime
from typing import Optional
from io import BytesIO

from fastapi import (
    APIRouter, Depends, HTTPException, UploadFile, File, Query,
    status,
)
from fastapi.responses import StreamingResponse

from app.ezpass.services import EZPassService
from app.ezpass.schemas import (
    EZPassTransactionResponse, PaginatedEZPassTransactionResponse,
    EZPassLogResponse, PaginatedEZPassLogResponse,
    EZPassTransactionUpdate, EZPassTransactionFilters, EZPassLogFilters,
    EZPassImportResult, EZPassAssociationResult, EZPassPostingResult,
)
from app.ezpass.exceptions import (
    EZPassBaseException, convert_to_http_exception,
    EZPassFileValidationException, EZPassExportException,
)
from app.ezpass.utils import validate_ezpass_file
from app.users.models import User
from app.users.utils import get_current_user
from app.utils.logger import get_logger
from app.utils.exporter_utils import ExporterFactory

logger = get_logger(__name__)
router = APIRouter(tags=["EZPass"], prefix="/ezpass")


# === Import operations ===

@router.post("/import", response_model=EZPassImportResult, status_code=status.HTTP_201_CREATED)
async def import_ezpass(
    file: UploadFile = File(...),
    ezpass_service: EZPassService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Import EZPass data from an uploaded file.

    The file should be in CSV or Excel format with the required columns.
    """
    logger.info(
        "EZPass import request received",
        filename=file.filename,
        user_id=current_user.id
    )

    try:
        # === Validate and parse file ===
        rows = validate_ezpass_file(file)
        logger.info("File validated successfully", row_count=len(rows))

        # === Process data ===
        result = await ezpass_service.process_ezpass_data(rows)

        logger.info(
            "EZPass import completed",
            log_id=result.log_id,
            success_count=result.success_count,
        )

        return result

    except EZPassFileValidationException as e:
        logger.warning("File validation failed", error=str(e))
        raise convert_to_http_exception(e) from e
    except EZPassBaseException as e:
        logger.error("EZPass import failed", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error during import", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to import EZPass data: {str(e)}"
        ) from e


# ===================== Transaction Operations =====================

@router.get("/transactions", response_model=PaginatedEZPassTransactionResponse)
async def list_transactions(
    transaction_id: Optional[int] = Query(None, description="Transaction ID"),
    transaction_from_date: Optional[datetime] = Query(None, description="Transaction date from"),
    transaction_to_date: Optional[datetime] = Query(None, description="Transaction date to"),
    medallion_no: Optional[str] = Query(None, description="Comma-separated medallion numbers"),
    driver_id: Optional[str] = Query(None, description="Comma-separated driver IDs"),
    plate_no: Optional[str] = Query(None, description="Comma-separated plate numbers"),
    posting_from_date: Optional[datetime] = Query(None, description="Posting date from"),
    posting_to_date: Optional[datetime] = Query(None, description="Posting date to"),
    transaction_status: Optional[str] = Query(None, description="Comma-separated statuses"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("updated_on", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    ezpass_service: EZPassService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    List EZPass transactions with optional filters, sorting, and pagination.
    """
    logger.info("List transactions request received", page=page, per_page=per_page)

    try:
        filters = EZPassTransactionFilters(
            transaction_id=transaction_id,
            transaction_from_date=transaction_from_date,
            transaction_to_date=transaction_to_date,
            medallion_no=medallion_no,
            driver_id=driver_id,
            plate_no=plate_no,
            posting_from_date=posting_from_date,
            posting_to_date=posting_to_date,
            transaction_status=transaction_status,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        transactions, total_count = await ezpass_service.get_transactions(filters)
        
        transactions_data = [
            EZPassTransactionResponse.model_validate(t) for t in transactions
        ]
        
        response = PaginatedEZPassTransactionResponse(
            items=transactions_data,
            total_items=total_count,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total_count / per_page)
        )
        
        logger.info("Transactions listed successfully", count=len(transactions_data))
        return response
        
    except EZPassBaseException as e:
        logger.error("Error listing transactions", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error listing transactions", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list transactions: {str(e)}"
        ) from e
    
@router.get("/transaction/{transaction_id}", response_model=EZPassTransactionResponse)
async def get_transaction(
    transaction_id: int,
    ezpass_service: EZPassService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific EZPass transaction by ID.
    """
    logger.info("Get transaction request", transaction_id=transaction_id)
    
    try:
        transaction = await ezpass_service.get_transaction_by_id(transaction_id)
        logger.info("Transaction retrieved successfully", transaction_id=transaction_id)
        return EZPassTransactionResponse.model_validate(transaction)
        
    except EZPassBaseException as e:
        logger.error("Error getting transaction", error=str(e))
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error getting transaction", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get transaction: {str(e)}"
        ) from e


@router.put("/transaction/{transaction_id}", response_model=EZPassTransactionResponse)
async def update_transaction(
    transaction_id: int,
    update_data: EZPassTransactionUpdate,
    ezpass_service: EZPassService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing EZPass transaction.
    """
    logger.info(
        "Update transaction request",
        transaction_id=transaction_id,
        user_id=current_user.id
    )
    
    try:
        transaction = await ezpass_service.update_transaction(transaction_id, update_data)
        logger.info("Transaction updated successfully", transaction_id=transaction_id)
        return EZPassTransactionResponse.model_validate(transaction)
        
    except EZPassBaseException as e:
        logger.error("Error updating transaction", error=str(e))
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error updating transaction", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update transaction: {str(e)}"
        ) from e


# ===================== Export Operations =====================

@router.get("/export/transactions", summary="Export EZPass transactions")
async def export_transactions(
    format: str = Query("excel", enum=["excel", "pdf", "csv", "json"]),
    transaction_id: Optional[int] = Query(None),
    transaction_from_date: Optional[datetime] = Query(None),
    transaction_to_date: Optional[datetime] = Query(None),
    medallion_no: Optional[str] = Query(None),
    driver_id: Optional[str] = Query(None),
    plate_no: Optional[str] = Query(None),
    posting_from_date: Optional[datetime] = Query(None),
    posting_to_date: Optional[datetime] = Query(None),
    transaction_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(1000, ge=1, le=10000),
    sort_by: str = Query("updated_on"),
    sort_order: str = Query("desc"),
    ezpass_service: EZPassService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Export EZPass transactions to Excel or PDF format.
    """
    logger.info("Export transactions request", format=format, user_id=current_user.id)
    
    try:
        filters = EZPassTransactionFilters(
            transaction_id=transaction_id,
            transaction_from_date=transaction_from_date,
            transaction_to_date=transaction_to_date,
            medallion_no=medallion_no,
            driver_id=driver_id,
            plate_no=plate_no,
            posting_from_date=posting_from_date,
            posting_to_date=posting_to_date,
            transaction_status=transaction_status,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        transactions, _ = await ezpass_service.get_transactions(filters)
        
        if not transactions:
            logger.warning("No transactions available for export")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No transactions available to export"
            )
        
        # Prepare data for export
        transactions_data = [{
            "ID": t.id,
            "Transaction ID": t.transaction_id,
            "Transaction Date": t.transaction_date,
            "Transaction Time": t.transaction_time,
            "Posting Date": t.posting_date,
            "Plate No": t.plate_no,
            "Medallion No": t.medallion_no,
            "Driver ID": t.driver_id,
            "Vehicle ID": t.vehicle_id,
            "Tag or Plate": t.tag_or_plate,
            "Agency": t.agency,
            "Entry Plaza": t.entry_plaza,
            "Exit Plaza": t.exit_plaza,
            "Amount": t.amount,
            "Status": t.status,
            "Created On": t.created_on
        } for t in transactions]
        
        # Generate file based on format
        if format == "excel":
            excel_exporter = ExporterFactory.get_exporter("excel", transactions_data)
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = "ezpass_transactions_export.xlsx"
        elif format == "pdf":  # pdf
            pdf_exporter = ExporterFactory.get_exporter("pdf", transactions_data)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            filename = "ezpass_transactions_export.pdf"
        elif format == "csv":  # csv
            csv_exporter = ExporterFactory.get_exporter("csv", transactions_data)
            file: BytesIO = csv_exporter.export()
            media_type = "text/csv"
            filename = "ezpass_transactions_export.csv"
        elif format == "json":  # json
            json_exporter = ExporterFactory.get_exporter("json", transactions_data)
            file: BytesIO = json_exporter.export()
            media_type = "application/json"
            filename = "ezpass_transactions_export.json"
        else:
            logger.error("Unsupported export format requested", format=format)
            raise EZPassExportException(f"Unsupported export format: {format}")
        
        logger.info("Transactions exported successfully", format=format, count=len(transactions_data))
        
        return StreamingResponse(
            file,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error exporting transactions", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting transactions"
        ) from e


# ===================== Log Operations =====================

@router.get("/logs", response_model=PaginatedEZPassLogResponse)
async def list_logs(
    log_id: Optional[int] = Query(None, description="Log ID"),
    log_from_date: Optional[datetime] = Query(None, description="Log date from"),
    log_to_date: Optional[datetime] = Query(None, description="Log date to"),
    log_status: Optional[str] = Query(None, description="Comma-separated statuses"),
    log_type: Optional[str] = Query(None, description="Comma-separated types"),
    records_impacted: Optional[int] = Query(None, description="Records impacted"),
    success_count: Optional[int] = Query(None, description="Success count"),
    unidentified_count: Optional[int] = Query(None, description="Unidentified count"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(10, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("log_date", description="Sort by field"),
    sort_order: str = Query("desc", description="Sort order (asc/desc)"),
    ezpass_service: EZPassService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    List EZPass logs with optional filters, sorting, and pagination.
    """
    logger.info("List logs request received", page=page, per_page=per_page)
    
    try:
        filters = EZPassLogFilters(
            log_id=log_id,
            log_from_date=log_from_date,
            log_to_date=log_to_date,
            log_status=log_status,
            log_type=log_type,
            records_impacted=records_impacted,
            success_count=success_count,
            unidentified_count=unidentified_count,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        logs, total_count = await ezpass_service.get_logs(filters)
        
        logs_data = [EZPassLogResponse.model_validate(log) for log in logs]
        
        response = PaginatedEZPassLogResponse(
            items=logs_data,
            total_items=total_count,
            page=page,
            per_page=per_page,
            total_pages=math.ceil(total_count / per_page)
        )
        
        logger.info("Logs listed successfully", count=len(logs_data))
        return response
        
    except EZPassBaseException as e:
        logger.error("Error listing logs", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error listing logs", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list logs: {str(e)}"
        ) from e


@router.get("/log/{log_id}", response_model=EZPassLogResponse)
async def get_log(
    log_id: int,
    ezpass_service: EZPassService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific EZPass log by ID.
    """
    logger.info("Get log request", log_id=log_id)
    
    try:
        log = await ezpass_service.get_log_by_id(log_id)
        logger.info("Log retrieved successfully", log_id=log_id)
        return EZPassLogResponse.model_validate(log)
        
    except EZPassBaseException as e:
        logger.error("Error getting log", error=str(e))
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error getting log", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get log: {str(e)}"
        ) from e


@router.get("/export/logs", summary="Export EZPass logs")
async def export_logs(
    format: str = Query("excel", enum=["excel", "pdf", "csv", "json"]),
    log_id: Optional[int] = Query(None),
    log_from_date: Optional[datetime] = Query(None),
    log_to_date: Optional[datetime] = Query(None),
    log_status: Optional[str] = Query(None),
    log_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(1000, ge=1, le=10000),
    sort_by: str = Query("log_date"),
    sort_order: str = Query("desc"),
    ezpass_service: EZPassService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Export EZPass logs to Excel or PDF format.
    """
    logger.info("Export logs request", format=format, user_id=current_user.id)
    
    try:
        filters = EZPassLogFilters(
            log_id=log_id,
            log_from_date=log_from_date,
            log_to_date=log_to_date,
            log_status=log_status,
            log_type=log_type,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        logs, _ = await ezpass_service.get_logs(filters)
        
        if not logs:
            logger.warning("No logs available for export")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No logs available to export"
            )
        
        # Prepare data for export
        logs_data = [{
            "ID": log.id,
            "Log Date": log.log_date,
            "Log Type": log.log_type,
            "Records Impacted": log.records_impacted,
            "Success Count": log.success_count,
            "Unidentified Count": log.unidentified_count,
            "Status": log.status,
            "Created On": log.created_on
        } for log in logs]
        
        # Generate file based on format
        if format == "excel":
            excel_exporter = ExporterFactory.get_exporter("excel", logs_data)
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = "ezpass_logs_export.xlsx"
        elif format == "pdf":
            pdf_exporter = ExporterFactory.get_exporter("pdf", logs_data)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            filename = "ezpass_logs_export.pdf"
        elif format == "csv":
            csv_exporter = ExporterFactory.get_exporter("csv", logs_data)
            file: BytesIO = csv_exporter.export()
            media_type = "text/csv"
            filename = "ezpass_logs_export.csv"
        elif format == "json":
            json_exporter = ExporterFactory.get_exporter("json", logs_data)
            file: BytesIO = json_exporter.export()
            media_type = "application/json"
            filename = "ezpass_logs_export.json"
        else:
            logger.error("Unsupported export format requested", format=format)
            raise EZPassExportException(f"Unsupported export format: {format}")
        
        logger.info("Logs exported successfully", format=format, count=len(logs_data))
        
        return StreamingResponse(
            file,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error exporting logs", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error exporting logs"
        ) from e


# ===================== Processing Operations =====================

@router.post("/associate", response_model=EZPassAssociationResult)
async def associate_transactions(
    ezpass_service: EZPassService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Associate imported EZPass transactions with vehicles, drivers, and medallions.
    
    This process matches transactions to existing records in the system.
    """
    logger.info("Associate transactions request received", user_id=current_user.id)
    
    try:
        result = await ezpass_service.associate_transactions()
        logger.info(
            "Transactions association completed",
            associated_count=result.associated_count,
            failed_count=result.failed_count
        )
        return result
        
    except EZPassBaseException as e:
        logger.error("Error associating transactions", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error associating transactions", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to associate transactions: {str(e)}"
        ) from e


@router.post("/post", response_model=EZPassPostingResult)
async def post_transactions(
    ezpass_service: EZPassService = Depends(),
    current_user: User = Depends(get_current_user)
):
    """
    Post associated EZPass transactions to the central ledger.
    
    This creates ledger entries for all associated transactions.
    """
    logger.info("Post transactions request received", user_id=current_user.id)
    
    try:
        result = await ezpass_service.post_transactions_to_ledger()
        logger.info(
            "Transactions posting completed",
            posted_count=result.posted_count,
            failed_count=result.failed_count
        )
        return result
        
    except EZPassBaseException as e:
        logger.error("Error posting transactions", error=str(e), exc_info=True)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error("Unexpected error posting transactions", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to post transactions: {str(e)}"
        ) from e
    
