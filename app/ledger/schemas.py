# app/ledger/schemas.py

"""
Pydantic schemas for Centralized Ledger module.
Handles validation and serialization for ledger operations.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict


# === Enums ===

class LedgerCategory(str, Enum):
    """Ledger categories"""
    LEASE = "Lease"
    REPAIR = "Repair"
    LOAN = "Loan"
    EZPASS = "EZPass"
    PVB = "PVB"
    TLC = "TLC"
    TAXES = "Taxes"
    MISC = "Misc"
    EARNINGS = "Earnings"
    INTERIM_PAYMENT = "InterimPayment"
    DEPOSIT = "Deposit"


class LedgerEntryType(str, Enum):
    """Entry types for double-entry bookkeeping"""
    DEBIT = "Debit"
    CREDIT = "Credit"


class LedgerStatus(str, Enum):
    """Ledger status"""
    POSTED = "Posted"
    VOIDED = "Voided"


class BalanceStatus(str, Enum):
    """Balance status"""
    OPEN = "Open"
    CLOSED = "Closed"


# === Ledger Posting Schemas ===

class LedgerPostingBase(BaseModel):
    """Base schema for ledger posting"""
    category: LedgerCategory
    entry_type: LedgerEntryType
    amount: Decimal = Field(..., ge=0.01, decimal_places=2)
    driver_id: Optional[int] = Field(None, gt=0)
    vehicle_id: Optional[int] = Field(None, gt=0)
    vin: Optional[str] = Field(None, max_length=17)
    plate: Optional[str] = Field(None, max_length=16)
    medallion_id: Optional[int] = Field(None, gt=0)
    lease_id: Optional[int] = Field(None, gt=0)
    reference_id: str = Field(..., max_length=128)
    reference_type: Optional[str] = Field(None, max_length=32)
    transaction_date: Optional[date] = None
    description: Optional[str] = None


class LedgerPostingCreate(LedgerPostingBase):
    """Schema for creating ledger posting"""
    pass


class LedgerPostingResponse(LedgerPostingBase):
    """Schema for posting response"""
    id: int
    posting_id: str
    status: LedgerStatus = LedgerStatus.POSTED
    voided_by_posting_id: Optional[str] = None
    posted_on: datetime
    created_on: Optional[datetime] = None
    created_by: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


# === Ledger Balance Schemas ===

class LedgerBalanceBase(BaseModel):
    """Base schema for ledger balance"""
    category: LedgerCategory
    driver_id: int = Field(..., gt=0)
    vehicle_id: Optional[int] = Field(None, gt=0)
    vin: Optional[str] = Field(None, max_length=17)
    plate: Optional[str] = Field(None, max_length=16)
    medallion_id: Optional[int] = Field(None, gt=0)
    lease_id: Optional[int] = Field(None, gt=0)
    reference_id: str = Field(..., max_length=128)
    reference_type: Optional[str] = Field(None, max_length=32)
    original_amount: Decimal = Field(..., ge=0, decimal_places=2)
    obligation_date: Optional[date] = None
    due_date: Optional[date] = None
    description: Optional[str] = None


class LedgerBalanceCreate(LedgerBalanceBase):
    """Schema for creating ledger balance"""
    pass


class LedgerBalanceResponse(LedgerBalanceBase):
    """Schema for balance response"""
    id: int
    balance_id: str
    prior_balance: Decimal
    payment: Decimal
    balance: Decimal
    applied_payment_refs: Optional[str] = None
    status: BalanceStatus = BalanceStatus.OPEN
    closed_on: Optional[datetime] = None
    updated_on: datetime
    created_on: Optional[datetime] = None
    created_by: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


# === Query & Filter Schemas ===

class PostingFilterParams(BaseModel):
    """Filter parameters for postings"""
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    medallion_id: Optional[int] = None
    lease_id: Optional[int] = None
    category: Optional[LedgerCategory] = None
    entry_type: Optional[LedgerEntryType] = None
    status: Optional[LedgerStatus] = None
    reference_id: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=1000)


class BalanceFilterParams(BaseModel):
    """Filter parameters for balances"""
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    medallion_id: Optional[int] = None
    lease_id: Optional[int] = None
    category: Optional[LedgerCategory] = None
    status: Optional[BalanceStatus] = None
    reference_id: Optional[str] = None
    min_balance: Optional[Decimal] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=1000)


# === Pagination Schemas ===

class PaginatedPostingResponse(BaseModel):
    """Paginated response for postings"""
    items: List[LedgerPostingResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int


class PaginatedBalanceResponse(BaseModel):
    """Paginated response for balances"""
    items: List[LedgerBalanceResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int


# === Driver Ledger View Schemas ===

class DriverLedgerSummary(BaseModel):
    """Summary of driver's ledger position"""
    driver_id: int
    driver_name: str
    tlc_license: Optional[str] = None
    
    # Earnings
    total_earnings: Decimal = Decimal("0.00")
    
    # Obligations by category
    lease_due: Decimal = Decimal("0.00")
    repairs_due: Decimal = Decimal("0.00")
    loans_due: Decimal = Decimal("0.00")
    ezpass_due: Decimal = Decimal("0.00")
    pvb_due: Decimal = Decimal("0.00")
    tlc_due: Decimal = Decimal("0.00")
    taxes_due: Decimal = Decimal("0.00")
    misc_due: Decimal = Decimal("0.00")
    
    # Totals
    total_obligations: Decimal = Decimal("0.00")
    net_position: Decimal = Decimal("0.00")  # earnings - obligations
    
    # Metadata
    as_of_date: date
    open_balances_count: int = 0


class DriverLedgerDetail(BaseModel):
    """Detailed driver ledger view"""
    summary: DriverLedgerSummary
    postings: List[LedgerPostingResponse]
    balances: List[LedgerBalanceResponse]


# === Reconciliation Schemas ===

class ReconciliationRequest(BaseModel):
    """Request for ledger reconciliation"""
    driver_id: Optional[int] = None
    date_from: date
    date_to: date
    categories: Optional[List[LedgerCategory]] = None


class ReconciliationResult(BaseModel):
    """Result of reconciliation check"""
    success: bool
    message: str
    discrepancies: List[dict] = []
    summary: dict = {}


# === Reversal Schemas ===

class ReversalRequest(BaseModel):
    """Request to void a posting"""
    posting_id: str = Field(..., max_length=64)
    reason: str = Field(..., max_length=512)


class ReversalResponse(BaseModel):
    """Response for reversal operation"""
    success: bool
    message: str
    original_posting_id: str
    reversal_posting_id: str
    voided_at: datetime