# app/ledger/router.py

"""
FastAPI router for Centralized Ledger endpoints.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_db
from app.users.utils import get_current_user
from app.utils.logger import get_logger
from app.ledger.services import LedgerService
from app.ledger.schemas import (
    LedgerPostingResponse, LedgerBalanceResponse,
    PostingFilterParams, BalanceFilterParams,
    PaginatedPostingResponse, PaginatedBalanceResponse,
    DriverLedgerSummary, DriverLedgerDetail,
    ReversalRequest, ReversalResponse,
    LedgerCategory, LedgerStatus, BalanceStatus
)

logger = get_logger(__name__)

router = APIRouter(prefix="/ledger", tags=["Ledger"])


# === Posting Endpoints ===

@router.get("/postings", response_model=PaginatedPostingResponse)
async def list_postings(
    driver_id: Optional[int] = Query(None),
    vehicle_id: Optional[int] = Query(None),
    medallion_id: Optional[int] = Query(None),
    lease_id: Optional[int] = Query(None),
    category: Optional[LedgerCategory] = Query(None),
    status: Optional[LedgerStatus] = Query(None),
    reference_id: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    List ledger postings with filters and pagination.
    
    **Filters:**
    - driver_id: Filter by driver
    - vehicle_id: Filter by vehicle
    - medallion_id: Filter by medallion
    - lease_id: Filter by lease
    - category: Filter by category (Lease, Repair, Loan, etc.)
    - status: Filter by status (Posted, Voided)
    - reference_id: Filter by source reference
    - date_from/date_to: Filter by transaction date range
    """
    logger.info(f"Listing postings - user: {current_user['id']}")
    
    service = LedgerService(db)
    
    filters = PostingFilterParams(
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        medallion_id=medallion_id,
        lease_id=lease_id,
        category=category,
        status=status,
        reference_id=reference_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page
    )
    
    postings, total_items = await service.repo.get_postings_filtered(filters)
    
    total_pages = (total_items + per_page - 1) // per_page
    
    return PaginatedPostingResponse(
        items=[LedgerPostingResponse.model_validate(p) for p in postings],
        total_items=total_items,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/postings/{posting_id}", response_model=LedgerPostingResponse)
async def get_posting(
    posting_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get a specific ledger posting by posting_id"""
    logger.info(f"Getting posting: {posting_id}")
    
    service = LedgerService(db)
    posting = await service.repo.get_posting_by_posting_id(posting_id)
    
    if not posting:
        from app.ledger.exceptions import LedgerNotFoundException
        raise LedgerNotFoundException(posting_id=posting_id)
    
    return LedgerPostingResponse.model_validate(posting)


@router.get("/postings/reference/{reference_id}", response_model=list[LedgerPostingResponse])
async def get_postings_by_reference(
    reference_id: str,
    reference_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get all postings for a specific reference (e.g., Repair Invoice, Loan, etc.)"""
    logger.info(f"Getting postings for reference: {reference_id}")
    
    service = LedgerService(db)
    postings = await service.repo.get_postings_by_reference(reference_id, reference_type)
    
    return [LedgerPostingResponse.model_validate(p) for p in postings]


@router.post("/postings/void", response_model=ReversalResponse)
async def void_posting(
    request: ReversalRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Void a ledger posting by creating a reversal entry.
    
    **Important:** This operation is irreversible and creates an audit trail.
    """
    logger.info(f"Voiding posting: {request.posting_id} - user: {current_user['id']}")
    
    service = LedgerService(db)
    result = await service.void_posting(request, created_by=current_user["id"])
    
    return result


# === Balance Endpoints ===

@router.get("/balances", response_model=PaginatedBalanceResponse)
async def list_balances(
    driver_id: Optional[int] = Query(None),
    vehicle_id: Optional[int] = Query(None),
    medallion_id: Optional[int] = Query(None),
    lease_id: Optional[int] = Query(None),
    category: Optional[LedgerCategory] = Query(None),
    status: Optional[BalanceStatus] = Query(None),
    reference_id: Optional[str] = Query(None),
    min_balance: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    List ledger balances with filters and pagination.
    
    **Filters:**
    - driver_id: Filter by driver
    - vehicle_id: Filter by vehicle
    - medallion_id: Filter by medallion
    - lease_id: Filter by lease
    - category: Filter by category
    - status: Filter by status (Open, Closed)
    - reference_id: Filter by source reference
    - min_balance: Filter by minimum balance amount
    """
    logger.info(f"Listing balances - user: {current_user['id']}")
    
    service = LedgerService(db)
    
    filters = BalanceFilterParams(
        driver_id=driver_id,
        vehicle_id=vehicle_id,
        medallion_id=medallion_id,
        lease_id=lease_id,
        category=category,
        status=status,
        reference_id=reference_id,
        min_balance=min_balance,
        page=page,
        per_page=per_page
    )
    
    balances, total_items = await service.repo.get_balances_filtered(filters)
    
    total_pages = (total_items + per_page - 1) // per_page
    
    return PaginatedBalanceResponse(
        items=[LedgerBalanceResponse.model_validate(b) for b in balances],
        total_items=total_items,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/balances/{balance_id}", response_model=LedgerBalanceResponse)
async def get_balance(
    balance_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get a specific ledger balance by balance_id"""
    logger.info(f"Getting balance: {balance_id}")
    
    service = LedgerService(db)
    balance = await service.repo.get_balance_by_balance_id(balance_id)
    
    if not balance:
        from app.ledger.exceptions import LedgerNotFoundException
        raise LedgerNotFoundException(balance_id=balance_id)
    
    return LedgerBalanceResponse.model_validate(balance)


@router.get("/balances/reference/{reference_id}", response_model=LedgerBalanceResponse)
async def get_balance_by_reference(
    reference_id: str,
    reference_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """Get balance for a specific reference (e.g., Repair Invoice, Loan, etc.)"""
    logger.info(f"Getting balance for reference: {reference_id}")
    
    service = LedgerService(db)
    balance = await service.repo.get_balance_by_reference(reference_id, reference_type)
    
    if not balance:
        from app.ledger.exceptions import LedgerNotFoundException
        raise LedgerNotFoundException(balance_id=reference_id)
    
    return LedgerBalanceResponse.model_validate(balance)


@router.get("/balances/driver/{driver_id}/open", response_model=list[LedgerBalanceResponse])
async def get_driver_open_balances(
    driver_id: int,
    category: Optional[LedgerCategory] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get all open balances for a driver.
    
    **Use case:** Interim payment allocation UI needs to show all outstanding obligations.
    """
    logger.info(f"Getting open balances for driver: {driver_id}")
    
    service = LedgerService(db)
    balances = await service.repo.get_open_balances_by_driver(
        driver_id, 
        category.value if category else None
    )
    
    return [LedgerBalanceResponse.model_validate(b) for b in balances]


# === Driver Ledger View ===

@router.get("/driver/{driver_id}/summary", response_model=DriverLedgerSummary)
async def get_driver_summary(
    driver_id: int,
    as_of_date: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get comprehensive summary of driver's ledger position.
    
    **Returns:**
    - Total earnings
    - Obligations by category (Lease, Repairs, Loans, EZPass, PVB, TLC, Taxes, Misc)
    - Net position (earnings - obligations)
    - Count of open balances
    """
    logger.info(f"Getting driver summary: {driver_id}")
    
    service = LedgerService(db)
    summary = await service.get_driver_ledger_summary(driver_id, as_of_date)
    
    return summary


@router.get("/driver/{driver_id}/detail", response_model=DriverLedgerDetail)
async def get_driver_detail(
    driver_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get detailed driver ledger view with all postings and balances.
    
    **Use case:** Driver dispute resolution, detailed reconciliation
    """
    logger.info(f"Getting driver detail: {driver_id}")
    
    service = LedgerService(db)
    
    # Get summary
    summary = await service.get_driver_ledger_summary(driver_id, date_to)
    
    # Get postings
    postings = await service.repo.get_driver_postings(driver_id, date_from, date_to)
    
    # Get balances
    balances = await service.repo.get_open_balances_by_driver(driver_id)
    
    return DriverLedgerDetail(
        summary=summary,
        postings=[LedgerPostingResponse.model_validate(p) for p in postings],
        balances=[LedgerBalanceResponse.model_validate(b) for b in balances]
    )


# === Statistics ===

@router.get("/statistics/outstanding")
async def get_outstanding_statistics(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get system-wide outstanding balance statistics by category.
    
    **Returns:** Total outstanding for each category across all drivers.
    """
    logger.info("Getting outstanding statistics")
    
    from sqlalchemy import select, func
    from app.ledger.models import LedgerBalance, BalanceStatus
    
    stmt = select(
        LedgerBalance.category,
        func.sum(LedgerBalance.balance).label("total_outstanding"),
        func.count(LedgerBalance.id).label("count")
    ).where(LedgerBalance.status == BalanceStatus.OPEN.value)
    stmt = stmt.group_by(LedgerBalance.category)
    
    result = await db.execute(stmt)
    rows = result.all()
    
    statistics = {
        "by_category": {
            row.category: {
                "total_outstanding": float(row.total_outstanding or 0),
                "count": row.count
            }
            for row in rows
        },
        "grand_total": sum(float(row.total_outstanding or 0) for row in rows),
        "total_open_balances": sum(row.count for row in rows)
    }
    
    return statistics