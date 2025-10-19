# app/repairs/router.py

"""
FastAPI router for Vehicle Repairs operations with async endpoints.
"""

import math
from datetime import date
from typing import Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, status
)

from app.repairs.services import RepairService
from app.repairs.schemas import (
    RepairInvoiceCreate, RepairInvoiceUpdate, RepairInvoiceResponse,
    PaginatedRepairInvoiceResponse, RepairInstallmentResponse,
    PaginatedRepairInstallmentResponse, RepairInvoiceFilters,
    RepairInstallmentFilters, RepairImportResult, RepairPostingResult,
    InvoiceStatus, InstallmentStatus, WorkshopType
)
from app.repairs.exceptions import RepairBaseException, convert_to_http_exception
from app.users.models import User
from app.users.utils import get_current_user
from app.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["Repairs"], prefix="/repairs")


# ===================== Invoice Operations =====================

@router.post("/invoices", response_model=RepairImportResult, status_code=status.HTTP_201_CREATED)
async def create_repair_invoice(
    invoice_data: RepairInvoiceCreate,
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new repair invoice with auto-generated payment schedule.
    
    The system will:
    1. Validate the invoice data
    2. Generate a unique repair ID
    3. Calculate weekly installments based on the payment matrix
    4. Create the complete payment schedule
    5. Save invoice in DRAFT status
    """
    try:
        logger.info(
            "Creating repair invoice",
            user_id=current_user.id,
            invoice_number=invoice_data.invoice_number
        )
        
        invoice = await repair_service.create_repair_invoice(
            invoice_data=invoice_data,
            user_id=current_user.id
        )
        
        return RepairImportResult(
            success=True,
            invoice_id=invoice.id,
            repair_id=invoice.repair_id,
            installments_created=len(invoice.installments),
            total_amount=invoice.repair_amount,
            weekly_installment=invoice.weekly_installment,
            message=f"Repair invoice created successfully with {len(invoice.installments)} installments"
        )
        
    except RepairBaseException as e:
        logger.error(f"Failed to create repair invoice: {e.message}", error_details=e.details)
        raise convert_to_http_exception(e) from e
    except Exception as e:
        logger.error(f"Unexpected error creating repair invoice: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to create repair invoice", "error": str(e)}
        ) from e


@router.post("/invoices/{invoice_id}/confirm", response_model=RepairInvoiceResponse)
async def confirm_repair_invoice(
    invoice_id: int,
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Confirm a draft repair invoice, moving it to OPEN status.
    Once confirmed, the payment schedule becomes active.
    """
    try:
        invoice = await repair_service.confirm_repair_invoice(
            invoice_id=invoice_id,
            user_id=current_user.id
        )
        return invoice
    except RepairBaseException as e:
        raise convert_to_http_exception(e) from e


@router.get("/invoices/{invoice_id}", response_model=RepairInvoiceResponse)
async def get_repair_invoice(
    invoice_id: int,
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific repair invoice by ID.
    """
    try:
        invoice = await repair_service.get_repair_invoice(invoice_id)
        return invoice
    except RepairBaseException as e:
        raise convert_to_http_exception(e) from e


@router.get("/invoices/repair-id/{repair_id}", response_model=RepairInvoiceResponse)
async def get_repair_invoice_by_repair_id(
    repair_id: str,
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific repair invoice by repair_id.
    """
    try:
        invoice = await repair_service.get_repair_invoice_by_repair_id(repair_id)
        return invoice
    except RepairBaseException as e:
        raise convert_to_http_exception(e) from e


@router.get("/invoices", response_model=PaginatedRepairInvoiceResponse)
async def list_repair_invoices(
    status: Optional[InvoiceStatus] = Query(None),
    workshop_type: Optional[WorkshopType] = Query(None),
    driver_id: Optional[int] = Query(None),
    vehicle_id: Optional[int] = Query(None),
    medallion_id: Optional[int] = Query(None),
    invoice_number: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort_by: str = Query("created_on"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get a paginated list of repair invoices with optional filters.
    
    Filters:
    - status: Filter by invoice status
    - workshop_type: Filter by workshop type
    - driver_id: Filter by driver
    - vehicle_id: Filter by vehicle
    - medallion_id: Filter by medallion
    - invoice_number: Search by invoice number
    - from_date/to_date: Filter by invoice date range
    """
    try:
        filters = RepairInvoiceFilters(
            status=status,
            workshop_type=workshop_type,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            medallion_id=medallion_id,
            invoice_number=invoice_number,
            from_date=from_date,
            to_date=to_date
        )
        
        invoices, total = await repair_service.list_repair_invoices(
            filters=filters,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        total_pages = math.ceil(total / per_page)
        
        return PaginatedRepairInvoiceResponse(
            items=invoices,
            total_items=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error listing repair invoices: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to list repair invoices", "error": str(e)}
        ) from e


@router.put("/invoices/{invoice_id}", response_model=RepairInvoiceResponse)
async def update_repair_invoice(
    invoice_id: int,
    update_data: RepairInvoiceUpdate,
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Update a repair invoice.
    Note: Changing the repair amount is only allowed for DRAFT invoices.
    """
    try:
        invoice = await repair_service.update_repair_invoice(
            invoice_id=invoice_id,
            update_data=update_data,
            user_id=current_user.id
        )
        return invoice
    except RepairBaseException as e:
        raise convert_to_http_exception(e) from e


@router.post("/invoices/{invoice_id}/hold", response_model=RepairInvoiceResponse)
async def hold_repair_invoice(
    invoice_id: int,
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Put a repair invoice on hold.
    This freezes all scheduled installment postings until the hold is lifted.
    """
    try:
        invoice = await repair_service.hold_repair_invoice(
            invoice_id=invoice_id,
            user_id=current_user.id
        )
        return invoice
    except RepairBaseException as e:
        raise convert_to_http_exception(e) from e


@router.post("/invoices/{invoice_id}/cancel", response_model=RepairInvoiceResponse)
async def cancel_repair_invoice(
    invoice_id: int,
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel a repair invoice.
    Only allowed if no installments have been posted yet.
    """
    try:
        invoice = await repair_service.cancel_repair_invoice(
            invoice_id=invoice_id,
            user_id=current_user.id
        )
        return invoice
    except RepairBaseException as e:
        raise convert_to_http_exception(e) from e


# ===================== Installment Operations =====================

@router.get("/installments/{installment_id}", response_model=RepairInstallmentResponse)
async def get_installment(
    installment_id: int,
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get a specific repair installment by ID.
    """
    try:
        installment = await repair_service.get_installment(installment_id)
        return installment
    except RepairBaseException as e:
        raise convert_to_http_exception(e) from e


@router.get("/invoices/{invoice_id}/installments", response_model=list[RepairInstallmentResponse])
async def get_invoice_installments(
    invoice_id: int,
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get all installments for a specific repair invoice.
    """
    try:
        installments = await repair_service.get_installments_for_invoice(invoice_id)
        return installments
    except RepairBaseException as e:
        raise convert_to_http_exception(e) from e


@router.get("/installments", response_model=PaginatedRepairInstallmentResponse)
async def list_installments(
    repair_invoice_id: Optional[int] = Query(None),
    status: Optional[InstallmentStatus] = Query(None),
    week_start_date: Optional[date] = Query(None),
    week_end_date: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    sort_by: str = Query("week_start_date"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get a paginated list of installments with optional filters.
    """
    try:
        filters = RepairInstallmentFilters(
            repair_invoice_id=repair_invoice_id,
            status=status,
            week_start_date=week_start_date,
            week_end_date=week_end_date
        )
        
        installments, total = await repair_service.list_installments(
            filters=filters,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        total_pages = math.ceil(total / per_page)
        
        return PaginatedRepairInstallmentResponse(
            items=installments,
            total_items=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error listing installments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to list installments", "error": str(e)}
        ) from e


# ===================== Posting Operations =====================

@router.post("/post", response_model=RepairPostingResult)
async def post_repair_installments(
    posting_date: Optional[date] = Query(None, description="Date to post for (defaults to today)"),
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Post due repair installments to the ledger.
    
    This endpoint:
    1. Finds all scheduled installments where the payment period has started
    2. Creates ledger entries (PLACEHOLDER)
    3. Updates installment status to POSTED
    4. Updates invoice balances
    5. Closes invoices when fully paid
    
    Note: This is typically called automatically on Sunday mornings at 05:00 AM,
    but can be triggered manually if needed.
    """
    try:
        if posting_date is None:
            posting_date = date.today()
        
        logger.info(
            "Manual posting triggered",
            user_id=current_user.id,
            posting_date=posting_date
        )
        
        result = await repair_service.post_due_installments(posting_date)
        
        return RepairPostingResult(**result)
        
    except Exception as e:
        logger.error(f"Error posting installments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to post installments", "error": str(e)}
        ) from e


# ===================== Statistics and Reports =====================

@router.get("/statistics", response_model=dict)
async def get_repair_statistics(
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get overall repair invoice statistics.
    """
    try:
        stats = await repair_service.get_invoice_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to get statistics", "error": str(e)}
        ) from e


@router.get("/drivers/{driver_id}/summary", response_model=dict)
async def get_driver_repair_summary(
    driver_id: int,
    repair_service: RepairService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get repair summary for a specific driver.
    """
    try:
        summary = await repair_service.get_driver_repair_summary(driver_id)
        return summary
    except Exception as e:
        logger.error(f"Error getting driver summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to get driver summary", "error": str(e)}
        ) from e
    
