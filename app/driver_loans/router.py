# app/driver_loans/router.py

"""
FastAPI router for Driver Loans module.
Provides REST API endpoints for loan management, schedule generation, and posting.
"""

from typing import List, Optional
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status, Query

from app.driver_loans.services import DriverLoanService
from app.driver_loans.schemas import (
    DriverLoanCreate, DriverLoanUpdate, DriverLoanResponse,
    DriverLoanSummaryResponse, DriverLoanFilters,
    DriverLoanInstallmentResponse, DriverLoanInstallmentFilters,
    PaginatedDriverLoanResponse, PaginatedInstallmentResponse,
    PaymentScheduleRequest, PaymentScheduleResponse,
    LoanCreationResult, LoanPostingResult, LoanStatus,
)
from app.driver_loans.exceptions import (
    DriverLoanNotFoundException,
    DriverLoanCreationException,
    DriverLoanPostingException,
)
from app.users.utils import get_current_user
from app.users.models import User
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/driver-loans",
    tags=["Driver Loans"],
    responses={404: {"description": "Not found"}},
)

# === Loan Management Endpoints ===

@router.post("/", response_model=LoanCreationResult, status_code=status.HTTP_201_CREATED)
async def create_driver_loan(
    loan_data: DriverLoanCreate,
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user),
) -> LoanCreationResult:
    """
    Create a new driver loan with automatic payment schedule generation.
    
    This endpoint:
    1. Creates a loan record
    2. Generates payment schedule based on Loan Repayment Matrix
    3. Calculates interest for each installment
    4. Returns the created loan with full schedule
    """
    logger.info(
        "Creating driver loan",
        user_id=current_user.id,
        driver_id=loan_data.driver_id,
        amount=str(loan_data.loan_amount)
    )

    try:
        result = await service.create_loan_with_schedule(loan_data)
        return result
    except DriverLoanCreationException as e:
        logger.error("Failed to create loan", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create loan",
        ) from e
    
@router.get("/{loan_id}", response_model=DriverLoanResponse)
async def get_driver_loan(
    loan_id: int,
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user)
) -> DriverLoanResponse:
    """
    Get a specific driver loan by ID with all installments.
    """
    logger.info("Getting loan", loan_id=loan_id, user_id=current_user.id)

    try:
        loan = await service.get_loan_by_id(loan_id)
        return loan
    except DriverLoanNotFoundException as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    
@router.get("/", response_model=PaginatedDriverLoanResponse)
async def get_loans(
    driver_id: Optional[int] = Query(None, description="Filter by driver ID"),
    medallion_id: Optional[int] = Query(None, description="Filter by medallion ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    loan_date_from: Optional[date] = Query(None, description="Filter by loan date from"),
    loan_date_to: Optional[date] = Query(None, description="Filter by loan date to"),
    outstanding_only: bool = Query(False, description="Show only loans with outstanding balance"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_on", description="Sort field"),
    sort_order: str = Query("desc", regex="^(asc|desc)$", description="Sort order"),
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user),
) -> PaginatedDriverLoanResponse:
    """
    Get paginated list of driver loans with filters
    """
    logger.info("Getting loans list", user_id=current_user.id)

    filters = DriverLoanFilters(
        driver_id=driver_id,
        medallion_id=medallion_id,
        status=status,
        loan_date_from=loan_date_from,
        loan_date_to=loan_date_to,
        outstanding_only=outstanding_only,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    
    loans, total_items = await service.get_loans(filters)
    
    # Convert to summary response
    items = [
        DriverLoanSummaryResponse(
            id=loan.id,
            loan_id=loan.loan_id,
            driver_id=loan.driver_id,
            driver_name=f"{loan.driver.first_name} {loan.driver.last_name}" if loan.driver else None,
            medallion_number=loan.medallion.medallion_number if loan.medallion else None,
            loan_amount=loan.loan_amount,
            interest_rate=loan.interest_rate,
            loan_date=loan.loan_date,
            status=loan.status,
            outstanding_balance=loan.outstanding_balance,
            next_payment_due=None,  # Could be calculated from installments
            next_payment_date=None,
        )
        for loan in loans
    ]
    
    total_pages = (total_items + per_page - 1) // per_page
    
    return PaginatedDriverLoanResponse(
        items=items,
        total_items=total_items,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )

@router.put("/{loan_id}", response_model=DriverLoanResponse)
async def update_loan(
    loan_id: int,
    loan_update: DriverLoanUpdate,
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user),
) -> DriverLoanResponse:
    """
    Update a driver loan (limited fields).
    
    Only certain fields can be updated after loan creation:
    - Status (with validation)
    - Purpose/Notes
    """
    logger.info("Updating loan", loan_id=loan_id, user_id=current_user.id)
    
    try:
        loan = await service.get_loan_by_id(loan_id)
        
        # If status update is requested, use the status update service
        if loan_update.status:
            loan = await service.update_loan_status(
                loan_id,
                loan_update.status,
                loan_update.notes,
            )
        
        return loan
    except (DriverLoanNotFoundException, Exception) as e:
        logger.error("Failed to update loan", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.put("/{loan_id}/status", response_model=DriverLoanResponse)
async def update_loan_status(
    loan_id: int,
    new_status: LoanStatus,
    reason: Optional[str] = None,
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user),
) -> DriverLoanResponse:
    """
    Update loan status with validation.
    
    Valid transitions:
    - Draft → Open, Cancelled
    - Open → Hold, Closed
    - Hold → Open, Closed
    """
    logger.info(
        "Updating loan status",
        loan_id=loan_id,
        new_status=new_status,
        user_id=current_user.id,
    )
    
    try:
        loan = await service.update_loan_status(loan_id, new_status, reason)
        return loan
    except (DriverLoanNotFoundException, Exception) as e:
        logger.error("Failed to update loan status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# === Payment Schedule Endpoints ===

@router.post("/schedule/preview", response_model=PaymentScheduleResponse)
async def preview_payment_schedule(
    request: PaymentScheduleRequest,
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user),
) -> PaymentScheduleResponse:
    """
    Generate a payment schedule preview without creating a loan.
    
    This endpoint allows users to see what the payment schedule would look like
    for a given loan amount and interest rate before actually creating the loan.
    """
    logger.info(
        "Generating payment schedule preview",
        user_id=current_user.id,
        amount=str(request.loan_amount),
        rate=str(request.interest_rate),
    )
    
    try:
        schedule = await service.generate_payment_schedule_preview(request)
        return schedule
    except Exception as e:
        logger.error("Failed to generate schedule preview", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


# === Installment Endpoints ===

@router.get("/installments/", response_model=PaginatedInstallmentResponse)
async def get_installments(
    loan_id: Optional[int] = Query(None, description="Filter by loan ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    week_start_from: Optional[date] = Query(None, description="Filter by week start from"),
    week_start_to: Optional[date] = Query(None, description="Filter by week start to"),
    due_only: bool = Query(False, description="Show only due installments"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("week_start_date", description="Sort field"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user),
) -> PaginatedInstallmentResponse:
    """
    Get paginated list of loan installments with filters.
    """
    logger.info("Getting installments list", user_id=current_user.id)
    
    filters = DriverLoanInstallmentFilters(
        loan_id=loan_id,
        status=status,
        week_start_from=week_start_from,
        week_start_to=week_start_to,
        due_only=due_only,
        page=page,
        per_page=per_page,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    
    installments, total_items = await service.get_installments(filters)
    
    # Convert to response
    items = [
        DriverLoanInstallmentResponse.model_validate(installment)
        for installment in installments
    ]
    
    total_pages = (total_items + per_page - 1) // per_page
    
    return PaginatedInstallmentResponse(
        items=items,
        total_items=total_items,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
    )


@router.get("/loans/{loan_id}/installments", response_model=List[DriverLoanInstallmentResponse])
async def get_loan_installments(
    loan_id: int,
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user),
) -> List[DriverLoanInstallmentResponse]:
    """
    Get all installments for a specific loan.
    """
    logger.info("Getting loan installments", loan_id=loan_id, user_id=current_user.id)
    
    filters = DriverLoanInstallmentFilters(
        loan_id=loan_id,
        page=1,
        per_page=100,  # Get all installments
        sort_by="installment_number",
        sort_order="asc",
    )
    
    installments, _ = await service.get_installments(filters)
    
    return [
        DriverLoanInstallmentResponse.model_validate(installment)
        for installment in installments
    ]


# === Posting and Processing Endpoints ===

@router.post("/installments/process", response_model=LoanPostingResult)
async def process_due_installments(
    as_of_date: Optional[date] = Query(None, description="Process installments due as of this date"),
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user),
) -> LoanPostingResult:
    """
    Process all due installments for posting to ledger.
    
    This endpoint would typically be called by a scheduled task every Sunday at 5:00 AM,
    but can also be triggered manually for testing or special processing.
    
    Processing steps:
    1. Find all installments due as of the specified date
    2. Post each installment to the ledger
    3. Update loan balances
    4. Check for completed loans and close them
    """
    logger.info(
        "Processing due installments",
        user_id=current_user.id,
        as_of_date=as_of_date,
    )
    
    try:
        result = await service.process_due_installments(as_of_date)
        return result
    except DriverLoanPostingException as e:
        logger.error("Failed to process installments", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error("Unexpected error processing installments", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process installments",
        ) from e


# === Dashboard and Summary Endpoints ===

@router.get("/dashboard/summary")
async def get_loan_dashboard_summary(
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get dashboard summary for driver loans.
    
    Returns:
    - Total loans by status
    - Total outstanding balance
    - Installments due this week
    - Recent loan activity
    """
    logger.info("Getting loan dashboard summary", user_id=current_user.id)
    
    # This would aggregate data from the service
    # Implementation would include various summary statistics
    
    return {
        "total_loans": {
            "draft": 0,
            "open": 0,
            "closed": 0,
            "hold": 0,
            "cancelled": 0,
        },
        "financial_summary": {
            "total_outstanding": 0,
            "due_this_week": 0,
            "collected_this_month": 0,
        },
        "recent_activity": [],
    }


@router.get("/reports/aging")
async def get_aging_report(
    as_of_date: Optional[date] = Query(None, description="Generate report as of this date"),
    service: DriverLoanService = Depends(),
    current_user: User = Depends(get_current_user),
):
    """
    Get aging report for outstanding loans.
    
    Groups outstanding balances by age:
    - Current (0-30 days)
    - 30-60 days
    - 60-90 days
    - Over 90 days
    """
    logger.info("Generating aging report", user_id=current_user.id, as_of_date=as_of_date)
    
    # Implementation would calculate aging buckets
    return {
        "as_of_date": as_of_date,
        "aging_buckets": {
            "current": {"count": 0, "amount": 0},
            "days_30_60": {"count": 0, "amount": 0},
            "days_60_90": {"count": 0, "amount": 0},
            "over_90": {"count": 0, "amount": 0},
        },
        "total_outstanding": 0,
    }