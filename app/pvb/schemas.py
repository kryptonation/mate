# app/pvb/schemas.py

"""
Pydantic schemas for PVB (Parking Violations Bureau) module
"""

from datetime import datetime, date
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# === PVB Violation Schemas ===

class PVBViolationBase(BaseModel):
    """Base schema for PVB Violation."""
    plate_number: str = Field(..., max_length=64)
    state: str = Field(..., max_length=2)
    vehicle_type: Optional[str] = Field(None, max_length=24)
    summons_number: Optional[str] = Field(None, max_length=32)
    issue_date: date
    issue_time: Optional[str] = Field(None, max_length=16)
    amount_due: Optional[int] = None
    amount_paid: Optional[int] = Field(default=0)
    status: str = Field(default="Imported", max_length=50)
    associated_failed_reason: Optional[str] = None
    post_failed_reason: Optional[str] = None


class PVBViolationCreate(PVBViolationBase):
    """Schema for creating PVB Violation."""
    driver_id: Optional[int] = None
    medallion_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    log_id: Optional[int] = None


class PVBViolationUpdate(BaseModel):
    """Schema for updating PVB Violation."""
    plate_number: Optional[str] = Field(None, max_length=64)
    state: Optional[str] = Field(None, max_length=2)
    vehicle_type: Optional[str] = Field(None, max_length=24)
    summons_number: Optional[str] = Field(None, max_length=32)
    issue_date: Optional[date] = None
    issue_time: Optional[str] = Field(None, max_length=16)
    amount_due: Optional[int] = None
    amount_paid: Optional[int] = None
    driver_id: Optional[int] = None
    medallion_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    status: Optional[str] = Field(None, max_length=50)
    associated_failed_reason: Optional[str] = None
    post_failed_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PVBViolationResponse(PVBViolationBase):
    """Schema for PVB Violation Response."""
    id: int
    driver_id: Optional[int] = None
    medallion_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    log_id: Optional[int] = None
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None
    created_by: Optional[int] = None
    modified_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedPVBViolationResponse(BaseModel):
    """Paginated response for PVB Violations."""
    items: List[PVBViolationResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    statuses: List[str] = ["Imported", "Associated", "Posted", "Failed", "Pending"]


# === PVB Log Schemas ===

class PVBLogBase(BaseModel):
    """Base schema for PVB Log."""
    log_date: datetime
    log_type: str = Field(..., max_length=50)
    records_impacted: Optional[int] = None
    success_count: Optional[int] = Field(default=0)
    unidentified_count: Optional[int] = Field(default=0)
    status: str = Field(default="Pending", max_length=50)


class PVBLogCreate(PVBLogBase):
    """Schema for creating PVB Log."""
    pass


class PVBLogUpdate(BaseModel):
    """Schema for updating PVB Log."""
    log_type: Optional[str] = Field(None, max_length=50)
    records_impacted: Optional[int] = None
    success_count: Optional[int] = None
    unidentified_count: Optional[int] = None
    status: Optional[str] = Field(None, max_length=50)

    model_config = ConfigDict(from_attributes=True)


class PVBLogResponse(PVBLogBase):
    """Schema for PVB Log Response."""
    id: int
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None
    created_by: Optional[int] = None
    modified_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class PaginatedPVBLogResponse(BaseModel):
    """Paginated response for PVB Logs."""
    items: List[PVBLogResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    statuses: List[str] = ["Pending", "Success", "Failure", "Partial"]
    types: List[str] = ["Import", "Associate", "Post"]


# === Operation Result Schemas ===

class PVBImportResult(BaseModel):
    """Schema for import operation result."""
    success: bool
    log_id: int
    records_impacted: int
    success_count: int
    unidentified_count: int
    message: str
    failed_rows: Optional[dict] = None


class PVBAssociationResult(BaseModel):
    """Schema for association operation result."""
    success: bool
    total_processed: int
    associated_count: int
    failed_count: int
    message: str
    details: Optional[List[dict]] = None


class PVBPostingResult(BaseModel):
    """Schema for posting operation result."""
    success: bool
    total_processed: int
    posted_count: int
    failed_count: int
    message: str
    details: Optional[List[dict]] = None


# === Filter Schemas ===

class PVBViolationFilters(BaseModel):
    """Filters for PVB Violation queries."""
    violation_id: Optional[int] = None
    plate_number: Optional[str] = None
    summons_number: Optional[str] = None
    state: Optional[str] = None
    vehicle_type: Optional[str] = None
    record_status: Optional[str] = None
    vehicle_id: Optional[str] = None
    driver_id: Optional[str] = None
    medallion_id: Optional[str] = None
    issue_from_date: Optional[date] = None
    issue_to_date: Optional[date] = None
    issue_time_from: Optional[str] = None
    issue_time_to: Optional[str] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=10000)
    sort_by: str = "updated_on"
    sort_order: str = "desc"


class PVBLogFilters(BaseModel):
    """Filters for PVB Log queries."""
    log_id: Optional[int] = None
    log_from_date: Optional[datetime] = None
    log_to_date: Optional[datetime] = None
    log_type: Optional[str] = None
    log_status: Optional[str] = None
    records_impacted: Optional[int] = None
    success_count: Optional[int] = None
    unidentified_count: Optional[int] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    sort_by: str = "log_date"
    sort_order: str = "desc"