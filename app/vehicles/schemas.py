### app/vehicles/schemas.py

# Standard library imports
from datetime import datetime , date
from enum import Enum as PyEnum
from typing import Any, Optional

from pydantic import BaseModel, root_validator


class VehicleStatus(str, PyEnum):
    """All the vehicle statuses in the system"""

    IN_PROGRESS = "In Progress"
    AVAILABLE = "Available"
    HACK_UP_IN_PROGRESS = "Hack-up In Progress"
    HACKED_UP = "Hacked up"
    ACTIVE = "Active"
    ARCHIVED = "Archived"
    DELIVERED = "Delivered"
    NOT_DELIVERED = "Not Delivered"
    DE_HACK_UP_IN_PROGRESS = "De Hack-up In Progress"


class HackupStatus(str, PyEnum):
    """All the vehicle hackup statuses in the system"""

    ACTIVE = "Active"
    INACTIVE = "Inactive"
    INPROGRESS = "In Progress"

class VehicleEntityStatus(str , PyEnum):
    ACTIVE = "Active"
    INACTIVE = "Inactive"

class RegistrationStatus(str, PyEnum):
    """All the vehicle registration statuses in the system"""

    ACTIVE = "active"
    INACTIVE = "inactive"


class NEWVR(str, PyEnum):
    """New vehicle document types"""

    VEHICLE_TYPE = "vehicle_type"
    DOCUMENT_2 = "document2"
    DOCUMENT_3 = "document3"


class HackUpData(BaseModel):
    tpep_provider: Optional[str] = None
    configuration_type: Optional[str] = None

    is_paint_completed: Optional[bool] = None
    paint_completed_date: Optional[datetime] = None
    paint_completed_charges: Optional[float] = None
    paint_status: Optional[str] = None
    paint_from_location: Optional[str] = None
    paint_to_location: Optional[str] = None

    is_camera_installed: Optional[bool] = None
    camera_type: Optional[str] = None
    camera_installed_date: Optional[datetime] = None
    camera_installed_charges: Optional[float] = None
    camera_status: Optional[str] = None
    camera_from_location: Optional[str] = None
    camera_to_location: Optional[str] = None

    is_partition_installed: Optional[bool] = None
    partition_type: Optional[str] = None
    partition_installed_date: Optional[datetime] = None
    partition_installed_charges: Optional[float] = None
    partition_status: Optional[str] = None
    partition_from_location: Optional[str] = None
    partition_to_location: Optional[str] = None

    is_meter_installed: Optional[bool] = None
    meter_type: Optional[str] = None
    meter_serial_number: Optional[str] = None
    meter_installed_charges: Optional[float] = None
    meter_installed_date: Optional[datetime] = None
    meter_status: Optional[str] = None
    meter_from_location: Optional[str] = None
    meter_to_location: Optional[str] = None

    is_rooftop_installed: Optional[bool] = None
    rooftop_type: Optional[str] = None
    rooftop_installed_date: Optional[datetime] = None
    rooftop_installation_charges: Optional[float] = None
    rooftop_status: Optional[str] = None
    rooftop_from_location: Optional[str] = None
    rooftop_to_location: Optional[str] = None

    @root_validator(pre=True)
    def convert_empty_to_none(cls, values):
        for field, value in values.items():
            if value in [0, "", []]:
                values[field] = None
        return values


class NewDealer(BaseModel):
    dealer_name: Optional[str] = None
    dealer_bank_name: Optional[str] = None
    dealer_bank_account_number: Optional[str] = None


class ProcessTypeEnum(str, PyEnum):
    paint = "Paint"
    meter = "Meter"
    rooftop = "Rooftop"
    camera = "Camera"
    partition = "Partition"


class ProcessStatusEnum(str, PyEnum):
    open = "open"
    initial = "initial"
    in_progress = "in_progress"
    verify = "verify"
    completed = "completed"
    empty = ""


class HackupProcessStatus(BaseModel):
    process_type: ProcessTypeEnum
    location: Optional[str] = None
    status: ProcessStatusEnum

class DeliveryData(BaseModel):
    is_delivered: Optional[bool] = None
    expected_delivery_date: Optional[date] = None
    delivery_location: Optional[str] = None
    delivery_note: Optional[str] = None
    vehicle_status: VehicleStatus = VehicleStatus.AVAILABLE
