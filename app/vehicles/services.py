### app/vehicles/services.py

# Standard library imports
from typing import List, Optional, Union

# Third party imports
from sqlalchemy import asc, desc, func , or_ , String, cast
from sqlalchemy.orm import Session

from app.utils.logger import get_logger
from app.medallions.models import Medallion
from app.uploads.models import Document

# Local imports
from app.vehicles.models import (
    Dealer,
    Vehicle,
    VehicleEntity,
    VehicleHackUp,
    VehicleInspection,
    VehicleRegistration,
    VehicleRepair,
)
from app.vehicles.schemas import HackupStatus, RegistrationStatus, VehicleStatus , VehicleEntityStatus

logger = get_logger(__name__)


class VehicleService:
    """Service for vehicle operations"""

    def get_documents_for_vehicle_inspection(
        self, db: Session, vehicle_inspection_id: str
    ):
        """
        Get documents for a specific vehicle inspection.

        Args:
            db: The database session.
            inspection_id: The ID of the inspection.

        Returns:
            A list of documents.
        """
        try:
            documents = (
                db.query(Document)
                .filter(
                    Document.object_type == "vehicle",
                    Document.document_type.in_(
                        [
                            "meter_inspection_report_document",
                            "rate_card_document",
                            "inspection_receipt",
                        ]
                    ),
                    Document.object_lookup_id == vehicle_inspection_id,
                )
                .all()
            )

            return [document.to_dict() for document in documents]
        except Exception as e:
            logger.error("Error getting documents for vehicle inspection: %s", str(e))
            raise e

    def get_vehicles_by_status(self, db: Session) -> dict:
        """Get vehicles by status"""
        try:
            status_count = (
                db.query(Vehicle.vehicle_status, func.count(Vehicle.id))
                .group_by(Vehicle.vehicle_status)
                .filter(
                    (
                        Vehicle.vehicle_status.in_(
                            [
                                VehicleStatus.ACTIVE,
                                VehicleStatus.IN_PROGRESS,
                                VehicleStatus.AVAILABLE,
                            ]
                        )
                    )
                    & (Vehicle.is_active == True)
                )
                .all()
            )

            return {status: count for status, count in status_count}
        except Exception as e:
            logger.error("Error getting vehicles by status: %s", str(e))
            raise e

    def get_dealer(
        self,
        db: Session,
        dealer_id: Optional[int] = None,
        dealer_name: Optional[str] = None,
        dealer_bank_name: Optional[str] = None,
        dealer_bank_account_number: Optional[str] = None,
        per_page: Optional[int] = None,
        page: Optional[int] = None,
        sort_order: Optional[str] = "desc",
        sort_by: Optional[str] = "created_on",
        multiple: bool = False,
    ) -> Union[Dealer, List[Dealer], None]:
        """Get dealer by ID"""
        try:
            query = db.query(Dealer)
            if dealer_id:
                query = query.filter(Dealer.id == dealer_id)
            if dealer_name:
                query = query.filter(Dealer.dealer_name.ilike(f"%{dealer_name}%"))
            if dealer_bank_name:
                query = query.filter(
                    Dealer.dealer_bank_name.ilike(f"%{dealer_bank_name}%")
                )
            if dealer_bank_account_number:
                query = query.filter(
                    Dealer.dealer_bank_account_number.ilike(
                        f"%{dealer_bank_account_number}%"
                    )
                )

            if multiple:
                if sort_by:
                    sort_mapping = {
                        "dealer_name": Dealer.dealer_name,
                        "dealer_bank_name": Dealer.dealer_bank_name,
                        "dealer_bank_account_number": Dealer.dealer_bank_account_number,
                        "created_on": Dealer.created_on,
                    }
                    sort_column = sort_mapping[sort_by]
                    query = query.order_by(
                        sort_column.desc()
                        if sort_order == "desc"
                        else sort_column.asc()
                    )
                else:
                    query = query.order_by(desc(Dealer.created_on))

                if per_page and page:
                    return query.count(), query.offset((page - 1) * per_page).limit(
                        per_page
                    ).all()
                return query.all()
            return query.first()
        except Exception as e:
            logger.error("Error getting dealer: %s", str(e))
            raise e

    def get_vehicles(
        self,
        db: Session,
        vehicle_id: Optional[int] = None,
        vin: Optional[str] = None,
        medallion_id: Optional[int] = None,
        medallion_number: Optional[str] = None,
        plate_number: Optional[str] = None,
        dealer_id: Optional[int] = None,
        multiple: bool = False,
    ) -> Union[Vehicle, List[Vehicle], None]:
        """Get vehicles by ID, VIN, or medallion ID"""
        try:
            query = db.query(Vehicle)

            if vehicle_id:
                query = query.filter(Vehicle.id == vehicle_id)
            if vin:
                query = query.filter(Vehicle.vin == vin)
            if medallion_id:
                query = query.filter(Vehicle.medallion_id == medallion_id)
            if medallion_number:
                query = query.join(
                    Medallion, Vehicle.medallion_id == Medallion.id
                ).filter(Medallion.medallion_number == medallion_number)
            if plate_number:
                query = query.join(
                    VehicleRegistration, Vehicle.id == VehicleRegistration.vehicle_id
                ).filter(VehicleRegistration.plate_number == plate_number)
            if dealer_id:
                query = query.filter(Vehicle.dealer_id == dealer_id)

            if multiple:
                return query.all()
            return query.first()
        except Exception as e:
            logger.error("Error getting vehicles: %s", str(e))
            raise e

    def upsert_vehicle(self, db: Session, vehicle_data: dict) -> Vehicle:
        """Upsert a vehicle"""
        try:
            if vehicle_data.get("id"):
                vehicle = self.get_vehicles(db, vehicle_id=vehicle_data.get("id"))
                if vehicle:
                    for key, value in vehicle_data.items():
                        setattr(vehicle, key, value)
                    db.commit()
                    db.refresh(vehicle)
                    return vehicle
            else:
                vehicle = Vehicle(**vehicle_data)
                vehicle.vehicle_status = VehicleStatus.IN_PROGRESS
                db.add(vehicle)
                db.commit()
                db.refresh(vehicle)
                return vehicle
        except Exception as e:
            logger.error("Error upserting vehicle: %s", str(e))
            raise e

    def get_vehicle_hackup(
        self,
        db: Session,
        vehicle_hackup_id: Optional[int] = None,
        vehicle_id: Optional[int] = None,
        hackup_status: Optional[HackupStatus] = None,
        multiple: bool = False,
        sort_order: Optional[str] = "desc",
    ) -> Union[VehicleHackUp, List[VehicleHackUp], None]:
        """Get vehicle hackup by ID, status, or multiple"""
        try:
            query = db.query(VehicleHackUp)
            if vehicle_hackup_id:
                query = query.filter(VehicleHackUp.id == vehicle_hackup_id)
            if vehicle_id:
                query = query.filter(VehicleHackUp.vehicle_id == vehicle_id)
            if hackup_status:
                query = query.filter(
                    VehicleHackUp.status == HackupStatus(hackup_status)
                )

            if sort_order:
                query = query.order_by(
                    desc(VehicleHackUp.created_on)
                    if sort_order == "desc"
                    else asc(VehicleHackUp.created_on)
                )

            if multiple:
                return query.all()
            return query.first()
        except Exception as e:
            logger.error("Error getting vehicle hackup: %s", str(e))
            raise e

    def upsert_vehicle_hackup(
        self, db: Session, vehicle_hackup_data: dict
    ) -> VehicleHackUp:
        """Upsert a vehicle hackup"""
        try:
            if vehicle_hackup_data.get("id"):
                vehicle_hackup = self.get_vehicle_hackup(
                    db, vehicle_hackup_id=vehicle_hackup_data.get("id")
                )
                if vehicle_hackup:
                    for key, value in vehicle_hackup_data.items():
                        setattr(vehicle_hackup, key, value)
                    db.commit()
                    db.refresh(vehicle_hackup)
                    return vehicle_hackup
            else:
                vehicle_hackup = VehicleHackUp(**vehicle_hackup_data)
                vehicle_hackup.status = HackupStatus.INPROGRESS
                db.add(vehicle_hackup)
                db.commit()
                db.refresh(vehicle_hackup)
                return vehicle_hackup
        except Exception as e:
            logger.error("Error upserting vehicle hackup: %s", str(e))
            raise e

    def get_vehicle_registration(
        self,
        db: Session,
        registration_id: Optional[int] = None,
        vehicle_id: Optional[int] = None,
        registration_status: Optional[RegistrationStatus] = None,
        multiple: bool = False,
        sort_order: Optional[str] = "desc",
    ) -> Union[VehicleRegistration, List[VehicleRegistration], None]:
        """Get vehicle registration by ID, vehicle ID, or multiple"""
        try:
            query = db.query(VehicleRegistration)
            if registration_id:
                query = query.filter(VehicleRegistration.id == registration_id)
            if vehicle_id:
                query = query.filter(VehicleRegistration.vehicle_id == vehicle_id)
            if registration_status:
                query = query.filter(
                    VehicleRegistration.status
                    == RegistrationStatus(registration_status)
                )

            if sort_order:
                query = query.order_by(
                    desc(VehicleRegistration.created_on)
                    if sort_order == "desc"
                    else asc(VehicleRegistration.created_on)
                )

            if multiple:
                return query.all()
            return query.first()
        except Exception as e:
            logger.error("Error getting vehicle registration: %s", str(e))
            raise e

    def upsert_registration(
        self, db: Session, registration_data: dict
    ) -> VehicleRegistration:
        """Upsert a vehicle registration"""
        try:
            if registration_data.get("id"):
                registration = self.get_vehicle_registration(
                    db, registration_id=registration_data.get("id")
                )
                if registration:
                    for key, value in registration_data.items():
                        setattr(registration, key, value)
                    db.commit()
                    db.refresh(registration)
                    return registration
            else:
                registration = VehicleRegistration(**registration_data)
                db.add(registration)
                db.commit()
                db.refresh(registration)
                return registration
        except Exception as e:
            logger.error("Error upserting vehicle registration: %s", str(e))
            raise e

    def get_inspection(
        self,
        db: Session,
        inspection_id: Optional[int] = None,
        vehicle_id: Optional[int] = None,
        inspection_status: Optional[RegistrationStatus] = None,
        multiple: bool = False,
        sort_order: Optional[str] = "desc",
    ) -> Union[VehicleInspection, List[VehicleInspection], None]:
        """Get vehicle inspection by ID, vehicle ID, or multiple"""
        try:
            query = db.query(VehicleInspection)
            if inspection_id:
                query = query.filter(VehicleInspection.id == inspection_id)
            if vehicle_id:
                query = query.filter(VehicleInspection.vehicle_id == vehicle_id)
            if inspection_status:
                query = query.filter(
                    VehicleInspection.status == RegistrationStatus(inspection_status)
                )

            if sort_order:
                query = query.order_by(
                    desc(VehicleInspection.created_on)
                    if sort_order == "desc"
                    else asc(VehicleInspection.created_on)
                )

            if multiple:
                return query.all()
            return query.first()
        except Exception as e:
            logger.error("Error getting vehicle inspection: %s", str(e))
            raise e

    def upsert_inspection(
        self, db: Session, inspection_data: dict
    ) -> VehicleInspection:
        """Upsert a vehicle inspection"""
        try:
            if inspection_data.get("id"):
                inspection = self.get_inspection(
                    db, inspection_id=inspection_data.get("id")
                )
                if inspection:
                    for key, value in inspection_data.items():
                        setattr(inspection, key, value)
                    db.commit()
                    db.refresh(inspection)
                    return inspection
            else:
                inspection = VehicleInspection(**inspection_data)
                db.add(inspection)
                db.commit()
                db.refresh(inspection)
                return inspection
        except Exception as e:
            logger.error("Error upserting vehicle inspection: %s", str(e))
            raise e

    def get_repair(
        self,
        db: Session,
        repair_id: Optional[int] = None,
        vehicle_id: Optional[int] = None,
        multiple: bool = False,
        sort_order: Optional[str] = "desc",
    ) -> Union[VehicleRepair, List[VehicleRepair], None]:
        """Get vehicle repair by ID, vehicle ID, or multiple"""
        try:
            query = db.query(VehicleRepair)
            if repair_id:
                query = query.filter(VehicleRepair.id == repair_id)
            if vehicle_id:
                query = query.filter(VehicleRepair.vehicle_id == vehicle_id)

            if sort_order:
                query = query.order_by(
                    desc(VehicleRepair.created_on)
                    if sort_order == "desc"
                    else asc(VehicleRepair.created_on)
                )

            if multiple:
                return query.all()
            return query.first()
        except Exception as e:
            logger.error("Error getting vehicle repair: %s", str(e))
            raise e

    def get_vehicle_entity(
            self, db: Session,
            entity_id: Optional[int] = None,
            entity_name: Optional[str] = None,
            owner_id: Optional[str] = None,
            entity_status: Optional[str] = None,
            ein: Optional[str] = None,
            multiple: bool = False,
            page: Optional[int] = None,
            per_page: Optional[int] = None,
            sort_order: Optional[str] = "desc",
            sort_by: Optional[str] = "created_on"
    ):
        try:
            query = db.query(VehicleEntity)

            if entity_id:
                query = query.filter(VehicleEntity.id == entity_id)
            if entity_name:
                names = [name.strip() for name in str(entity_name).split(",") if name.strip()]
                query = query.filter(or_(
                    *[VehicleEntity.entity_name.ilike(f"%{name}%") for name in names]
                ))
            if owner_id:
                ids = [int(id.strip()) for id in str(owner_id).split(",") if id.strip().isdigit()]
                query = query.filter(or_(
                    *[cast(VehicleEntity.owner_id, String).ilike(f"%{id}%") for id in ids]
                ))
            if entity_status:
                query = query.filter(VehicleEntity.entity_status == entity_status)
            if ein:
                eins = [ein.strip() for ein in str(ein).split(",") if ein.strip()]
                query = query.filter(or_(
                    *[VehicleEntity.ein.ilike(f"%{e}%") for e in eins]
                ))
            if sort_by and hasattr(VehicleEntity, sort_by):
                column = getattr(VehicleEntity, sort_by)
                query = query.order_by(
                    column.desc() if sort_order == "desc" else column.asc()
                )

            if multiple:
                query = query.filter(VehicleEntity.entity_status != VehicleEntityStatus.INACTIVE)
                total_count = query.count()
                if per_page and page:
                    query = query.offset((page - 1) * per_page).limit(per_page)
                return query.all(), total_count
            return query.first()
        except Exception as e:
            logger.error("Error getting vehicle entity: %s", str(e))
            raise e

    def upsert_repair(self, db: Session, repair_data: dict) -> VehicleRepair:
        """Upsert a vehicle repair"""
        try:
            if repair_data.get("id"):
                repair = self.get_repair(db, repair_id=repair_data.get("id"))
                if repair:
                    for key, value in repair_data.items():
                        setattr(repair, key, value)
                    db.commit()
                    db.refresh(repair)
                    return repair
            else:
                repair = VehicleRepair(**repair_data)
                db.add(repair)
                db.commit()
                db.refresh(repair)
                return repair
        except Exception as e:
            logger.error("Error upserting vehicle repair: %s", str(e))
            raise e

    def upsert_dealer(self, db: Session, dealer_data: dict) -> Dealer:
        """Upsert a dealer"""
        try:
            if dealer_data.get("id"):
                dealer = self.get_dealer(db, dealer_id=dealer_data.get("id"))
                if dealer:
                    for key, value in dealer_data.items():
                        setattr(dealer, key, value)
                        db.commit()
                    db.refresh(dealer)
                    return dealer
            else:
                dealer = Dealer(**dealer_data)
                db.add(dealer)
                db.commit()
                db.refresh(dealer)
                return dealer
        except Exception as e:
            logger.error("Error upserting dealer: %s", str(e))
            raise e

    def upsert_vehicle_entity(self, db: Session, entity_data: dict):
        try:
            if entity_data.get("id"):
                Vehicle_entity = self.get_vehicle_entity(
                    db, entity_id=entity_data.get("id")
                )
                if Vehicle_entity:
                    for key, value in entity_data.items():
                        setattr(Vehicle_entity, key, value)
                    db.commit()
                    db.refresh(Vehicle_entity)
                    return Vehicle_entity
            else:
                Vehicle_entity = VehicleEntity(**entity_data)
                db.add(Vehicle_entity)
                db.commit()
                db.refresh(Vehicle_entity)
                return Vehicle_entity
        except Exception as e:
            logger.error("Error upserting vehicle entity: %s", str(e))
            raise e
        
    def finalize_hackup(self, db: Session, vehicle_id: int) -> Vehicle:
        """
        Finalizes the hack-up process for a vehicle.

        This function validates the vehicle's current state, updates its status
        to 'Hacked up', and updates the associated medallion's status to 'Active'.
        It also closes the related BPMN case.

        Args:
            db: The database session.
            vehicle_id: The ID of the vehicle to finalize.

        Returns:
            The updated Vehicle object.
        
        Raises:
            ValueError: If the vehicle is not in a valid state for hack-up completion.
        """
        from app.medallions.services import medallion_service
        from app.medallions.schemas import MedallionStatus
        from app.bpm.services import bpm_service
        vehicle = self.get_vehicles(db, vehicle_id=vehicle_id)

        if not vehicle:
            raise ValueError(f"Vehicle with ID {vehicle_id} not found.")

        # Validation 1: Ensure vehicle is in the correct pre-completion status.
        if vehicle.vehicle_status not in [VehicleStatus.HACK_UP_IN_PROGRESS, VehicleStatus.HACKED_UP]:
            raise ValueError(f"Vehicle is not in a valid state for hack-up completion. Current status: '{vehicle.vehicle_status}'")
        
        # If already hacked up, we can return success without re-doing the work.
        if vehicle.vehicle_status == VehicleStatus.HACKED_UP:
            logger.info(f"Vehicle {vehicle.vin} is already marked as 'Hacked Up'. No action needed.")
            return vehicle

        # Validation 2: Ensure a medallion is assigned.
        if not vehicle.medallion_id:
            raise ValueError("Cannot complete hack-up: No medallion is assigned to this vehicle.")
        
        medallion = medallion_service.get_medallion(db, medallion_id=vehicle.medallion_id)
        if not medallion:
            raise ValueError(f"Assigned medallion with ID {vehicle.medallion_id} not found.")

        # --- Main Logic ---
        
        # 1. Update Vehicle Status
        vehicle = self.upsert_vehicle(db, {
            "id": vehicle.id,
            "vehicle_status": VehicleStatus.HACKED_UP
        })
        logger.info(f"Updated vehicle {vehicle.vin} status to HACKED_UP.")
        
        # 2. Update Medallion Status to Active
        medallion_service.upsert_medallion(db, {
            "id": medallion.id,
            "medallion_status": MedallionStatus.ACTIVE
        })
        logger.info(f"Updated medallion {medallion.medallion_number} status to ACTIVE.")

        # 3. Find and Close the related BPMN Case
        # Assuming the case is linked via a CaseEntity
        case_entity = bpm_service.get_case_entity(db, entity_name="vehicles", identifier_value=str(vehicle.id))
        if case_entity:
            bpm_service.mark_case_as_closed(db, case_entity.id)
            # bpm_service.close_case(db, case_no=case_entity.case_no, notes="Vehicle hack-up process completed successfully via API.")
            logger.info(f"Closed BPMN case {case_entity.case_no} for vehicle {vehicle.vin}.")
        else:
            logger.warning(f"Could not find a corresponding BPMN case for vehicle ID {vehicle.id} to close.")
            
        return vehicle


vehicle_service = VehicleService()
