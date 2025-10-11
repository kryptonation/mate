### app/vehicles/models.py

# Third party imports
from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

# Local imports
from app.core.db import Base
from app.ledger.models import DailyReceipt
from app.users.models import AuditMixin
from app.utils.general import generate_random_6_digit
from app.vehicles.schemas import VehicleEntityStatus


class Dealer(Base, AuditMixin):
    """
    Dealer model
    """

    __tablename__ = "dealers"
    id = Column(
        Integer, primary_key=True, nullable=False, comment="Primary Key for Vehicles"
    )
    dealer_name = Column(String(255), nullable=True, comment="Name of the dealer")
    dealer_bank_name = Column(
        String(255), nullable=True, comment="Name of the dealer bank name"
    )
    dealer_bank_account_number = Column(
        String(50), nullable=True, comment="Name of the dealer bank name"
    )
    vehicle = relationship(
        "Vehicle", back_populates="dealer", foreign_keys="Vehicle.dealer_id"
    )


class VehicleEntity(Base, AuditMixin):
    """
    Vehicle Entity model
    """

    __tablename__ = "vehicle_entity"

    id = Column(Integer, primary_key=True, nullable=False)
    entity_name = Column(String(255), nullable=True)
    owner_id = Column(
        Integer, default=generate_random_6_digit, unique=True, nullable=True
    )
    entity_status = Column(
        String(255), default=VehicleEntityStatus.INACTIVE, nullable=True
    )
    ein = Column(String(255), nullable=True)
    entity_address_id = Column(Integer, ForeignKey("address.id"), nullable=True)
    contact_number = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)

    owner_address = relationship(
        "Address", back_populates="vehicle_entity", foreign_keys=[entity_address_id]
    )
    vehicles = relationship(
        "Vehicle", back_populates="vehicle_entity", foreign_keys="Vehicle.entity_id"
    )


class VehicleInspection(Base, AuditMixin):
    """
    Vehicle Inspection model
    """

    __tablename__ = "vehicle_inspections"

    id = Column(
        Integer,
        primary_key=True,
        nullable=False,
        comment="Primary Key for Vehicle Inspections",
    )
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id"),
        nullable=False,
        comment="Foreign Key to Vehicle table",
    )

    mile_run = Column(
        Boolean, nullable=True, comment="Indicates if a mile run was completed"
    )
    inspection_date = Column(Date, nullable=True, comment="Date of inspection")
    inspection_time = Column(String(255), nullable=True, comment="Time of inspection")
    odometer_reading_date = Column(
        Date, nullable=True, comment="Date of odometer reading"
    )
    odometer_reading_time = Column(
        String(255), nullable=True, comment="Time of odometer reading"
    )
    odometer_reading = Column(
        Integer, nullable=True, comment="Odometer reading at the time of inspection"
    )
    logged_date = Column(
        Date, nullable=True, comment="Date when the inspection details were logged"
    )
    logged_time = Column(
        String(255),
        nullable=True,
        comment="Time when the inspection details were logged",
    )
    inspection_fee = Column(
        Float, nullable=True, comment="Fee charged for the inspection"
    )
    result = Column(
        Enum("Pass", "Fail", name="inspection_result"),
        nullable=True,
        comment="Result of the inspection",
    )
    next_inspection_due_date = Column(
        Date, nullable=True, comment="Date when the next inspection is due"
    )
    status = Column(String(50), nullable=False, comment="Registration Status")
    # Relationship with the Vehicle
    vehicle = relationship("Vehicle", back_populates="inspections")

    def to_dict(self):
        """Convert VehicleInspection object to a dictionary"""
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "mile_run": self.mile_run,
            "inspection_date": self.inspection_date,
            "inspection_time": self.inspection_time,
            "odometer_reading_date": self.odometer_reading_date,
            "odometer_reading_time": self.odometer_reading_time,
            "odometer_reading": self.odometer_reading,
            "logged_date": self.logged_date,
            "logged_time": self.logged_time,
            "inspection_fee": self.inspection_fee,
            "result": self.result,
            "next_inspection_due_date": self.next_inspection_due_date,
            "status": self.status,
        }


class VehicleRegistration(Base, AuditMixin):
    """
    Vehicle Registration model
    """

    __tablename__ = "vehicle_registration"

    id = Column(
        Integer,
        primary_key=True,
        nullable=False,
        comment="Primary Key for Vehicle Registration",
    )
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id"),
        nullable=False,
        comment="Foreign Key to Vehicle table",
    )
    registration_date = Column(Date, nullable=False, comment="Date of registration")
    registration_expiry_date = Column(
        Date, nullable=False, comment="Expiry date of the registration"
    )
    registration_fee = Column(
        Float, nullable=True, comment="Fee paid for the registration"
    )
    registration_state = Column(String(2), nullable=True, comment="Registration State")
    registration_class = Column(String(2), nullable=True, comment="Registration Class")
    plate_number = Column(String(255), nullable=True, comment="Vehicle plate number")
    status = Column(String(50), nullable=False, comment="Registration Status")
    # Back-populates the relationship with Vehicle
    vehicle = relationship("Vehicle", back_populates="registrations")

    def to_dict(self):
        """Convert VehicleRegistration object to a dictionary"""
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "registration_date": self.registration_date,
            "registration_expiry_date": self.registration_expiry_date,
            "registration_fee": self.registration_fee,
            "registration_state": self.registration_state,
            "registration_class": self.registration_class,
            "plate_number": self.plate_number,
            "status": self.status,
        }


class VehicleHackUp(Base, AuditMixin):
    """
    Vehicle HackUp model
    """

    __tablename__ = "vehicle_hackups"

    id = Column(
        Integer,
        primary_key=True,
        nullable=False,
        comment="Primary Key for Vehicle HackUp",
    )
    vehicle_id = Column(
        Integer,
        ForeignKey("vehicles.id"),
        nullable=False,
        comment="Foreign Key to Vehicles table",
    )
    tpep_provider = Column(
        String(255), nullable=True, comment="TPEP Type selected by the user"
    )
    configuration_type = Column(
        String(255), nullable=True, comment="Configuration type Camera or Partition"
    )
    is_paint_completed = Column(
        Boolean, nullable=True, comment="Has painting completed"
    )
    paint_completed_date = Column(
        Date, nullable=True, comment="Date when paint was completed"
    )
    paint_completed_charges = Column(
        Integer, nullable=True, comment="Paint completion charges"
    )
    paint_status = Column(String(50), nullable=True, comment="Paint Status")
    is_camera_installed = Column(
        Boolean, nullable=True, comment="Has camera got installed"
    )
    camera_type = Column(String(255), nullable=True, comment="Type of camera installed")
    camera_installed_date = Column(
        Date, nullable=True, comment="Date when camera was installed"
    )
    camera_installed_charges = Column(
        Integer, nullable=True, comment="Camera installation charges"
    )
    camera_status = Column(String(50), nullable=True, comment="Camera Status")
    is_partition_installed = Column(
        Boolean, nullable=True, comment="Has partition got installed"
    )
    partition_type = Column(
        String(255), nullable=True, comment="Type of partition installed"
    )
    partition_installed_date = Column(
        Date, nullable=True, comment="Date when partition was installed"
    )
    partition_installed_charges = Column(
        Integer, nullable=True, comment="partition installation charges"
    )
    partition_status = Column(String(50), nullable=True, comment="Partition Status")
    is_meter_installed = Column(
        Boolean, nullable=True, comment="Has meter been installed"
    )
    meter_installed_date = Column(
        Date, nullable=True, comment="Date when the meter was installed"
    )
    meter_type = Column(String(255), nullable=True, comment="Type of meter installed")
    meter_serial_number = Column(
        String(255), nullable=True, comment="Serial number of the installed meter"
    )
    meter_installed_charges = Column(
        Integer, nullable=True, comment="Meter installation charges"
    )
    meter_status = Column(String(50), nullable=True, comment="Meter Status")
    is_rooftop_installed = Column(
        Boolean, nullable=True, comment="Whether the rooftop is installed"
    )
    rooftop_type = Column(
        String(255), nullable=True, comment="Type of rooftop installed"
    )
    rooftop_installed_date = Column(
        Date, nullable=True, comment="Date when the rooftop was installed"
    )
    rooftop_installation_charges = Column(
        Integer, nullable=True, comment="Rooftop installation charges"
    )
    rooftop_status = Column(String(50), nullable=True, comment="meter Status")
    status = Column(String(50), nullable=False, comment="HackUp Status")
    # Paint
    paint_from_location = Column(
        String(50), nullable=True, comment="Pickup location for paint"
    )
    paint_to_location = Column(
        String(50), nullable=True, comment="Drop location for paint"
    )

    # Camera
    camera_from_location = Column(
        String(50), nullable=True, comment="Pickup location for camera"
    )
    camera_to_location = Column(
        String(50), nullable=True, comment="Drop location for camera"
    )

    # Partition
    partition_from_location = Column(
        String(50), nullable=True, comment="Pickup location for partition"
    )
    partition_to_location = Column(
        String(50), nullable=True, comment="Drop location for partition"
    )

    # Meter
    meter_from_location = Column(
        String(50), nullable=True, comment="Pickup location for meter"
    )
    meter_to_location = Column(
        String(50), nullable=True, comment="Drop location for meter"
    )

    # Rooftop
    rooftop_from_location = Column(
        String(50), nullable=True, comment="Pickup location for rooftop"
    )
    rooftop_to_location = Column(
        String(50), nullable=True, comment="Drop location for rooftop"
    )

    # Relationships
    vehicle = relationship("Vehicle", back_populates="hackups")

    def to_dict(self):
        """Convert VehicleHackUp object to a dictionary"""
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "tpep_type": self.tpep_provider,
            "configuration_type": self.configuration_type,
            "is_paint_completed": self.is_paint_completed,
            "paint_completed_date": self.paint_completed_date,
            "paint_completed_charges": self.paint_completed_charges,
            "is_camera_installed": self.is_camera_installed,
            "camera_type": self.camera_type,
            "camera_installed_date": self.camera_installed_date,
            "camera_installed_charges": self.camera_installed_charges,
            "is_partition_installed": self.is_partition_installed,
            "partition_type": self.partition_type,
            "partition_installed_date": self.partition_installed_date,
            "partition_installed_charges": self.partition_installed_charges,
            "is_meter_installed": self.is_meter_installed,
            "meter_type": self.meter_type,
            "meter_serial_number": self.meter_serial_number,
            "meter_installed_charges": self.meter_installed_charges,
            "is_rooftop_installed": self.is_rooftop_installed,
            "rooftop_type": self.rooftop_type,
            "rooftop_installed_date": self.rooftop_installed_date,
            "rooftop_installation_charges": self.rooftop_installation_charges,
            "status": self.status,
            "paint_status": self.paint_status,
            "paint_from_location": self.paint_from_location,
            "paint_to_location": self.paint_to_location,
            "camera_status": self.camera_status,
            "camera_from_location": self.camera_from_location,
            "camera_to_location": self.camera_to_location,
            "partition_status": self.partition_status,
            "partition_from_location": self.partition_from_location,
            "partition_to_location": self.partition_to_location,
            "meter_status": self.meter_status,
            "meter_from_location": self.meter_from_location,
            "meter_to_location": self.meter_to_location,
            "rooftop_status": self.rooftop_status,
            "rooftop_from_location": self.rooftop_from_location,
            "rooftop_to_location": self.rooftop_to_location,
            "created_on": self.created_on,
            "updated_on": self.updated_on,
        }


class Vehicle(Base, AuditMixin):
    """
    Vehicle model
    """

    __tablename__ = "vehicles"

    id = Column(
        Integer, primary_key=True, nullable=False, comment="Primary Key for Vehicles"
    )
    vin = Column(String(64), nullable=True, comment="Vehicle Identification Number")
    make = Column(String(45), nullable=True, comment="Make of the vehicle")
    model = Column(String(45), nullable=True, comment="Model of the vehicle")

    year = Column(String(4), nullable=True)
    cylinders = Column(Integer, nullable=True)
    color = Column(String(50), nullable=True)
    vehicle_type = Column(
        String(255), nullable=True, comment="Would be either Regular or Wav"
    )
    is_hybrid = Column(Boolean, nullable=True, comment="Is the vehicle hybrid or not")
    base_price = Column(
        Float, nullable=True, default=0.0, comment="Base price of the vehicle"
    )
    sales_tax = Column(
        Float, nullable=True, default=0.0, comment="Sales tax applied to the vehicle"
    )
    vehicle_total_price = Column(
        Integer, nullable=True, comment="Total cost of the vehicle"
    )
    vehicle_true_cost = Column(
        Integer,
        nullable=True,
        comment="True cost typically could mean that hack up costs and other miscellaneous costs are accounted",
    )
    vehicle_hack_up_cost = Column(
        Integer, nullable=True, comment="Total hack up cost of the vehicle"
    )
    vehicle_lifetime_cap = Column(
        Integer,
        nullable=True,
        comment="Cap calculated off between true cost or tlc cap",
    )

    # TODO: This may be removed, keeping it for now
    vehicle_office = Column(String(255), nullable=True, comment="Vehicle Office")
    is_delivered = Column(
        Boolean, nullable=True, comment="Is the vehicle hybrid or not"
    )
    expected_delivery_date = Column(
        Date, nullable=True, comment="The expected delivery date of the vehicle"
    )
    delivery_location = Column(
        String(255), nullable=True, comment="Delivery location of the vehicle"
    )
    delivery_note = Column(Text, nullable=True, comment="Delivery note for the vehicle")
    is_insurance_procured = Column(
        Boolean, nullable=True, comment="The insurance procured for the vehicle"
    )
    tlc_hackup_inspection_date = Column(
        Date, nullable=True, comment="TLC Hackup Inspection Date"
    )
    is_medallion_assigned = Column(
        Boolean, nullable=True, comment="Is a medallion allocated to the vehicle"
    )
    vehicle_status = Column(
        String(50),
        nullable=True,
        comment="Status of the vehicle - one among Registration In Progress, Registered, Delivered, Hacked, Active & Inactive",
    )
    entity_id = Column(
        Integer,
        ForeignKey("vehicle_entity.id"),
        nullable=True,
        comment="Foreign Key to Entity Table",
    )
    dealer_id = Column(
        Integer,
        ForeignKey("dealers.id"),
        nullable=True,
        comment="Foreign Key to dealer Table",
    )
    medallion_id = Column(
        Integer,
        ForeignKey("medallions.id"),
        nullable=True,
        comment="Foreign Key to medallion Table",
    )
    tsp = Column(
        String(255), nullable=True, comment="Taxi and Limousine Commission (TLC) Permit"
    )
    security_type = Column(String(255), nullable=True, comment="Security Type")
    camera_type = Column(String(50), nullable=True, comment="Camera Type")
    paint_address = Column(String(255), nullable=True, comment="Paint Address")
    camera_address = Column(String(255), nullable=True, comment="Camera Address")
    metro_address = Column(String(255), nullable=True, comment="Metro Address")
    meter_type = Column(String(50), nullable=True, comment="Meter Type")
    rooftop_address = Column(String(255), nullable=True, comment="Rooftop Address")
    dmv_registration_address = Column(
        String(255), nullable=True, comment="DMV Registration Address"
    )
    tlc_inspection_address = Column(
        String(255), nullable=True, comment="TLC Inspection Address"
    )
    delay_reason = Column(Text, nullable=True, comment="Delay Reason")
    partition_type = Column(String(50), nullable=True, comment="Partition Type")
    partition_address = Column(String(255), nullable=True, comment="Partition Address")
    rooftop_type = Column(String(50), nullable=True, comment="Rooftop Type")

    vehicle_entity = relationship(
        "VehicleEntity", back_populates="vehicles", foreign_keys=[entity_id]
    )
    dealer = relationship("Dealer", back_populates="vehicle", foreign_keys=[dealer_id])

    hackups = relationship(
        "VehicleHackUp",
        back_populates="vehicle",
    )

    registrations = relationship("VehicleRegistration", back_populates="vehicle")

    inspections = relationship("VehicleInspection", back_populates="vehicle")

    lease = relationship(
        "Lease",
        back_populates="vehicle",
    )

    medallions = relationship("Medallion", back_populates="vehicle")

    repairs = relationship("VehicleRepair", back_populates="vehicle")

    daily_receipts = relationship("DailyReceipt", back_populates="vehicle")
    ledger_entries = relationship("LedgerEntry", back_populates="vehicle")

    def to_dict(self):
        """Convert Vehicle object to a dictionary"""
        return {
            "vehicle_id": self.id,
            "vin": self.vin,
            "make": self.make,
            "model": self.model,
            "year": self.year,
            "cylinders": self.cylinders,
            "color": self.color,
            "vehicle_type": self.vehicle_type,
            "is_hybrid": self.is_hybrid,
            "base_price": self.base_price,
            "sales_tax": self.sales_tax,
            "vehicle_office": self.vehicle_office,
            "is_delivered": self.is_delivered,
            "expected_delivery_date": self.expected_delivery_date,
            "delivery_location": self.delivery_location,
            "delivery_note": self.delivery_note,
            "is_insurance_procured": self.is_insurance_procured,
            "tlc_hackup_inspection_date": self.tlc_hackup_inspection_date,
            "is_medallion_assigned": self.is_medallion_assigned,
            "vehicle_status": self.vehicle_status,
            "entity_id": self.entity_id,
            "entity_name": self.vehicle_entity.entity_name
            if self.vehicle_entity
            else None,
            "dealer_id": self.dealer_id,
            "medallion_id": self.medallion_id,
            "created_on": self.created_on,
            "updated_on": self.updated_on,
        }


class VehicleRepair(Base, AuditMixin):
    """Vehicle Repair model"""

    __tablename__ = "vehicle_repairs"

    id = Column(Integer, primary_key=True, nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)

    # Invoice details
    invoice_date = Column(Date, nullable=True)
    invoice_amount = Column(Float, nullable=True)

    # Vehicle in/out details
    vehicle_in_date = Column(Date, nullable=True)
    vehicle_in_time = Column(String(10), nullable=True)
    vehicle_out_date = Column(Date, nullable=True)
    vehicle_out_time = Column(String(10), nullable=True)

    # Payment details
    repair_paid_by = Column(String(10), nullable=True)  # BAT or Driver

    # Service details
    next_service_due_by = Column(Date, nullable=True)
    remarks = Column(Text, nullable=True)

    # Status
    status = Column(String(20), nullable=False, default="In Progress")

    # Relationships
    vehicle = relationship("Vehicle", back_populates="repairs")

    def to_dict(self):
        """Convert VehicleRepair object to a dictionary"""
        return {
            "id": self.id,
            "vehicle_id": self.vehicle_id,
            "invoice_date": self.invoice_date,
            "invoice_amount": self.invoice_amount,
            "vehicle_in_date": self.vehicle_in_date,
            "vehicle_in_time": self.vehicle_in_time,
            "vehicle_out_date": self.vehicle_out_date,
            "vehicle_out_time": self.vehicle_out_time,
            "repair_paid_by": self.repair_paid_by,
            "next_service_due_by": self.next_service_due_by,
            "remarks": self.remarks,
            "status": self.status,
            "created_on": self.created_on,
            "updated_on": self.updated_on,
        }


# Add to Vehicle model
Vehicle.repairs = relationship("VehicleRepair", back_populates="vehicle")
