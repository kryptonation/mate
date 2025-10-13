# app/ezpass/schemas.py

"""
Pydantic schemas for EZPass module
Enhanced to match CSV format
"""

from datetime import datetime, date, time
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# === EZPass Transaction schemas ===

class EZPassTransactionBase(BaseModel):
    """Base schema for EZPass Transaction."""
    transaction_id: Optional[int] = None
    transaction_date: date
    transaction_time: Optional[time] = None
    posting_date: Optional[date] = None
    medallion_no: Optional[str] = None
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    plate_no: Optional[str] = None
    tag_or_plate: str
    agency: Optional[str] = None
    entry_plaza: Optional[str] = None
    exit_plaza: Optional[str] = None
    vehicle_class: Optional[str] = None
    amount: float = 0.0
    status: str = "Imported"
    associate_failed_reason: Optional[str] = None
    post_failed_reason: Optional[str] = None


class EZPassTransactionCreate(EZPassTransactionBase):
    """Schema for creating EZPass Transaction."""
    log_id: Optional[int] = None


class EZPassTransactionUpdate(BaseModel):
    """Schema for updating EZPass Transaction."""
    transaction_id: Optional[str] = None
    transaction_date: Optional[date] = None
    transaction_time: Optional[time] = None
    posting_date: Optional[date] = None
    medallion_no: Optional[str] = None
    driver_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    plate_no: Optional[str] = None
    tag_or_plate: Optional[str] = None
    agency: Optional[str] = None
    entry_plaza: Optional[str] = None
    exit_plaza: Optional[str] = None
    vehicle_class: Optional[str] = None
    amount: Optional[float] = None
    status: Optional[str] = None
    associate_failed_reason: Optional[str] = None
    post_failed_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class EZPassTransactionResponse(EZPassTransactionBase):
    """Schema for EZPass Transaction Response."""
    id: int
    log_id: Optional[int] = None
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None
    created_by: Optional[int] = None
    modified_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedEZPassTransactionResponse(BaseModel):
    """Paginated response for EZPass Transactions."""
    items: List[EZPassTransactionResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    statuses: List[str] = ["Imported", "Associated", "Posted", "Failed"]


# === EZPass Log Schemas ===

class EZPassLogBase(BaseModel):
    """Base schema for EZPass Log."""
    log_date: datetime
    log_type: str
    records_impacted: Optional[int] = None
    success_count: Optional[int] = None
    unidentified_count: Optional[int] = None
    status: str = "Imported"


class EZPassLogCreate(EZPassLogBase):
    """Schema for creating EZPass Log."""
    pass


class EZPassLogResponse(EZPassLogBase):
    """Schema for EZPass Log response."""
    id: int
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None
    created_by: Optional[int] = None
    modified_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedEZPassLogResponse(BaseModel):
    """Paginated response for EZPass Logs."""
    items: List[EZPassLogResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    statuses: List[str] = ["Success", "Failure", "Partial"]
    types: List[str] = ["Import", "Associate", "Post"]


# === Operation Result Schemas ===

class EZPassImportResult(BaseModel):
    """Schema for import operation result."""
    success: bool
    log_id: int
    records_impacted: int
    success_count: int
    unidentified_count: int
    message: str


class EZPassAssociationResult(BaseModel):
    """Schema for association operation result."""
    success: bool
    total_processed: int
    associated_count: int
    failed_count: int
    message: str
    details: Optional[List[dict]] = None


class EZPassPostingResult(BaseModel):
    """Schema for posting operation result."""
    success: bool
    total_processed: int
    posted_count: int
    failed_count: int
    message: str
    details: Optional[List[dict]] = None


# === Filter Schemas ===

class EZPassTransactionFilters(BaseModel):
    """Filters for EZPass Transaction queries."""
    transaction_id: Optional[int] = None
    transaction_from_date: Optional[datetime] = None
    transaction_to_date: Optional[datetime] = None
    medallion_no: Optional[str] = None
    driver_id: Optional[str] = None
    plate_no: Optional[str] = None
    posting_from_date: Optional[datetime] = None
    posting_to_date: Optional[datetime] = None
    transaction_status: Optional[str] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    sort_by: str = "updated_on"
    sort_order: str = "desc"


class EZPassLogFilters(BaseModel):
    """Filters for EZPass Log queries."""
    log_id: Optional[int] = None
    log_from_date: Optional[datetime] = None
    log_to_date: Optional[datetime] = None
    log_status: Optional[str] = None
    log_type: Optional[str] = None
    records_impacted: Optional[int] = None
    success_count: Optional[int] = None
    unidentified_count: Optional[int] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    sort_by: str = "log_date"
    sort_order: str = "desc"


# === Bulk Operation Schemas ===

class BulkAssociateRequest(BaseModel):
    """Request for bulk association."""
    transaction_ids: Optional[List[int]] = None
    force_reassociate: bool = False


class BulkPostRequest(BaseModel):
    """Request for bulk posting."""
    transaction_ids: Optional[List[int]] = None
    force_repost: bool = False



