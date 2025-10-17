# app/driver_loans/schemas.py

"""
Pydantic schemas for Driver Loans module.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


# === Enums ===

class LoanStatus(str, Enum):
    """Loan status enum."""
    DRAFT = "Draft"
    OPEN = "Open"
    CLOSED = "Closed"
    HOLD = "Hold"
    CANCELLED = "Cancelled"


class InstallmentStatus(str, Enum):
    """Installment status enum."""
    SCHEDULED = "Scheduled"
    DUE = "Due"
    POSTED = "Posted"
    PAID = "Paid"


class StartWeekOption(str, Enum):
    """Start week options for loan repayment."""
    CURRENT = "Current Payment Period"
    NEXT = "Next Payment Period"


# === Driver Loan Schemas ===

class DriverLoanBase(BaseModel):
    """Base schema for Driver Loan."""
    driver_id: int
    medallion_id: Optional[int] = None
    lease_id: Optional[int] = None
    loan_amount: Decimal = Field(..., ge=1, description="Loan amount must be >= $1")
    interest_rate: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=20,
        description="Annual interest rate (0-20%)"
    )
    loan_date: date
    purpose: Optional[str] = Field(None, max_length=250)
    notes: Optional[str] = None


class DriverLoanCreate(DriverLoanBase):
    """Schema for creating Driver Loan."""
    start_week_option: StartWeekOption = StartWeekOption.CURRENT
    
    @field_validator('loan_amount')
    @classmethod
    def validate_loan_amount(cls, v: Decimal) -> Decimal:
        """Ensure loan amount is positive."""
        if v < 1:
            raise ValueError('Loan amount must be at least $1')
        return v
    
    @field_validator('interest_rate')
    @classmethod
    def validate_interest_rate(cls, v: Decimal) -> Decimal:
        """Ensure interest rate is within valid range."""
        if v < 0 or v > 20:
            raise ValueError('Interest rate must be between 0% and 20%')
        return v


class DriverLoanUpdate(BaseModel):
    """Schema for updating Driver Loan."""
    status: Optional[LoanStatus] = None
    purpose: Optional[str] = Field(None, max_length=250)
    notes: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class DriverLoanResponse(DriverLoanBase):
    """Schema for Driver Loan Response."""
    id: int
    loan_id: str
    start_week: date
    status: str
    total_principal_paid: Decimal
    total_interest_paid: Decimal
    outstanding_balance: Decimal
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None
    created_by: Optional[int] = None
    modified_by: Optional[int] = None
    
    # Related data
    installments: Optional[List["DriverLoanInstallmentResponse"]] = []
    
    model_config = ConfigDict(from_attributes=True)


class DriverLoanSummaryResponse(BaseModel):
    """Schema for Driver Loan summary response."""
    id: int
    loan_id: str
    driver_id: int
    driver_name: Optional[str] = None
    medallion_number: Optional[str] = None
    loan_amount: Decimal
    interest_rate: Decimal
    loan_date: date
    status: str
    outstanding_balance: Decimal
    next_payment_due: Optional[Decimal] = None
    next_payment_date: Optional[date] = None
    
    model_config = ConfigDict(from_attributes=True)


# === Driver Loan Installment Schemas ===

class DriverLoanInstallmentBase(BaseModel):
    """Base schema for Driver Loan Installment."""
    installment_number: int
    week_start_date: date
    week_end_date: date
    principal_amount: Decimal
    interest_amount: Decimal
    total_due: Decimal
    outstanding_principal: Decimal
    remaining_balance: Decimal


class DriverLoanInstallmentCreate(DriverLoanInstallmentBase):
    """Schema for creating Driver Loan Installment."""
    loan_id: int
    installment_id: str
    prior_balance: Decimal = Decimal("0.00")


class DriverLoanInstallmentUpdate(BaseModel):
    """Schema for updating Driver Loan Installment."""
    status: Optional[InstallmentStatus] = None
    posting_date: Optional[datetime] = None
    ledger_posting_ref: Optional[str] = None
    amount_paid: Optional[Decimal] = None
    payment_date: Optional[date] = None
    
    model_config = ConfigDict(from_attributes=True)


class DriverLoanInstallmentResponse(DriverLoanInstallmentBase):
    """Schema for Driver Loan Installment Response."""
    id: int
    installment_id: str
    loan_id: int
    prior_balance: Decimal
    status: str
    posting_date: Optional[datetime] = None
    ledger_posting_ref: Optional[str] = None
    amount_paid: Decimal
    payment_date: Optional[date] = None
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# === Payment Schedule Schemas ===

class PaymentScheduleRequest(BaseModel):
    """Request schema for generating payment schedule."""
    loan_amount: Decimal = Field(..., ge=1)
    interest_rate: Decimal = Field(default=Decimal("0.00"), ge=0, le=20)
    loan_date: date
    start_week_option: StartWeekOption = StartWeekOption.CURRENT


class PaymentScheduleResponse(BaseModel):
    """Response schema for payment schedule generation."""
    loan_amount: Decimal
    interest_rate: Decimal
    total_interest: Decimal
    total_amount: Decimal
    number_of_installments: int
    weekly_payment: Decimal
    installments: List[dict]
    
    model_config = ConfigDict(from_attributes=True)


# === Filter and Query Schemas ===

class DriverLoanFilters(BaseModel):
    """Filters for querying driver loans."""
    driver_id: Optional[int] = None
    medallion_id: Optional[int] = None
    status: Optional[str] = None
    loan_date_from: Optional[date] = None
    loan_date_to: Optional[date] = None
    outstanding_only: bool = False
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=100)
    sort_by: str = Field(default="created_on")
    sort_order: str = Field(default="desc")


class DriverLoanInstallmentFilters(BaseModel):
    """Filters for querying loan installments."""
    loan_id: Optional[int] = None
    status: Optional[str] = None
    week_start_from: Optional[date] = None
    week_start_to: Optional[date] = None
    due_only: bool = False
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=100)
    sort_by: str = Field(default="week_start_date")
    sort_order: str = Field(default="asc")


class PaginatedDriverLoanResponse(BaseModel):
    """Paginated response for Driver Loans."""
    items: List[DriverLoanSummaryResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    statuses: List[str] = ["Draft", "Open", "Closed", "Hold", "Cancelled"]


class PaginatedInstallmentResponse(BaseModel):
    """Paginated response for Loan Installments."""
    items: List[DriverLoanInstallmentResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    statuses: List[str] = ["Scheduled", "Due", "Posted", "Paid"]


# === Operation Result Schemas ===

class LoanCreationResult(BaseModel):
    """Result schema for loan creation operation."""
    success: bool
    loan_id: str
    message: str
    loan: Optional[DriverLoanResponse] = None
    schedule: Optional[List[DriverLoanInstallmentResponse]] = None
    error: Optional[str] = None


class LoanPostingResult(BaseModel):
    """Result schema for loan posting operation."""
    success: bool
    total_processed: int
    posted_count: int
    failed_count: int
    message: str
    details: Optional[List[dict]] = None


class LoanAdjustmentRequest(BaseModel):
    """Request schema for loan adjustment."""
    loan_id: int
    adjustment_type: str  # credit, waiver, restructure
    amount: Optional[Decimal] = None
    reason: str
    effective_date: date


class LoanAdjustmentResult(BaseModel):
    """Result schema for loan adjustment operation."""
    success: bool
    loan_id: str
    adjustment_type: str
    message: str
    updated_loan: Optional[DriverLoanResponse] = None
    error: Optional[str] = None


# === Log Schemas ===

class DriverLoanLogBase(BaseModel):
    """Base schema for Driver Loan Log."""
    log_date: datetime
    log_type: str
    loan_id: Optional[int] = None
    records_impacted: Optional[int] = None
    status: str = "Success"
    details: Optional[str] = None


class DriverLoanLogCreate(DriverLoanLogBase):
    """Schema for creating Driver Loan Log."""
    pass


class DriverLoanLogResponse(DriverLoanLogBase):
    """Schema for Driver Loan Log Response."""
    id: int
    created_on: Optional[datetime] = None
    created_by: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


# Update forward references
DriverLoanResponse.model_rebuild()
PaymentScheduleResponse.model_rebuild()