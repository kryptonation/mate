# app/repairs/schemas.py

"""
Pydantic schemas for Vehicle Repairs module
"""

from datetime import datetime, date
from typing import Optional, List
from enum import Enum as PyEnum

from pydantic import BaseModel, Field, ConfigDict, field_validator


# === Enums ===

class WorkshopType(str, PyEnum):
    """Workshop type enum."""
    BIG_APPLE = "Big Apple Workshop"
    EXTERNAL = "External Workshop"


class InvoiceStatus(str, PyEnum):
    """Invoice status enum."""
    DRAFT = "Draft"
    OPEN = "Open"
    CLOSED = "Closed"
    HOLD = "Hold"
    CANCELLED = "Cancelled"


class InstallmentStatus(str, PyEnum):
    """Installment status enum."""
    SCHEDULED = "Scheduled"
    DUE = "Due"
    POSTED = "Posted"
    PAID = "Paid"


class StartWeekOption(str, PyEnum):
    """Start week option enum."""
    CURRENT = "Current Payment Period"
    NEXT = "Next Payment Period"


# === Repair Invoice Schemas ===

class RepairInvoiceBase(BaseModel):
    """Base schema for Repair Invoice."""
    invoice_number: str = Field(..., max_length=100)
    invoice_date: date
    vin: str = Field(..., max_length=17)
    plate_number: str = Field(..., max_length=20)
    medallion_number: str = Field(..., max_length=20)
    hack_license_number: Optional[str] = Field(None, max_length=20)
    workshop_type: WorkshopType
    repair_description: Optional[str] = Field(None, max_length=500)
    repair_amount: float = Field(..., gt=0)
    start_week: StartWeekOption = StartWeekOption.CURRENT


class RepairInvoiceCreate(RepairInvoiceBase):
    """Schema for creating Repair Invoice."""
    driver_id: Optional[int] = None
    vehicle_id: int
    medallion_id: int
    lease_id: Optional[int] = None

    @field_validator('repair_amount')
    @classmethod
    def validate_repair_amount(cls, v: float) -> float:
        if v < 1:
            raise ValueError('Repair amount must be at least $1')
        return v


class RepairInvoiceUpdate(BaseModel):
    """Schema for updating Repair Invoice."""
    invoice_number: Optional[str] = Field(None, max_length=100)
    invoice_date: Optional[date] = None
    repair_description: Optional[str] = Field(None, max_length=500)
    repair_amount: Optional[float] = Field(None, gt=0)
    status: Optional[InvoiceStatus] = None
    start_week: Optional[StartWeekOption] = None

    model_config = ConfigDict(from_attributes=True)


class RepairInvoiceResponse(RepairInvoiceBase):
    """Schema for Repair Invoice Response."""
    id: int
    repair_id: str
    driver_id: Optional[int] = None
    vehicle_id: int
    medallion_id: int
    lease_id: Optional[int] = None
    status: InvoiceStatus
    weekly_installment: float
    balance: float
    created_on: datetime
    updated_on: datetime
    created_by: Optional[int] = None
    modified_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedRepairInvoiceResponse(BaseModel):
    """Paginated response for Repair Invoices."""
    items: List[RepairInvoiceResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    statuses: List[str] = ["Draft", "Open", "Closed", "Hold", "Cancelled"]


# === Repair Installment Schemas ===

class RepairInstallmentBase(BaseModel):
    """Base schema for Repair Installment."""
    installment_id: str = Field(..., max_length=50)
    week_start_date: date
    week_end_date: date
    payment_amount: float = Field(..., ge=0)
    prior_balance: float = Field(default=0, ge=0)
    balance: float = Field(..., ge=0)


class RepairInstallmentCreate(RepairInstallmentBase):
    """Schema for creating Repair Installment."""
    repair_invoice_id: int
    status: InstallmentStatus = InstallmentStatus.SCHEDULED


class RepairInstallmentUpdate(BaseModel):
    """Schema for updating Repair Installment."""
    status: Optional[InstallmentStatus] = None
    ledger_posting_ref: Optional[str] = Field(None, max_length=100)
    payment_amount: Optional[float] = Field(None, ge=0)
    balance: Optional[float] = Field(None, ge=0)

    model_config = ConfigDict(from_attributes=True)


class RepairInstallmentResponse(RepairInstallmentBase):
    """Schema for Repair Installment Response."""
    id: int
    repair_invoice_id: int
    status: InstallmentStatus
    ledger_posting_ref: Optional[str] = None
    created_on: datetime
    updated_on: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedRepairInstallmentResponse(BaseModel):
    """Paginated response for Repair Installments."""
    items: List[RepairInstallmentResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int


# === Filter Schemas ===

class RepairInvoiceFilters(BaseModel):
    """Filters for Repair Invoice queries."""
    status: Optional[InvoiceStatus] = None
    workshop_type: Optional[WorkshopType] = None
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    medallion_id: Optional[int] = None
    invoice_number: Optional[str] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None


class RepairInstallmentFilters(BaseModel):
    """Filters for Repair Installment queries."""
    repair_invoice_id: Optional[int] = None
    status: Optional[InstallmentStatus] = None
    week_start_date: Optional[date] = None
    week_end_date: Optional[date] = None


# === Operation Result Schemas ===

class RepairImportResult(BaseModel):
    """Schema for import operation result."""
    success: bool
    invoice_id: int
    repair_id: str
    installments_created: int
    total_amount: float
    weekly_installment: float
    message: str


class RepairPostingResult(BaseModel):
    """Schema for posting operation result."""
    success: bool
    total_processed: int
    posted_count: int
    failed_count: int
    message: str
    details: Optional[List[dict]] = None


class RepairScheduleResponse(BaseModel):
    """Schema for displaying payment schedule."""
    repair_id: str
    invoice_number: str
    total_amount: float
    weekly_installment: float
    installments: List[RepairInstallmentResponse]
    remaining_balance: float
    next_payment_date: Optional[date] = None


# === OCR Result Schema ===

class RepairInvoiceOCRResult(BaseModel):
    """Schema for OCR extraction result."""
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None
    repair_amount: Optional[float] = None
    vendor_name: Optional[str] = None
    confidence_score: float = 0.0
    raw_text: Optional[str] = None