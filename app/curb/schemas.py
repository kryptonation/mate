# app/curb/schemas.py

"""
Pydantic schemas for CURB module
"""

from datetime import datetime, date, time
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


# === CURB Trip Schemas ===

class CURBTripBase(BaseModel):
    """Base schema for CURB Trip."""
    record_id: str
    period: Optional[str] = None
    trip_number: Optional[str] = None
    cab_number: str
    driver_id: str
    
    start_date: date
    end_date: date
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    
    trip_amount: float = 0.0
    tips: float = 0.0
    extras: float = 0.0
    tolls: float = 0.0
    tax: float = 0.0
    imp_tax: float = 0.0
    total_amount: float = 0.0
    
    gps_start_lat: Optional[float] = None
    gps_start_lon: Optional[float] = None
    gps_end_lat: Optional[float] = None
    gps_end_lon: Optional[float] = None
    
    from_address: Optional[str] = None
    to_address: Optional[str] = None
    
    payment_type: str  # T=Cash, P=Private, C=Credit Card
    cc_number: Optional[str] = None
    auth_code: Optional[str] = None
    auth_amount: float = 0.0
    
    ehail_fee: float = 0.0
    health_fee: float = 0.0
    congestion_fee: float = 0.0
    airport_fee: float = 0.0
    cbdt_fee: float = 0.0
    
    passengers: int = 1
    distance_service: float = 0.0
    distance_bs: float = 0.0
    reservation_number: Optional[str] = None
    
    status: str = "Imported"


class CURBTripCreate(CURBTripBase):
    """Schema for creating CURB Trip."""
    import_id: Optional[int] = None


class CURBTripUpdate(BaseModel):
    """Schema for updating CURB Trip."""
    status: Optional[str] = None
    is_reconciled: Optional[bool] = None
    is_posted: Optional[bool] = None
    recon_stat: Optional[int] = None
    driver_fk: Optional[int] = None
    medallion_fk: Optional[int] = None
    vehicle_fk: Optional[int] = None
    associate_failed_reason: Optional[str] = None
    post_failed_reason: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class CURBTripResponse(CURBTripBase):
    """Schema for CURB Trip Response."""
    id: int
    is_reconciled: bool
    is_posted: bool
    recon_stat: Optional[int] = None
    import_id: Optional[int] = None
    driver_fk: Optional[int] = None
    medallion_fk: Optional[int] = None
    vehicle_fk: Optional[int] = None
    associate_failed_reason: Optional[str] = None
    post_failed_reason: Optional[str] = None
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None
    created_by: Optional[int] = None
    modified_by: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class PaginatedCURBTripResponse(BaseModel):
    """Paginated response for CURB Trips."""
    items: List[CURBTripResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    statuses: List[str] = ["Imported", "Associated", "Posted", "Failed"]
    payment_types: List[str] = ["T", "P", "C"]


# === CURB Import Log Schemas ===

class CURBImportLogBase(BaseModel):
    """Base schema for CURB Import Log."""
    import_source: str
    imported_by: str = "SYSTEM"
    total_records: int = 0
    success_count: int = 0
    failure_count: int = 0
    duplicate_count: int = 0
    status: str = "IN_PROGRESS"


class CURBImportLogCreate(CURBImportLogBase):
    """Schema for creating CURB Import Log."""
    pass


class CURBImportLogUpdate(BaseModel):
    """Schema for updating CURB Import Log."""
    import_end: Optional[datetime] = None
    total_records: Optional[int] = None
    success_count: Optional[int] = None
    failure_count: Optional[int] = None
    duplicate_count: Optional[int] = None
    status: Optional[str] = None
    error_summary: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class CURBImportLogResponse(CURBImportLogBase):
    """Schema for CURB Import Log Response."""
    id: int
    import_start: datetime
    import_end: Optional[datetime] = None
    error_summary: Optional[str] = None
    created_on: Optional[datetime] = None
    updated_on: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class PaginatedCURBImportLogResponse(BaseModel):
    """Paginated response for CURB Import Logs."""
    items: List[CURBImportLogResponse]
    total_items: int
    page: int
    per_page: int
    total_pages: int
    statuses: List[str] = ["IN_PROGRESS", "COMPLETED", "FAILED", "PARTIAL"]


# === CURB Trip Reconciliation Schemas ===

class CURBTripReconciliationCreate(BaseModel):
    """Schema for creating CURB Trip Reconciliation."""
    trip_id: int
    recon_stat: int
    reconciled_by: str = "SYSTEM"
    reconciliation_type: str = "LOCAL"


class CURBTripReconciliationResponse(BaseModel):
    """Schema for CURB Trip Reconciliation Response."""
    id: int
    trip_id: int
    recon_stat: int
    reconciled_at: datetime
    reconciled_by: str
    reconciliation_type: str
    
    model_config = ConfigDict(from_attributes=True)


# === Operation Result Schemas ===

class CURBImportResult(BaseModel):
    """Schema for import operation result."""
    success: bool
    log_id: int
    total_records: int
    success_count: int
    duplicate_count: int
    failure_count: int
    message: str
    failed_rows: Optional[dict] = None


class CURBReconciliationResult(BaseModel):
    """Schema for reconciliation operation result."""
    success: bool
    total_processed: int
    reconciled_count: int
    already_reconciled_count: int
    failed_count: int
    recon_stat: int
    message: str
    details: Optional[List[dict]] = None


class CURBAssociationResult(BaseModel):
    """Schema for association operation result."""
    success: bool
    total_processed: int
    associated_count: int
    failed_count: int
    message: str
    details: Optional[List[dict]] = None


class CURBPostingResult(BaseModel):
    """Schema for posting operation result."""
    success: bool
    total_processed: int
    posted_count: int
    failed_count: int
    skipped_count: int
    message: str
    details: Optional[List[dict]] = None


# === Filter Schemas ===

class CURBTripFilters(BaseModel):
    """Filters for CURB Trip queries."""
    trip_id: Optional[int] = None
    record_id: Optional[str] = None
    period: Optional[str] = None
    driver_id: Optional[str] = None
    cab_number: Optional[str] = None
    start_date_from: Optional[date] = None
    start_date_to: Optional[date] = None
    end_date_from: Optional[date] = None
    end_date_to: Optional[date] = None
    payment_type: Optional[str] = None
    is_reconciled: Optional[bool] = None
    is_posted: Optional[bool] = None
    status: Optional[str] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    sort_by: str = "updated_on"
    sort_order: str = "desc"


class CURBImportLogFilters(BaseModel):
    """Filters for CURB Import Log queries."""
    log_id: Optional[int] = None
    import_source: Optional[str] = None
    imported_by: Optional[str] = None
    import_start_from: Optional[datetime] = None
    import_start_to: Optional[datetime] = None
    status: Optional[str] = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=10, ge=1, le=100)
    sort_by: str = "import_start"
    sort_order: str = "desc"


# === SOAP Request/Response Schemas ===

class CURBFetchTripsRequest(BaseModel):
    """Schema for fetching trips from CURB SOAP API."""
    from_date: str  # MM/DD/YYYY
    to_date: str    # MM/DD/YYYY
    driver_id: Optional[str] = ""
    cab_number: Optional[str] = ""
    recon_stat: int = -1  # -1 = all, 0 = unreconciled, >0 = specific receipt number


class CURBReconcileTripsRequest(BaseModel):
    """Schema for reconciling trips with CURB SOAP API."""
    trip_ids: List[int]
    recon_stat: int  # Receipt number


class CURBManualProcessRequest(BaseModel):
    """Schema for manual trip processing."""
    from_date: date
    to_date: date
    driver_id: Optional[str] = None
    import_by: str = "MANUAL"