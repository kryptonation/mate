# app/leases/services.py

import os
import tempfile
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple, Union

from sqlalchemy import asc, delete, desc, func, or_, select
from sqlalchemy.orm import Session

from app.drivers.models import Driver
from app.drivers.schemas import DOVLease
from app.drivers.services import driver_service
from app.esign.esign_client import ESignClient
from app.leases.models import (
    Lease,
    LeaseConfiguration,
    LeaseDriver,
    LeaseDriverDocument,
    LeasePaymentConfiguration,
    LeasePreset,
)
from app.leases.schemas import (
    LeasePresetCreate,
    LeasePresetUpdate,
    LeaseStatus,
    LongTermLease,
    MedallionOnlyLease,
    ShortTermLease,
)
from app.medallions.models import Medallion
from app.uploads.models import Document
from app.utils.logger import get_logger
from app.utils.s3_utils import s3_utils
from app.vehicles.models import Vehicle, VehicleRegistration
from app.vehicles.schemas import VehicleStatus

logger = get_logger(__name__)


class LeaseService:
    """Service for managing lease operations"""

    def get_lease(
        self,
        db: Session,
        page=None,
        per_page=None,
        lookup_id: Optional[int] = None,
        lease_id: Optional[str] = None,
        is_lease_list: Optional[bool] = None,
        lease_type: Optional[str] = None,
        medallion_number: Optional[int] = None,
        vin_number: Optional[str] = None,
        plate_number: Optional[str] = None,
        driver_id: Optional[str] = None,
        driver_name: Optional[str] = None,
        vehicle_id: Optional[int] = None,
        lease_start_date: Optional[date] = None,
        lease_end_date: Optional[date] = None,
        status: Optional[str] = None,
        sort_by: Optional[str] = "created_on",
        sort_order: Optional[str] = "desc",
        multiple: bool = False,
    ) -> Union[Lease, List[Lease], None]:
        """Get a lease by ID, vehicle ID, or status"""
        try:
            query = db.query(Lease)
            joined_medallion = False
            joined_vehicle = False
            joined_vehicle_registration = False
            joined_lease_driver = False
            joined_driver = False

            if lookup_id:
                query = query.filter(Lease.id == lookup_id)
            if lease_id:
                lease_ids = [i.strip() for i in lease_id.split(",") if i.strip()]
                query = query.filter(
                    or_(*[Lease.lease_id.ilike(f"%{i}%") for i in lease_ids])
                )
            if is_lease_list == True:
                query = query.filter(Lease.lease_status != LeaseStatus.IN_PROGRESS)
            if lease_type:
                query = query.filter(Lease.lease_type == lease_type)

            if vehicle_id:
                query = query.filter(Lease.vehicle_id == vehicle_id)
            if medallion_number:
                medallion_numbers = [
                    i.strip() for i in medallion_number.split(",") if i.strip()
                ]
                if not joined_medallion:
                    query = query.join(Medallion, Lease.medallion_id == Medallion.id)
                    joined_medallion = True
                query = query.filter(
                    or_(
                        *[
                            Medallion.medallion_number.ilike(f"%{number}%")
                            for number in medallion_numbers
                        ]
                    )
                )
            if vin_number:
                vins = [i.strip() for i in vin_number.split(",") if i.strip()]
                if not joined_vehicle:
                    query = query.join(Vehicle, Lease.vehicle_id == Vehicle.id)
                    joined_vehicle = True
                query = query.filter(
                    or_(*[Vehicle.vin.ilike(f"%{vin}%") for vin in vins])
                )
            if plate_number:
                plate_numbers = [
                    i.strip() for i in plate_number.split(",") if i.strip()
                ]
                if not joined_vehicle:
                    query = query.join(Vehicle, Lease.vehicle_id == Vehicle.id)
                    joined_vehicle = True
                if not joined_vehicle_registration:
                    query = query.join(
                        VehicleRegistration,
                        Vehicle.id == VehicleRegistration.vehicle_id,
                    )
                    joined_vehicle_registration = True
                query = query.filter(
                    or_(
                        *[
                            VehicleRegistration.plate_number.ilike(f"%{plate}%")
                            for plate in plate_numbers
                        ]
                    )
                )

            if driver_id:
                driver_ids = [i.strip() for i in str(driver_id).split(",") if i.strip()]
                if not joined_lease_driver:
                    query = query.join(LeaseDriver, Lease.id == LeaseDriver.lease_id)
                    joined_lease_driver = True
                if not joined_driver:
                    query = query.join(
                        Driver, LeaseDriver.driver_id == Driver.driver_id
                    )
                    joined_driver = True
                query = query.filter(
                    or_(*[Driver.driver_id.ilike(f"%{id}%") for id in driver_ids])
                )

            if driver_name:
                driver_names = [i.strip() for i in driver_name.split(",") if i.strip()]
                if not joined_lease_driver:
                    query = query.join(LeaseDriver, Lease.id == LeaseDriver.lease_id)
                    joined_lease_driver = True
                if not joined_driver:
                    query = query.join(
                        Driver, LeaseDriver.driver_id == Driver.driver_id
                    )
                    joined_driver = True
                query = query.filter(
                    or_(
                        *[
                            (Driver.full_name.ilike(f"%{name}%"))
                            for name in driver_names
                        ]
                    )
                )
            if lease_start_date:
                query = query.filter(Lease.lease_end_date >= lease_start_date)
            if lease_end_date:
                query = query.filter(Lease.lease_end_date <= lease_end_date)
            if status:
                query = query.filter(Lease.lease_status == status)

            if sort_by:
                sort_attr = [
                    "lease_id",
                    "created_on",
                    "lease_type",
                    "lease_start_date",
                    "lease_end_date",
                    "lease_status",
                    "vin_no",
                    "medallion_no",
                    "plate_no",
                    "driver_id",
                    "driver_name",
                ]
                if sort_by in sort_attr:
                    if sort_by == "vin_no":
                        if not joined_vehicle:
                            query = query.join(Vehicle, Lease.vehicle_id == Vehicle.id)
                            joined_vehicle = True
                        query = query.order_by(
                            Vehicle.vin.asc()
                            if sort_order == "asc"
                            else Vehicle.vin.desc()
                        )
                    if sort_by == "medallion_no":
                        if not joined_medallion:
                            query = query.join(
                                Medallion, Lease.medallion_id == Medallion.id
                            )
                            joined_medallion = True
                        query = query.order_by(
                            Medallion.medallion_number.asc()
                            if sort_order == "asc"
                            else Medallion.medallion_number.desc()
                        )
                    if sort_by == "plate_no":
                        if not joined_vehicle:
                            query = query.join(Vehicle, Lease.vehicle_id == Vehicle.id)
                            joined_vehicle = True
                        if not joined_vehicle_registration:
                            query = query.join(
                                VehicleRegistration,
                                Vehicle.id == VehicleRegistration.vehicle_id,
                            )
                            joined_vehicle_registration = True
                        query = query.order_by(
                            VehicleRegistration.plate_number.asc()
                            if sort_order == "asc"
                            else VehicleRegistration.plate_number.desc()
                        )
                    if sort_by == "driver_id":
                        if not joined_lease_driver:
                            query = query.join(
                                LeaseDriver, Lease.id == LeaseDriver.lease_id
                            )
                            joined_lease_driver = True
                        if not joined_driver:
                            query = query.join(
                                Driver, LeaseDriver.driver_id == Driver.driver_id
                            )
                            joined_driver = True
                        query = query.order_by(
                            Driver.driver_id.asc()
                            if sort_order == "asc"
                            else Driver.driver_id.desc()
                        )
                    if sort_by == "driver_name":
                        if not joined_lease_driver:
                            query = query.join(
                                LeaseDriver, Lease.id == LeaseDriver.lease_id
                            )
                            joined_lease_driver = True
                        if not joined_driver:
                            query = query.join(
                                Driver, LeaseDriver.driver_id == Driver.driver_id
                            )
                            joined_driver = True
                        query = query.order_by(
                            Driver.full_name.asc()
                            if sort_order == "asc"
                            else Driver.full_name.desc()
                        )
                    if sort_by == "lease_start_date":
                        query = query.order_by(
                            Lease.lease_start_date.asc()
                            if sort_order == "asc"
                            else Lease.lease_start_date.desc()
                        )
                    if sort_by == "lease_end_date":
                        query = query.order_by(
                            Lease.lease_end_date.asc()
                            if sort_order == "asc"
                            else Lease.lease_end_date.desc()
                        )
                    if sort_by == "created_on":
                        query = query.order_by(
                            Lease.created_on.asc()
                            if sort_order == "asc"
                            else Lease.created_on.desc()
                        )
                    if sort_by == "lease_status":
                        query = query.order_by(
                            Lease.lease_status.asc()
                            if sort_order == "asc"
                            else Lease.lease_status.desc()
                        )
                    if sort_by == "lease_type":
                        query = query.order_by(
                            Lease.lease_type.asc()
                            if sort_order == "asc"
                            else Lease.lease_type.desc()
                        )
                    if sort_by == "lease_id":
                        query = query.order_by(
                            Lease.lease_id.asc()
                            if sort_order == "asc"
                            else Lease.lease_id.desc()
                        )
            else:
                query = query.order_by(desc(Lease.created_on))

            if multiple:
                total_count = query.count()
                if page and per_page:
                    query = query.offset((page - 1) * per_page).limit(per_page)
                return query.all(), total_count
            return query.first()
        except Exception as e:
            logger.error("Error getting lease: %s", str(e), exc_info=True)
            raise e

    def get_can_lease(
        self,
        db: Session,
        vin: str = None,
        medallion_number: str = None,
        plate_number: str = None,
        sort_by: str = None,
        sort_order: str = None,
        page: int = None,
        per_page: int = None,
        multiple: bool = False,
    ):
        """Get all active leases"""

        try:
            query = (
                db.query(
                    Vehicle,
                    Medallion.medallion_number.label("medallion_number"),
                    VehicleRegistration.plate_number.label("plate_number"),
                )
                .outerjoin(
                    VehicleRegistration, Vehicle.id == VehicleRegistration.vehicle_id
                )
                .outerjoin(Medallion, Vehicle.medallion_id == Medallion.id)
                .filter(Vehicle.vehicle_status == VehicleStatus.HACKED_UP)
            )
            if vin:
                query = query.filter(Vehicle.vin.ilike(f"%{vin}%"))
            if medallion_number:
                query = query.filter(
                    Medallion.medallion_number.ilike(f"%{medallion_number}%")
                )
            if plate_number:
                query = query.filter(
                    VehicleRegistration.plate_number.ilike(f"%{plate_number}%")
                )

            if sort_by and sort_order:
                sort_attr = {
                    "medallion_number": Medallion.medallion_number,
                    "plate_number": VehicleRegistration.plate_number,
                    "vin": Vehicle.vin,
                    "status": Vehicle.vehicle_status,
                    "created_on": Vehicle.created_on,
                    "updated_on": Vehicle.updated_on,
                    "make": Vehicle.make,
                    "model": Vehicle.model,
                    "year": Vehicle.year,
                }
                if sort_attr.get(sort_by):
                    query = query.order_by(
                        sort_attr.get(sort_by).asc()
                        if sort_order == "asc"
                        else sort_attr.get(sort_by).desc()
                    )

            if multiple:
                total = query.count()
                if page and per_page:
                    query = query.offset((page - 1) * per_page).limit(per_page)

                results = [
                    {
                        "id": vehicle.id,
                        "vin": vehicle.vin,
                        "medallion_number": medallion_number,
                        "plate_number": plate_number,
                        "vehicle_type": vehicle.vehicle_type,
                        "status": vehicle.vehicle_status,
                        "created_on": vehicle.created_on,
                        "updated_on": vehicle.updated_on,
                        "make": vehicle.make,
                        "model": vehicle.model,
                        "year": vehicle.year,
                    }
                    for vehicle, medallion_number, plate_number in query.all()
                ]
                return results, total

            vehicle, medallion_number, plate_number = query.first()
            if vehicle:
                return {
                    "id": vehicle.id,
                    "vin": vehicle.vin,
                    "medallion_number": medallion_number,
                    "plate_number": plate_number,
                    "vehicle_type": vehicle.vehicle_type,
                    "status": vehicle.vehicle_status,
                    "created_on": vehicle.created_on,
                    "updated_on": vehicle.updated_on,
                    "make": vehicle.make,
                    "model": vehicle.model,
                    "year": vehicle.year,
                }
            return None
        except Exception as e:
            logger.error("Error getting all active leases: %s", str(e))
            raise e

    def get_lease_configurations(
        self,
        db: Session,
        lookup_id: Optional[int] = None,
        lease_id: Optional[int] = None,
        lease_configuration_id: Optional[int] = None,
        lease_breakup_type: Optional[str] = None,
        sort_order: Optional[str] = "desc",
        multiple: bool = False,
    ) -> Union[LeaseConfiguration, List[LeaseConfiguration], None]:
        """Get lease configurations by ID"""
        try:
            query = db.query(LeaseConfiguration)
            if lookup_id:
                query = query.filter(LeaseConfiguration.id == lookup_id)
            if lease_id:
                query = query.filter(LeaseConfiguration.lease_id == lease_id)
            if lease_configuration_id:
                query = query.filter(LeaseConfiguration.id == lease_configuration_id)
            if lease_breakup_type:
                query = query.filter(
                    LeaseConfiguration.lease_breakup_type == lease_breakup_type
                )
            if sort_order:
                if sort_order == "desc":
                    query = query.order_by(desc(LeaseConfiguration.created_on))
                else:
                    query = query.order_by(asc(LeaseConfiguration.created_on))

            if multiple:
                return query.all()
            return query.first()
        except Exception as e:
            logger.error("Error getting lease configurations: %s", str(e))
            raise e

    def upsert_lease_configuration(
        self, db: Session, lease_configuration_data: dict
    ) -> LeaseConfiguration:
        """Upsert a lease configuration"""
        try:
            if lease_configuration_data.get("id"):
                lease_configuration = (
                    db.query(LeaseConfiguration)
                    .filter(LeaseConfiguration.id == lease_configuration_data.get("id"))
                    .first()
                )
                if lease_configuration:
                    for key, value in lease_configuration_data.items():
                        setattr(lease_configuration, key, value)
                    db.commit()
                    db.refresh(lease_configuration)
                    return lease_configuration
            else:
                lease_configuration = LeaseConfiguration(**lease_configuration_data)
                db.add(lease_configuration)
                db.commit()
                db.refresh(lease_configuration)
                return lease_configuration
        except Exception as e:
            logger.error("Error upserting lease configuration: %s", str(e))
            raise e

    def delete_lease_configurations(self, db: Session, config_id: int):
        """Delete lease configurations by lease ID"""
        try:
            db.query(LeaseConfiguration).filter(
                LeaseConfiguration.id == config_id
            ).delete()
            db.commit()
        except Exception as e:
            logger.error("Error deleting lease configurations: %s", str(e))
            raise e

    def upsert_lease(self, db: Session, lease_data: dict) -> Lease:
        """Upsert a lease"""
        try:
            if lease_data.get("id"):
                lease = db.query(Lease).filter(Lease.id == lease_data.get("id")).first()
                if lease:
                    for key, value in lease_data.items():
                        setattr(lease, key, value)
                    db.flush()
                    db.refresh(lease)
                    return lease
            else:
                lease = Lease(**lease_data)
                db.add(lease)
                db.flush()
                db.refresh(lease)
                return lease
        except Exception as e:
            logger.error("Error upserting lease: %s", str(e))
            raise e

    def get_lease_driver_documents(
        self,
        db: Session,
        lease_driver_id: Optional[int] = None,
        lease_id: Optional[int] = None,
        status: Optional[bool] = None,
        multiple: bool = False,
    ) -> Union[LeaseDriverDocument, List[LeaseDriverDocument], None]:
        """Get lease driver documents by ID"""
        try:
            query = db.query(LeaseDriverDocument)
            if lease_driver_id:
                query = query.filter(
                    LeaseDriverDocument.lease_driver_id == lease_driver_id
                )
            if lease_id:
                query = query.filter(LeaseDriverDocument.lease_id == lease_id)
            if status:
                query = query.filter(LeaseDriverDocument.status == status)

            if multiple:
                return query.all()
            return query.first()
        except Exception as e:
            logger.error("Error getting lease driver documents: %s", str(e))
            raise e

    def get_lease_drivers(
        self,
        db: Session,
        lease_id: Optional[int] = None,
        lease_driver_id: Optional[int] = None,
        driver_id: Optional[str] = None,
        sort_order: Optional[str] = "desc",
        multiple: bool = False,
    ) -> Union[LeaseDriver, List[LeaseDriver], None]:
        """Get lease drivers by ID"""
        try:
            query = db.query(LeaseDriver)
            if lease_driver_id:
                query = query.filter(LeaseDriver.id == lease_driver_id)
            if lease_id:
                query = query.filter(LeaseDriver.lease_id == lease_id)
            if driver_id:
                query = query.filter(LeaseDriver.driver_id == driver_id)
            if sort_order:
                query = query.order_by(
                    desc(LeaseDriver.created_on)
                    if sort_order == "desc"
                    else asc(LeaseDriver.created_on)
                )

            if multiple:
                return query.all()
            return query.first()
        except Exception as e:
            logger.error("Error getting lease drivers: %s", str(e))
            raise e

    def get_lease_payment_configuration(self, db: Session):
        """Get Lease Payment"""
        try:
            configs = db.query(LeasePaymentConfiguration).all()

            config_map = {}
            for config in configs:
                entry = {"total_amount": config.total_amount}
                if config.day_shift_amount is not None:
                    entry["day_shift_amount"] = config.day_shift_amount
                if config.night_shift_amount is not None:
                    entry["night_shift_amount"] = config.night_shift_amount
                config_map[config.config_type] = entry

            return config_map

        except Exception as e:
            logger.error("Error getting lease payment config: %s", str(e))
            raise e

    def upsert_lease_driver(self, db: Session, lease_driver_data: dict) -> LeaseDriver:
        """Upsert a lease driver"""
        try:
            if lease_driver_data.get("id"):
                lease_driver = self.get_lease_drivers(
                    db, lease_driver_id=lease_driver_data.get("id")
                )
                if lease_driver:
                    for key, value in lease_driver_data.items():
                        setattr(lease_driver, key, value)
                    db.flush()
                    db.refresh(lease_driver)
                    return lease_driver
            else:
                lease_driver = LeaseDriver(**lease_driver_data)
                db.add(lease_driver)
                db.flush()
                db.refresh(lease_driver)
                return lease_driver
        except Exception as e:
            logger.error("Error upserting lease driver: %s", str(e), exc_info=True)
            raise e

    def upsert_lease_payment_configuration(
        self, db: Session, lease_payment_config_data: dict
    ):
        """Upsert lease payment configuration"""

        try:
            config_type = lease_payment_config_data.get("config_type")
            if config_type:
                lease_config = (
                    db.query(LeasePaymentConfiguration)
                    .filter(LeasePaymentConfiguration.config_type == config_type)
                    .first()
                )

                if lease_config:
                    # Update existing fields
                    for key, value in lease_payment_config_data.items():
                        setattr(lease_config, key, value)

                    db.commit()
                    db.refresh(lease_config)
                    return lease_config

            # If not found, insert new
            lease_payment_config = LeasePaymentConfiguration(
                **lease_payment_config_data
            )
            db.add(lease_payment_config)
            db.commit()
            db.refresh(lease_payment_config)
            return lease_payment_config

        except Exception as e:
            logger.error(
                "Error upserting lease payment config: %s", str(e), exc_info=True
            )
            raise e

    def delete_lease_driver(self, db: Session, lease_driver_id: int):
        """Delete a lease driver"""
        try:
            db.query(LeaseDriver).filter(LeaseDriver.id == lease_driver_id).delete()
            db.commit()
        except Exception as e:
            logger.error("Error deleting lease driver: %s", str(e), exc_info=True)
            raise e

    def fetch_lease_information_driver(
        self, db: Session, driver_id: Optional[str] = None
    ):
        """Fetch lease information for a driver"""
        try:
            query = (
                db.query(
                    LeaseDriver.id.label("driver_lease_id"),
                    Lease.lease_id,
                    Medallion.medallion_number,
                    Driver.first_name,
                    Driver.last_name,
                    Driver.driver_id,
                    Vehicle.vin,
                    VehicleRegistration.plate_number,
                    Lease.lease_date,
                    Lease.id.label("lease_id_pk"),
                )
                .join(Driver, Driver.driver_id == LeaseDriver.driver_id)
                .join(Lease, Lease.id == LeaseDriver.lease_id)
                .join(Medallion, Medallion.id == Lease.medallion_id)
                .join(Vehicle, Vehicle.id == Lease.vehicle_id)
                .join(VehicleRegistration, VehicleRegistration.vehicle_id == Vehicle.id)
                .filter(
                    Driver.is_active == True,
                    LeaseDriver.is_active == True,
                    VehicleRegistration.is_active == True,
                )
            )

            if driver_id:
                query = query.filter(LeaseDriver.driver_id == driver_id)

            active_drivers = query.all()
            driver_ids = [ldr.driver_id for ldr in active_drivers]

            driver_lease_documents = (
                db.query(LeaseDriverDocument.lease_driver_id)
                .join(
                    LeaseDriver, LeaseDriver.id == LeaseDriverDocument.lease_driver_id
                )
                .filter(
                    LeaseDriverDocument.is_active == True,
                    LeaseDriver.driver_id.in_(driver_ids),
                )
                .all()
            )

            driver_ids_with_documents = {
                doc.lease_driver_id for doc in driver_lease_documents
            }

            lease_vehicle_info = []
            for lease_driver in active_drivers:
                if not lease_driver.lease_id:
                    continue

                lease_vehicle_info.append(
                    {
                        "driver_lease_id": lease_driver.driver_lease_id,
                        "lease_id": lease_driver.lease_id,
                        "medallion_number": lease_driver.medallion_number,
                        "driver_name": f"{lease_driver.first_name} {lease_driver.last_name}",
                        "vin_number": lease_driver.vin,
                        "vehicle_plate_number": lease_driver.plate_number,
                        "lease_date": lease_driver.lease_date,
                        "lease_id_pk": lease_driver.lease_id_pk,
                        "is_manager": lease_driver.driver_lease_id
                        in driver_ids_with_documents,
                    }
                )

            return lease_vehicle_info
        except Exception as e:
            logger.error(
                "Error fetching lease information for a driver: %s",
                str(e),
                exc_info=True,
            )
            raise e

    def handle_dov_lease(self, db: Session, lease_id: int, lease_data: DOVLease):
        """Handle DOV lease"""
        try:
            financials = lease_data.financial_information.model_dump(exclude_none=True)
            configuration_data = {}

            for key, value in financials.items():
                existing_config = self.get_lease_configurations(
                    db, lease_id=lease_id, lease_breakup_type=key
                )

                if existing_config:
                    configuration_data = {
                        "id": existing_config.id,
                        "lease_limit": value,
                    }
                else:
                    configuration_data = {
                        "lease_id": lease_id,
                        "lease_breakup_type": key,
                        "lease_limit": value,
                    }
                self.upsert_lease_configuration(db, configuration_data)
        except Exception as e:
            logger.error("Error handling DOV lease: %s", str(e))
            raise e

    def handle_long_term_lease(
        self, db: Session, lease_id: int, lease_data: LongTermLease
    ):
        """Handle Long Term Lease"""
        try:
            financials = lease_data.financialInformation.model_dump(exclude_none=True)
            configuration_data = {}

            for key, value in financials.items():
                existing_config = self.get_lease_configurations(
                    db, lease_id=lease_id, lease_breakup_type=key
                )

                if existing_config:
                    configuration_data = {
                        "id": existing_config.id,
                        "lease_limit": value,
                    }
                else:
                    configuration_data = {
                        "lease_id": lease_id,
                        "lease_breakup_type": key,
                        "lease_limit": value,
                    }
                self.upsert_lease_configuration(db, configuration_data)
        except Exception as e:
            logger.error("Error handling Long Term Lease: %s", str(e))
            raise e

    def handle_short_term_lease(
        self, db: Session, lease_id: int, short_term_data: ShortTermLease
    ):
        """Handle Short Term Lease"""
        try:
            financials = short_term_data.financialInformation
            days_of_week = ["sun", "mon", "tus", "wen", "thu", "fri", "sat"]

            for day in days_of_week:
                config_data = {}
                day_info = financials.get(day)
                if not day_info:
                    continue

                for shift_type in ["day_shift", "night_shift"]:
                    lease_breakup_type = f"{day}_{shift_type}"
                    lease_limit = day_info.get(
                        "day_shift" if shift_type == "day_shift" else "night_shift", ""
                    )
                    if lease_limit is None:
                        continue

                    existing_config = self.get_lease_configurations(
                        db, lease_id=lease_id, lease_breakup_type=lease_breakup_type
                    )

                    if existing_config:
                        config_data = {
                            "lease_limit": lease_limit,
                            "id": existing_config.id,
                        }
                    else:
                        config_data = {
                            "lease_id": lease_id,
                            "lease_breakup_type": lease_breakup_type,
                            "lease_limit": lease_limit,
                        }

                    self.upsert_lease_configuration(db, config_data)
        except Exception as e:
            logger.error("Error handling Short Term Lease: %s", str(e))
            raise e

    def handle_medallion_lease(
        self, db: Session, lease_id: int, medallion_data: MedallionOnlyLease
    ):
        """Handle Medallion Only Lease"""
        try:
            financials = medallion_data.financialInformation.model_dump(
                exclude_none=True
            )
            configuration_data = {}

            for key, value in financials.items():
                existing_config = self.get_lease_configurations(
                    db, lease_id=lease_id, lease_breakup_type=key
                )

                if existing_config:
                    configuration_data = {
                        "id": existing_config.id,
                        "lease_limit": value,
                    }
                else:
                    configuration_data = {
                        "lease_id": lease_id,
                        "lease_breakup_type": key,
                        "lease_limit": value,
                    }
                self.upsert_lease_configuration(db, configuration_data)
        except Exception as e:
            logger.error("Error handling Long Term Lease: %s", str(e))
            raise e

    def update_lease_driver_info(self, db: Session, lease_id: int, driver_info: dict):
        """Update lease driver information"""
        try:
            driver_id = driver_info.get("driver_id")
            is_day_night_shift = driver_info.get("is_day_night_shift")
            co_lease_seq = driver_info.get("co_lease_seq")

            valid_driver = driver_service.get_drivers(db, driver_id=driver_id)
            if not valid_driver:
                raise ValueError(f"Driver ID {driver_id} passed is invalid")

            if is_day_night_shift is None:
                driver_role = "L"
            elif is_day_night_shift:
                driver_role = "DL"
            else:
                driver_role = "NL"

            lease_driver = self.get_lease_drivers(
                db, lease_id=lease_id, driver_id=driver_id
            )
            lease_driver_data = {}

            if lease_driver:
                lease_driver_data = {
                    "id": lease_driver.id,
                    "is_day_night_shift": is_day_night_shift,
                    "co_lease_seq": co_lease_seq,
                }
            else:
                lease_driver_data = {
                    "driver_id": driver_id,
                    "lease_id": lease_id,
                    "driver_role": driver_role,
                    "is_day_night_shift": is_day_night_shift,
                    "co_lease_seq": co_lease_seq,
                    "date_added": datetime.now(timezone.utc),
                }
            self.upsert_lease_driver(db, lease_driver_data)
            return f"Driver {driver_id} added or updated successfully for lease with ID {lease_id}"
        except Exception as e:
            logger.error("Error updating lease driver information: %s", str(e))
            raise e

    def remove_drivers_from_lease(
        self, db: Session, lease_id: int, driver_ids: set[str]
    ):
        """Remove drivers from lease"""
        try:
            delete_query = (
                delete(LeaseDriver)
                .where(LeaseDriver.lease_id == lease_id)
                .where(LeaseDriver.driver_id.in_(driver_ids))
            )
            result = db.execute(delete_query)
            db.flush()
            for driver_id in driver_ids:
                logger.info("%s removed from the lease table", driver_id)
            return result.rowcount
        except Exception as e:
            logger.error("Error removing drivers from lease: %s", str(e))
            raise e

    def fetch_latest_driver_document_status_by_lease(self, db: Session, lease: Lease):
        """Fetch the latest driver document status by lease"""
        try:
            # Fetch drivers associated with the lease
            lease_drivers = (
                db.query(LeaseDriver).filter(LeaseDriver.lease_id == lease.id).all()
            )

            if not lease_drivers:
                return {"message": "No drivers associated with this lease."}

            result = []

            for lease_driver in lease_drivers:
                co_lease_seq = lease_driver.co_lease_seq
                driver_id = lease_driver.driver_id

                lease_driver_documents = lease_driver.documents[:2]

                # Fetch the latest document for the driver
                latest_docs = (
                    db.query(Document)
                    .filter(
                        Document.object_lookup_id == str(lease_driver.id),
                        Document.object_type == f"co-leasee-{co_lease_seq}",
                        Document.document_type.in_(
                            ["driver_vehicle_lease", "driver_medallion_lease"]
                        ),
                    )
                    .order_by(desc(Document.created_on))
                    .all()
                )

                # signed_document_url = ""
                if not lease_driver_documents:
                    for latest_document in latest_docs[:2]:
                        result.append(
                            {
                                "document_id": latest_document.id,
                                "driver_id": lease_driver.driver_id,
                                "driver_name": lease_driver.driver.full_name,
                                "driver_email": lease_driver.driver.email_address,
                                "document_name": latest_document.document_name,
                                "envelope_id": "",
                                "is_sent_for_signature": False,
                                "has_front_desk_signed": False,
                                "has_driver_signed": False,
                                "document_envelope_id": "",
                                "document_date": latest_document.document_date,
                                "file_size": latest_document.document_actual_size
                                if latest_document.document_actual_size
                                else 0,
                                "comments": latest_document.document_note,
                                "document_type": latest_document.document_type,
                                "object_type": latest_document.object_type,
                                "presigned_url": latest_document.presigned_url,
                                "document_format": latest_document.document_format,
                                "document_created_on": latest_document.created_on,
                                "object_lookup_id": lease_driver.id,
                                "signing_type": "",
                            }
                        )
                    return result

                for lease_driver_document in lease_driver_documents:
                    if lease_driver_document.envelope:
                        document_type = (
                            f"driver_{lease_driver_document.envelope.object_type}"
                        )
                        latest_document = (
                            db.query(Document)
                            .filter(
                                Document.object_lookup_id == str(lease_driver.id),
                                Document.object_type == f"co-leasee-{co_lease_seq}",
                                Document.document_type.in_([document_type]),
                            )
                            .order_by(desc(Document.created_on))
                            .first()
                        )
                    else:
                        latest_document = (
                            db.query(Document)
                            .filter(
                                Document.id == str(lease_driver_document.document_id),
                            )
                            .order_by(desc(Document.created_on))
                            .first()
                        )
                    result.append(
                        {
                            "object_lookup_id": lease_driver.id,
                            "document_id": latest_document.id,
                            "driver_id": lease_driver.driver_id,
                            "driver_name": lease_driver.driver.full_name,
                            "driver_email": lease_driver.driver.email_address,
                            "document_name": latest_document.document_name,
                            "envelope_id": lease_driver_document.document_envelope_id
                            if lease_driver_document
                            else "",
                            "is_sent_for_signature": False
                            if lease_driver_document
                            else False,
                            "has_front_desk_signed": lease_driver_document.has_frontend_signed
                            if lease_driver_document
                            else None,
                            "has_driver_signed": lease_driver_document.has_driver_signed
                            if lease_driver_document
                            else None,
                            "document_envelope_id": lease_driver_document.document_envelope_id
                            if lease_driver_document
                            else None,
                            "document_date": latest_document.document_date,
                            "file_size": latest_document.document_actual_size
                            if latest_document.document_actual_size
                            else 0,
                            "comments": latest_document.document_note,
                            "document_type": latest_document.document_type,
                            "object_type": latest_document.object_type,
                            "presigned_url": latest_document.presigned_url,
                            "document_format": latest_document.document_format,
                            # "signed_document_url": signed_document_url,
                            "document_created_on": latest_document.created_on,
                            "signing_type": lease_driver_document.signing_type,
                        }
                    )
            return result
        except Exception as e:
            logger.error(
                "Error fetching latest driver document status by lease: %s", str(e)
            )
            raise e

    def upsert_lease_drive_document_for_wet_signature(
        self,
        db: Session,
        lease: Lease,
        signature_mode="",
    ):
        """Upsert lease driver documents"""
        try:
            documents = []
            for driver in lease.lease_driver:
                lease_document = (
                    db.query(LeaseDriverDocument)
                    .filter(
                        LeaseDriverDocument.lease_driver_id == driver.id,
                        LeaseDriverDocument.is_active == True,
                    )
                    .first()
                )

                if lease_document:
                    logger.info(
                        "Marking this lease driver document %s as inactive",
                        lease_document.id,
                    )
                    lease_document.is_active = False
                    lease_document.updated_on = datetime.now(timezone.utc)
                    db.add(lease_document)
                    db.flush()

                latest_docs = (
                    db.query(Document)
                    .filter(
                        Document.object_lookup_id == str(driver.id),
                        Document.object_type == f"co-leasee-{driver.co_lease_seq}",
                        Document.document_type.in_(
                            ["driver_medallion_lease", "driver_vehicle_lease"],
                        ),
                    )
                    .order_by(desc(Document.document_date))
                    .all()
                )

                for id, latest_doc in enumerate(latest_docs[:2]):
                    lease_document = LeaseDriverDocument(
                        lease_driver_id=driver.id,
                        document_id=latest_doc.id,
                        document_envelope_id=None,
                        has_frontend_signed=True,
                        has_driver_signed=True,
                        frontend_signed_date=datetime.now(timezone.utc),
                        driver_signed_date=datetime.now(timezone.utc),
                        signing_type=signature_mode,
                        created_on=datetime.now(timezone.utc),
                        updated_on=datetime.now(timezone.utc),
                    )
                    db.add(lease_document)
                    db.flush()
                    documents.append(
                        {
                            "driver_id": driver.id,
                            "lease_id": lease.id,
                            "document_envelope_id": lease_document.document_envelope_id,
                            "has_frontend_signed": lease_document.has_frontend_signed,
                            "has_driver_signed": lease_document.has_driver_signed,
                        }
                    )
            return documents
        except Exception as e:
            logger.error(
                "Error upserting lease driver documents: %s", str(e), exc_info=True
            )
            raise e

    def invalidate_lease_driver_documents(self, db: Session, lease: Lease):
        for driver in lease.lease_driver:
            lease_document = (
                db.query(LeaseDriverDocument)
                .filter(
                    LeaseDriverDocument.lease_driver_id == driver.id,
                    LeaseDriverDocument.is_active,
                )
                .first()
            )

            if lease_document:
                logger.info(
                    f"Marking this lease driver's - {lease_document.lease_driver_id} document {lease_document.id} as inactive",
                )
                lease_document.is_active = False
                lease_document.updated_on = datetime.now(timezone.utc)
                db.add(lease_document)
                db.flush()
        logger.info(
            f"All documents for the lease id {lease.lease_id} have been invalidated"
        )

    def upsert_lease_driver_documents(
        self,
        db: Session,
        lease: Lease,
        signature_mode="",
        envelope_ids=[],
        document_types=[],
    ):
        """Upsert lease driver documents"""
        try:
            documents = []
            for driver in lease.lease_driver:
                lease_document = (
                    db.query(LeaseDriverDocument)
                    .filter(
                        LeaseDriverDocument.lease_driver_id == driver.id,
                        LeaseDriverDocument.is_active,
                    )
                    .first()
                )

                latest_docs = (
                    db.query(Document)
                    .filter(
                        Document.object_lookup_id == str(driver.id),
                        Document.object_type == f"co-leasee-{driver.co_lease_seq}",
                        Document.document_type.in_(
                            document_types,
                        ),
                    )
                    .order_by(desc(Document.document_date))
                    .all()
                )

                for id, latest_doc in enumerate(latest_docs[: len(document_types)]):
                    try:
                        envelope_id = envelope_ids[id]
                    except (IndexError, TypeError):
                        envelope_id = ""

                    lease_document = LeaseDriverDocument(
                        lease_driver_id=driver.id,
                        document_envelope_id=envelope_id,
                        has_frontend_signed=False,
                        has_driver_signed=False,
                        frontend_signed_date=None,
                        driver_signed_date=None,
                        signing_type=signature_mode,
                        created_on=datetime.now(timezone.utc),
                        updated_on=datetime.now(timezone.utc),
                    )
                    db.add(lease_document)
                    db.flush()
                    documents.append(
                        {
                            "driver_id": driver.id,
                            "lease_id": lease.id,
                            "document_envelope_id": lease_document.document_envelope_id,
                            "has_frontend_signed": lease_document.has_frontend_signed,
                            "has_driver_signed": lease_document.has_driver_signed,
                        }
                    )
            return documents
        except Exception as e:
            logger.error(
                "Error upserting lease driver documents: %s", str(e), exc_info=True
            )
            raise e

    def fetch_lease_information_for_driver(self, db: Session, driver_id: str = None):
        """Fetch lease information for a driver"""
        try:
            active_lease_drivers_query = (
                db.query(
                    LeaseDriver.id.label("driver_lease_id"),
                    Lease.lease_id,
                    Medallion.medallion_number,
                    Driver.first_name,
                    Driver.last_name,
                    Driver.driver_id,
                    Vehicle.vin,
                    VehicleRegistration.plate_number,
                    Lease.lease_date,
                    Lease.id.label("lease_id_pk"),
                )
                .join(Driver, Driver.driver_id == LeaseDriver.driver_id)
                .join(Lease, Lease.id == LeaseDriver.lease_id)
                .join(Medallion, Medallion.id == Lease.medallion_id)
                .join(Vehicle, Vehicle.id == Lease.vehicle_id)
                .join(VehicleRegistration, VehicleRegistration.vehicle_id == Vehicle.id)
                .filter(
                    Driver.is_active == True,
                    LeaseDriver.is_active == True,
                    VehicleRegistration.is_active == True,
                )
            )

            if driver_id:
                active_lease_drivers_query = active_lease_drivers_query.filter(
                    LeaseDriver.driver_id == driver_id
                )

            active_lease_drivers = active_lease_drivers_query.all()
            lease_vehicle_info = []
            for lease_driver in active_lease_drivers:
                driver_lease_document = (
                    db.query(LeaseDriverDocument)
                    .join(
                        LeaseDriver,
                        LeaseDriver.id == LeaseDriverDocument.lease_driver_id,
                    )
                    .filter(
                        LeaseDriverDocument.is_active == True,
                        LeaseDriver.driver_id == lease_driver.driver_id,
                    )
                    .first()
                )
                if not lease_driver.lease_id:
                    continue
                lease_vehicle_info.append(
                    {
                        "driver_lease_id": lease_driver.driver_lease_id,
                        "lease_id": lease_driver.lease_id,
                        "medallion_number": lease_driver.medallion_number,
                        "driver_name": f"{lease_driver.first_name} {lease_driver.last_name}",
                        "vin_number": lease_driver.vin,
                        "vehicle_plate_number": lease_driver.plate_number,
                        "lease_date": lease_driver.lease_date,
                        "lease_id_pk": lease_driver.lease_id_pk,
                        "is_manager": True if driver_lease_document else False,
                    }
                )
            return lease_vehicle_info
        except Exception as e:
            logger.error(
                "Error fetching lease information for driver: %s", e, exc_info=True
            )
            raise e

    def fetch_lease_payment_configuration(
        self,
        db: Session,
        config_type: Optional[str] = None,
        multiple: Optional[bool] = False,
    ) -> Union[LeasePaymentConfiguration, List[LeasePaymentConfiguration], None]:
        """Fetch lease payment configuration"""
        try:
            query = db.query(LeasePaymentConfiguration)
            if config_type:
                config_types = config_type.split(",")
                query = query.filter(
                    LeasePaymentConfiguration.config_type.in_(config_types)
                )

            if multiple:
                return query.all()
            return query.first()
        except Exception as e:
            logger.error(
                "Error fetching lease payment configuration: %s", e, exc_info=True
            )
            raise e

    # --- LEASE PRESET CRUD METHODS ---

    def get_lease_preset(self, db: Session, preset_id: int) -> Optional[LeasePreset]:
        """Gets a single lease preset by its ID."""
        stmt = select(LeasePreset).where(LeasePreset.id == preset_id)
        return db.execute(stmt).scalar_one_or_none()

    def list_lease_presets(
        self,
        db: Session,
        page: int,
        per_page: int,
        sort_by: str,
        sort_order: str,
        lease_type: Optional[str] = None,
        vehicle_make: Optional[str] = None,
        vehicle_model: Optional[str] = None,
        vehicle_year: Optional[int] = None,
    ) -> Tuple[List[LeasePreset], int]:
        """Lists lease presets with filtering, sorting, and pagination."""
        stmt = select(LeasePreset)

        # Apply filters
        if lease_type:
            stmt = stmt.where(LeasePreset.lease_type.ilike(f"%{lease_type}%"))
        if vehicle_make:
            stmt = stmt.where(LeasePreset.vehicle_make.ilike(f"%{vehicle_make}%"))
        if vehicle_model:
            stmt = stmt.where(LeasePreset.vehicle_model.ilike(f"%{vehicle_model}%"))
        if vehicle_year:
            stmt = stmt.where(LeasePreset.vehicle_year == vehicle_year)

        # Get total count before pagination
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_items = db.execute(count_stmt).scalar()

        # Apply sorting
        if hasattr(LeasePreset, sort_by):
            sort_column = getattr(LeasePreset, sort_by)
            stmt = stmt.order_by(
                sort_column.desc() if sort_order == "desc" else sort_column.asc()
            )

        # Apply pagination
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        results = db.execute(stmt).scalars().all()
        return results, total_items

    def create_lease_preset(
        self, db: Session, preset_data: LeasePresetCreate
    ) -> LeasePreset:
        """Creates a new lease preset record."""
        new_preset = LeasePreset(**preset_data.model_dump())
        db.add(new_preset)
        db.commit()
        db.refresh(new_preset)
        return new_preset

    def update_lease_preset(
        self, db: Session, preset_id: int, preset_data: LeasePresetUpdate
    ) -> LeasePreset:
        """Updates an existing lease preset record."""
        preset = self.get_lease_preset(db, preset_id)
        if not preset:
            raise ValueError(f"LeasePreset with id {preset_id} not found.")

        update_data = preset_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(preset, key, value)

        db.commit()
        db.refresh(preset)
        return preset

    def delete_lease_preset(self, db: Session, preset_id: int) -> bool:
        """Deletes a lease preset record."""
        preset = self.get_lease_preset(db, preset_id)
        if not preset:
            raise ValueError(f"LeasePreset with id {preset_id} not found.")

        db.delete(preset)
        db.commit()
        return True

    def _coerce_to_date(self, dt_str: Optional[str]) -> date:
        if not dt_str:
            return date.today()
        try:
            if isinstance(dt_str, datetime):
                return dt_str.date()
            s = str(dt_str)
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            return datetime.fromisoformat(s).date()
        except Exception:
            return date.today()

    def mark_bat_manager_as_signed(self, db: Session, lease: Lease):
        for lease_driver in lease.lease_driver:
            for driver_doc in lease_driver.documents:
                driver_doc.has_frontend_signed = True
                driver_doc.frontend_signed_date = date.today()
                logger.info(
                    f"Marking lease document id-{driver_doc.id}, for envelope {driver_doc.document_envelope_id} for driver {lease_driver.driver_id} as signed by manager"
                )

        db.add(lease)
        db.flush()

    def update_lease_driver_document_signoff_latest(
        self,
        db: Session,
        *,
        ctx: dict,
        signed_on: Optional[date] = None,
    ) -> dict:
        """
        Update the latest LeaseDriverDocument for ctx['envelope_id']:
        - recipient_id '1' => set driver signoff + date
        - recipient_id '2' => set front-end signoff + date
        Update-only, picks ONE latest row (by id desc). Calls db.flush(); no commit/rollback.
        """
        envelope_id = (ctx or {}).get("envelope_id")
        if not envelope_id:
            raise ValueError(
                "update_lease_driver_document_signoff_latest: missing ctx['envelope_id']"
            )

        recipient_id_raw = (ctx or {}).get("recipient_id")
        if recipient_id_raw is None:
            raise ValueError(
                "update_lease_driver_document_signoff_latest: missing ctx['recipient_id']"
            )

        recipient_id = str(recipient_id_raw).strip()
        when = signed_on or self._coerce_to_date((ctx or {}).get("generated_at"))

        row = (
            db.query(LeaseDriverDocument)
            .filter(LeaseDriverDocument.document_envelope_id == envelope_id)
            .order_by(LeaseDriverDocument.id.desc())
            .first()
        )

        if not row:
            return {
                "ok": False,
                "reason": "no LeaseDriverDocument found for envelope",
                "envelope_id": envelope_id,
                "updated": False,
            }

        updated = False
        if recipient_id == "1":
            # Driver signoff
            if row.has_driver_signed is not True:
                row.has_driver_signed = True
                updated = True
            if not row.driver_signed_date:
                row.driver_signed_date = when
                updated = True
        elif recipient_id == "2":
            # Front-end signoff
            if row.has_frontend_signed is not True:
                row.has_frontend_signed = True
                updated = True
            if not row.frontend_signed_date:
                row.frontend_signed_date = when
                updated = True
        else:
            return {
                "ok": False,
                "reason": f"recipient_id '{recipient_id}' not mapped (expect '1' for driver, '2' for front-end)",
                "envelope_id": envelope_id,
                "updated": False,
            }

        # Push changes without ending the transaction
        db.flush()

        return {
            "ok": True,
            "envelope_id": envelope_id,
            "recipient_id": recipient_id,
            "lease_driver_document_id": row.id,
            "updated": updated,
            "signed_on": when.isoformat(),
        }


lease_service = LeaseService()
