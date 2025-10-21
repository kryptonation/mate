# app/interim_payments/schemas.py

"""
Pydantic schemas for Interim Payments module.
Handles validation and serialization for payment operations.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


# === Enums ===

class PaymentMethod(str, Enum):
    """Payment method options"""
    CASH = "Cash"
    CHECK = "Check"
    ACH = "ACH"


class AllocationCategory(str, Enum):
    """Obligation categories for payment allocation"""
    LEASE = "Lease"
    REPAIR = "Repair"
    LOAN = "Loan"
    EZPASS = "EZPass"
    PVB = "PVB"
    MISC = "Misc"


class PaymentStatus(str, Enum):
    """Payment status"""
    COMPLETED = "Completed"
    VOIDED = "Voided"
    REVERSED = "Reversed"


class LogType(str, Enum):
    """Log operation types"""
    CREATE = "Create"
    ALLOCATE = "Allocate"
    VOID = "Void"
    REVERSE = "Reverse"


class LogStatus(str, Enum):
    """Log status"""
    SUCCESS = "Success"
    FAILURE = "Failure"
    PARTIAL = "Partial"


# === Interim Payment Allocation Schemas ===

class InterimPaymentAllocationBase(BaseModel):
    """Base schema for payment allocation"""
    category: AllocationCategory
    reference_id: str = Field(..., max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    allocated_amount: Decimal = Field(..., ge=0.01, decimal_places=2)
    outstanding_before: Decimal = Field(..., ge=0, decimal_places=2)


class InterimPaymentAllocationCreate(InterimPaymentAllocationBase):
    """Schema for creating payment allocation"""
    pass


class InterimPaymentAllocationResponse(InterimPaymentAllocationBase):
    """Schema for allocation response"""
    id: int
    payment_id: int
    outstanding_after: Decimal
    ledger_posting_ref: Optional[str] = None
    posted_at: Optional[datetime] = None
    created_on: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


# === Interim Payment Schemas ===

class InterimPaymentBase(BaseModel):
    """Base schema for interim payment"""
    driver_id: int = Field(..., gt=0)
    medallion_id: int = Field(..., gt=0)
    lease_id: Optional[int] = Field(None, gt=0)
    payment_date: date
    total_amount: Decimal = Field(..., gt=0, decimal_places=2)
    payment_method: PaymentMethod
    check_number: Optional[str] = Field(None, max_length=64)
    notes: Optional[str] = Field(None, max_length=512)


class InterimPaymentCreate(InterimPaymentBase):
    """Schema for creating interim payment with allocations"""
    allocations: List[InterimPaymentAllocationCreate] = Field(
        ..., 
        min_length=1,
        description="At least one allocation required"
    )
    
    @field_validator('allocations')
    @classmethod
    def validate_allocations(cls, allocations: List[InterimPaymentAllocationCreate], info):
        """Validate that allocations don't exceed total amount"""
        # Get total_amount from the model being validated
        if hasattr(info.data, 'total_amount'):
            total_amount = info.data['total_amount']
            allocated_sum = sum(a.allocated_amount for a in allocations)
            
            if allocated_sum > total_amount:
                raise ValueError(
                    f"Total allocated amount ({allocated_sum}) exceeds payment amount ({total_amount})"
                )
        
        return allocations


class InterimPaymentUpdate(BaseModel):
    """Schema for updating interim payment"""
    status: Optional[PaymentStatus] = None
    notes: Optional[str] = Field(None, max_length=512)
    
    model_config = ConfigDict(from_attributes=True)


class InterimPaymentResponse(InterimPaymentBase):
    """Schema for payment response"""
    id: int
    payment_id: str
    allocated_amount: Decimal
    unallocated_amount: Decimal
    status: str
    receipt_number: str
    receipt_issued_at: datetime
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None
    created_by: Optional[int] = None
    modified_by: Optional[int] = None
    
    # Include allocations in response
    allocations: List[InterimPaymentAllocationResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


class InterimPaymentSummaryResponse(BaseModel):
    """Schema for payment summary (list views)"""
    id: int
    payment_id: str
    driver_id: int
    driver_name: Optional[str] = None
    medallion_number: Optional[str] = None
    payment_date: date
    total_amount: Decimal
    payment_method: str
    status: str
    receipt_number: str
    
    model_config = ConfigDict(from_attributes=True)


# === Filter Schemas ===

class InterimPaymentFilters(BaseModel):
    """Filters for querying interim payments"""
    driver_id: Optional[int] = None
    medallion_id: Optional[int] = None
    lease_id: Optional[int] = None
    payment_date_from: Optional[date] = None
    payment_date_to: Optional[date] = None
    payment_method: Optional[PaymentMethod] = None
    status: Optional[PaymentStatus] = None
    receipt_number: Optional[str] = None
    payment_id: Optional[str] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=100)
    sort_by: str = Field(default="payment_date")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class InterimPaymentAllocationFilters(BaseModel):
    """Filters for querying allocations"""
    payment_id: Optional[int] = None
    category: Optional[AllocationCategory] = None
    reference_id: Optional[str] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=50, ge=1, le=100)
    sort_by: str = Field(default="created_on")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$")


class PaginatedInterimPaymentResponse(BaseModel):
    """Paginated response for interim payments"""
    items: List[InterimPaymentSummaryResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    payment_methods: List[str] = ["Cash", "Check", "ACH"]
    statuses: List[str] = ["Completed", "Voided", "Reversed"]


class PaginatedAllocationResponse(BaseModel):
    """Paginated response for allocations"""
    items: List[InterimPaymentAllocationResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    categories: List[str] = ["Lease", "Repair", "Loan", "EZPass", "PVB", "Misc"]


# === Operation Result Schemas ===

class InterimPaymentCreationResult(BaseModel):
    """Result schema for payment creation"""
    success: bool
    payment_id: str
    message: str
    payment: Optional[InterimPaymentResponse] = None
    receipt_number: str
    error: Optional[str] = None


class AllocationResult(BaseModel):
    """Result for individual allocation"""
    category: str
    reference_id: str
    allocated_amount: Decimal
    outstanding_before: Decimal
    outstanding_after: Decimal
    ledger_posting_ref: Optional[str] = None


class PaymentProcessingResult(BaseModel):
    """Result schema for payment processing"""
    success: bool
    total_allocations: int
    successful_allocations: int
    failed_allocations: int
    message: str
    allocation_details: List[AllocationResult] = []
    errors: Optional[List[str]] = None


# === Log Schemas ===

class InterimPaymentLogBase(BaseModel):
    """Base schema for payment log"""
    log_date: datetime
    log_type: LogType
    payment_id: Optional[int] = None
    records_impacted: int = Field(default=0)
    status: LogStatus = LogStatus.SUCCESS
    details: Optional[str] = Field(None, max_length=1024)
    error_message: Optional[str] = Field(None, max_length=512)


class InterimPaymentLogCreate(InterimPaymentLogBase):
    """Schema for creating log entry"""
    pass


class InterimPaymentLogResponse(InterimPaymentLogBase):
    """Schema for log response"""
    id: int
    created_on: Optional[datetime] = None
    created_by: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class PaginatedLogResponse(BaseModel):
    """Paginated response for logs"""
    items: List[InterimPaymentLogResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    log_types: List[str] = ["Create", "Allocate", "Void", "Reverse"]
    statuses: List[str] = ["Success", "Failure", "Partial"]


# === UI Workflow Schemas ===

class ObligationItem(BaseModel):
    """Single obligation item for allocation UI"""
    category: AllocationCategory
    reference_id: str
    description: str
    outstanding_amount: Decimal
    due_date: Optional[date] = None
    age_days: Optional[int] = None


class ObligationListResponse(BaseModel):
    """Response with all outstanding obligations for a medallion/lease"""
    driver_id: int
    driver_name: str
    medallion_id: int
    medallion_number: str
    lease_id: Optional[int] = None
    obligations: List[ObligationItem]
    total_outstanding: Decimal


class AllocationRequest(BaseModel):
    """Request to allocate payment to obligations"""
    category: AllocationCategory
    reference_id: str
    amount: Decimal = Field(..., gt=0, decimal_places=2)


class PaymentAllocationRequest(BaseModel):
    """Complete payment allocation request"""
    driver_id: int
    medallion_id: int
    lease_id: Optional[int] = None
    payment_date: date
    total_amount: Decimal = Field(..., gt=0, decimal_places=2)
    payment_method: PaymentMethod
    check_number: Optional[str] = None
    notes: Optional[str] = None
    allocations: List[AllocationRequest]
    
    @field_validator('allocations')
    @classmethod
    def validate_total_allocation(cls, allocations: List[AllocationRequest], info):
        """Ensure allocations don't exceed payment amount"""
        if hasattr(info.data, 'total_amount'):
            total_amount = info.data['total_amount']
            allocated_sum = sum(a.amount for a in allocations)
            
            if allocated_sum > total_amount:
                raise ValueError(
                    f"Total allocated ({allocated_sum}) exceeds payment amount ({total_amount})"
                )
        
        return allocations


# === Receipt Schema ===

class ReceiptLineItem(BaseModel):
    """Single line item on receipt"""
    category: str
    reference_id: str
    description: str
    allocated_amount: Decimal
    balance_remaining: Decimal


class PaymentReceiptResponse(BaseModel):
    """Complete payment receipt"""
    receipt_number: str
    payment_id: str
    driver_name: str
    driver_tlc_license: Optional[str] = None
    medallion_number: str
    lease_id: Optional[str] = None
    payment_date: date
    payment_method: str
    check_number: Optional[str] = None
    total_amount: Decimal
    line_items: List[ReceiptLineItem]
    auto_allocated_to_lease: Optional[Decimal] = None
    issued_at: datetime
    issued_by: Optional[str] = None


# Update forward references
InterimPaymentResponse.model_rebuild()
PaginatedInterimPaymentResponse.model_rebuild()