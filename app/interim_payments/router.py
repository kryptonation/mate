# app/interim_payments/router.py

"""
FastAPI router for Interim Payments module.
Provides REST API endpoints for payment operations.
"""

import math
from typing import Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.interim_payments.services import InterimPaymentService
from app.interim_payments.schemas import (
    InterimPaymentResponse, InterimPaymentSummaryResponse,
    InterimPaymentFilters, PaginatedInterimPaymentResponse,
    InterimPaymentAllocationResponse, InterimPaymentAllocationFilters,
    PaginatedAllocationResponse, PaymentAllocationRequest,
    InterimPaymentCreationResult, ObligationListResponse,
    PaymentReceiptResponse, PaymentMethod, PaymentStatus,
    AllocationCategory,
)
from app.interim_payments.exceptions import (
    InterimPaymentNotFoundException, InvalidPaymentAmountException,
    PaymentCreationException, PaymentAllocationException,
)
from app.users.models import User
from app.users.utils import get_current_user
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/interim-payments", tags=["Interim Payments"])


# ===================== Payment Operations =====================

@router.post("", response_model=InterimPaymentCreationResult, status_code=status.HTTP_201_CREATED)
async def create_interim_payment(
    payment_request: PaymentAllocationRequest,
    interim_payment_service: InterimPaymentService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new interim payment with allocations.
    
    This endpoint:
    1. Validates driver and medallion
    2. Validates allocation amounts
    3. Creates payment record
    4. Processes allocations
    5. Posts to ledger (reduces Ledger_Balances)
    6. Auto-applies unallocated amount to Lease
    7. Generates receipt
    
    **Business Rules:**
    - Total allocations cannot exceed payment amount
    - Cannot allocate to statutory taxes
    - Partial payments allowed (obligation remains open)
    - Excess payments auto-applied to Lease
    - All allocations posted immediately to Ledger_Balances
    """
    try:
        logger.info(
            "Creating interim payment",
            user_id=current_user.id,
            driver_id=payment_request.driver_id,
            amount=str(payment_request.total_amount)
        )
        
        result = await interim_payment_service.create_payment_with_allocations(
            payment_request,
            created_by=current_user.id
        )
        
        return result
        
    except (InvalidPaymentAmountException, PaymentAllocationException) as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e)}
        ) from e
    
    except Exception as e:
        logger.error(f"Error generating receipt: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to generate receipt", "error": str(e)}
        ) from e


# ===================== Administrative Operations =====================

@router.post("/{payment_id}/void")
async def void_payment(
    payment_id: int,
    reason: str = Query(..., description="Reason for voiding payment"),
    interim_payment_service: InterimPaymentService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Void a payment (mark as voided and reverse ledger entries).
    
    **Important:** 
    - This is an administrative operation
    - Should only be used for same-day corrections
    - Requires proper authorization
    - Reverses all ledger postings
    - Restores original obligation balances
    
    **Use cases:**
    - Duplicate payment entry
    - Incorrect payment amount
    - Payment applied to wrong driver
    - Check bounced or payment reversed
    """
    try:
        logger.info(
            "Voiding payment",
            payment_id=payment_id,
            user_id=current_user.id,
            reason=reason
        )
        
        payment = await interim_payment_service.void_payment(payment_id, reason)
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "success": True,
                "message": f"Payment {payment.payment_id} has been voided",
                "payment_id": payment.payment_id,
                "status": payment.status
            }
        )
        
    except InterimPaymentNotFoundException as e:
        logger.error(f"Payment not found: {payment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e)}
        ) from e
    
    except Exception as e:
        logger.error(f"Error voiding payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to void payment", "error": str(e)}
        ) from e


# ===================== Statistics and Reports =====================

@router.get("/statistics/summary")
async def get_payment_statistics(
    date_from: Optional[date] = Query(None, description="Start date for statistics"),
    date_to: Optional[date] = Query(None, description="End date for statistics"),
    interim_payment_service: InterimPaymentService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get summary statistics for interim payments.
    
    Returns:
    - Total payments count
    - Total amount collected
    - Breakdown by payment method
    - Breakdown by category
    - Average payment amount
    - Top drivers by payment count
    """
    try:
        # TODO: Implement statistics aggregation
        # This would query the database for:
        # - COUNT(*) grouped by payment_method
        # - SUM(total_amount) grouped by date ranges
        # - JOIN with allocations to get category breakdown
        
        # Placeholder response
        return JSONResponse(
            content={
                "success": True,
                "statistics": {
                    "total_payments": 0,
                    "total_amount": "0.00",
                    "by_payment_method": {
                        "Cash": {"count": 0, "amount": "0.00"},
                        "Check": {"count": 0, "amount": "0.00"},
                        "ACH": {"count": 0, "amount": "0.00"}
                    },
                    "by_category": {
                        "Lease": "0.00",
                        "Repair": "0.00",
                        "Loan": "0.00",
                        "EZPass": "0.00",
                        "PVB": "0.00",
                        "Misc": "0.00"
                    },
                    "average_payment": "0.00"
                }
            }
        )
    except PaymentCreationException as e:
        logger.error(f"Payment creation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to create payment", "error": str(e)}
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "An unexpected error occurred", "error": str(e)}
        ) from e


@router.get("", response_model=PaginatedInterimPaymentResponse)
async def list_interim_payments(
    driver_id: Optional[int] = Query(None, description="Filter by driver ID"),
    medallion_id: Optional[int] = Query(None, description="Filter by medallion ID"),
    lease_id: Optional[int] = Query(None, description="Filter by lease ID"),
    payment_date_from: Optional[date] = Query(None, description="Filter from date"),
    payment_date_to: Optional[date] = Query(None, description="Filter to date"),
    payment_method: Optional[PaymentMethod] = Query(None, description="Filter by payment method"),
    payment_status: Optional[PaymentStatus] = Query(None, description="Filter by status"),
    receipt_number: Optional[str] = Query(None, description="Filter by receipt number"),
    payment_id: Optional[str] = Query(None, description="Filter by payment ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("payment_date", description="Sort by field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    interim_payment_service: InterimPaymentService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    List interim payments with filters and pagination.
    
    **Filters:**
    - driver_id: Filter by specific driver
    - medallion_id: Filter by medallion
    - payment_date_from/to: Date range filter
    - payment_method: Cash, Check, or ACH
    - payment_status: Completed, Voided, or Reversed
    - receipt_number: Exact receipt number match
    
    **Sorting:**
    - sort_by: payment_date, total_amount, created_on, etc.
    - sort_order: asc or desc
    """
    try:
        filters = InterimPaymentFilters(
            driver_id=driver_id,
            medallion_id=medallion_id,
            lease_id=lease_id,
            payment_date_from=payment_date_from,
            payment_date_to=payment_date_to,
            payment_method=payment_method,
            status=payment_status,
            receipt_number=receipt_number,
            payment_id=payment_id,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        payments, total = await interim_payment_service.get_payments(filters)
        
        total_pages = math.ceil(total / per_page)
        
        # Convert to summary response
        items = [
            InterimPaymentSummaryResponse(
                id=p.id,
                payment_id=p.payment_id,
                driver_id=p.driver_id,
                driver_name=p.driver.name if hasattr(p.driver, 'name') else None,
                medallion_number=p.medallion.medallion_number if hasattr(p.medallion, 'medallion_number') else None,
                payment_date=p.payment_date,
                total_amount=p.total_amount,
                payment_method=p.payment_method,
                status=p.status,
                receipt_number=p.receipt_number
            )
            for p in payments
        ]
        
        return PaginatedInterimPaymentResponse(
            items=items,
            total_items=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error listing payments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to list payments", "error": str(e)}
        ) from e


@router.get("/{payment_id}", response_model=InterimPaymentResponse)
async def get_interim_payment(
    payment_id: int,
    interim_payment_service: InterimPaymentService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get a single interim payment by ID with all allocations.
    
    Returns complete payment details including:
    - Payment information
    - All allocation line items
    - Ledger posting references
    - Receipt details
    """
    try:
        payment = await interim_payment_service.get_payment_by_id(payment_id)
        return InterimPaymentResponse.model_validate(payment)
        
    except InterimPaymentNotFoundException as e:
        logger.error(f"Payment not found: {payment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e)}
        ) from e
    
    except Exception as e:
        logger.error(f"Error getting payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to get payment", "error": str(e)}
        ) from e


# ===================== Allocation Operations =====================

@router.get("/allocations/all", response_model=PaginatedAllocationResponse)
async def list_allocations(
    payment_id: Optional[int] = Query(None, description="Filter by payment ID"),
    category: Optional[AllocationCategory] = Query(None, description="Filter by category"),
    reference_id: Optional[str] = Query(None, description="Filter by reference ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_on", description="Sort by field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
    interim_payment_service: InterimPaymentService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    List payment allocations with filters.
    
    Useful for:
    - Viewing all allocations for a specific payment
    - Finding allocations by category (e.g., all Repair allocations)
    - Tracking allocations to specific obligations
    """
    try:
        filters = InterimPaymentAllocationFilters(
            payment_id=payment_id,
            category=category,
            reference_id=reference_id,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        allocations, total = await interim_payment_service.get_allocations(filters)
        
        total_pages = math.ceil(total / per_page)
        
        items = [
            InterimPaymentAllocationResponse.model_validate(a)
            for a in allocations
        ]
        
        return PaginatedAllocationResponse(
            items=items,
            total_items=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages
        )
        
    except Exception as e:
        logger.error(f"Error listing allocations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to list allocations", "error": str(e)}
        ) from e


# ===================== UI Support Endpoints =====================

@router.get("/obligations/{driver_id}/{medallion_id}", response_model=ObligationListResponse)
async def get_outstanding_obligations(
    driver_id: int,
    medallion_id: int,
    lease_id: Optional[int] = Query(None, description="Optional lease ID"),
    interim_payment_service: InterimPaymentService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get all outstanding obligations for a driver/medallion.
    
    Used by the UI allocation screen to display:
    - All open Lease obligations
    - Outstanding Repair invoices
    - Unpaid Driver Loans
    - Open EZPass tolls
    - Unpaid PVB violations
    - Miscellaneous charges
    
    Returns obligations grouped by category with:
    - Reference ID (Invoice #, Loan ID, etc.)
    - Description
    - Outstanding amount
    - Due date and age
    """
    try:
        obligations = await interim_payment_service.get_outstanding_obligations(
            driver_id,
            medallion_id,
            lease_id
        )
        
        return obligations
        
    except Exception as e:
        logger.error(f"Error getting obligations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": "Failed to get obligations", "error": str(e)}
        ) from e


@router.get("/{payment_id}/receipt", response_model=PaymentReceiptResponse)
async def get_payment_receipt(
    payment_id: int,
    interim_payment_service: InterimPaymentService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Generate and retrieve receipt for a payment.
    
    Returns formatted receipt with:
    - Driver and medallion information
    - Payment details (method, amount, date)
    - Line-by-line allocation breakdown
    - Auto-allocated amounts (if any)
    - Receipt number and timestamp
    
    This endpoint can be used to:
    - Display receipt on screen
    - Print receipt
    - Email receipt to driver
    """
    try:
        receipt = await interim_payment_service.generate_receipt(payment_id)
        return receipt
        
    except InterimPaymentNotFoundException as e:
        logger.error(f"Payment not found: {payment_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": str(e)}
        ) from e