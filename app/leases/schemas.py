# app/leases/schemas.py

from datetime import datetime
from enum import Enum as PyEnum
from typing import Literal, Optional

from pydantic import BaseModel


class LeaseStatus(str, PyEnum):
    """All the lease statuses in the system"""

    IN_PROGRESS = "In Progress"
    ACTIVE = "Active"
    INACTIVE = "Inactive"
    TERMINATED = "Terminated"


class LongTermFinancialInfo(BaseModel):
    """
    Financial information for a long term lease
    """

    management_recommendation: Optional[float] = 0
    day_shift: Optional[float] = 0
    day_tlc_maximum_amount: Optional[float] = 0
    night_shift: Optional[float] = 0
    night_tlc_maximum_amount: Optional[float] = 0
    lease_amount: Optional[float] = 0


class LongTermLease(BaseModel):
    """
    Long term lease schema
    """

    leaseType: str
    financialInformation: LongTermFinancialInfo


class ShortTermDayNight(BaseModel):
    """
    Day and night shift financial information for a short term lease
    """

    day_shift: Optional[float] = 0
    night_shift: Optional[float] = 0


class ShortTermLease(BaseModel):
    """
    Short term lease schema
    """

    leaseType: Literal["short-term"]
    financialInformation: Optional[dict] = {
        "1_week_or_longer": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "1_week_or_longer_tlc_maximum_amount": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "sun": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "sun_tlc_maximum_amount": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "mon": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "mon_tlc_maximum_amount": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "tus": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "tus_tlc_maximum_amount": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "wen": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "wen_tlc_maximum_amount": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "thu": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "thu_tlc_maximum_amount": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "fri": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "fri_tlc_maximum_amount": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "sat": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
        "sat_tlc_maximum_amount": {
            "day_shift": Optional[float],
            "night_shift": Optional[float],
        },
    }


class MedallionOnlyFinancialInfo(BaseModel):
    """
    Financial information for a medallion only lease
    """

    weekly_lease_rate: Optional[float] = 0
    week_tlc_maximum_amount: Optional[float] = 0


class MedallionOnlyLease(BaseModel):
    """
    Medallion only lease schema
    """

    leaseType: str
    financialInformation: MedallionOnlyFinancialInfo


class LeasePresetBase(BaseModel):
    """
    Base schema for lease presets with all common fields
    """

    lease_type: str
    vehicle_year: int
    vehicle_make: str
    vehicle_model: str
    weekly_rate: float


class LeasePresetCreate(LeasePresetBase):
    """
    Schema for creating a new lease preset.
    """

    pass


class LeasePresetUpdate(BaseModel):
    """
    Schema for updating an existing lease preset. All fields are optional.
    """

    lease_type: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    weekly_rate: Optional[float] = None


class LeasePresetResponse(LeasePresetBase):
    """Schema for returning a lease preset, including its ID and audit fields."""

    id: int
    created_on: datetime
    updated_on: Optional[datetime] = None

    class Config:
        """Pydantic configuration"""

        from_attributes = True
