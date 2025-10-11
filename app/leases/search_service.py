### app/leases/search_service.py

# Third party imports
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func
from app.medallions.utils import format_medallion_response

# Local imports
from app.leases.models import Lease, LeaseDriver, LeaseDriverDocument

def get_active_leases(db: Session):
    """Get all active leases"""
    return db.query(Lease).options(
        joinedload(Lease.medallion),
        joinedload(Lease.vehicle).joinedload("registrations"),
        joinedload(Lease.lease_driver).joinedload(LeaseDriver.driver).joinedload("tlc_license"),
        joinedload(Lease.lease_driver).joinedload(LeaseDriver.driver).joinedload("dmv_license"),
        joinedload(Lease.lease_driver).joinedload("documents")
    ).filter(Lease.is_active.is_(True)).all()

def format_lease_response(db: Session, lease):
    """Format a lease response"""
    lease_details = {
        "lease_id": lease.lease_id,
        "lease_id_pk": lease.id,
        "medallion_number": lease.medallion.medallion_number if lease.medallion else None,
        "vehicle_vin_number": lease.vehicle.vin if lease.vehicle else None,
        "vehicle_plate_number": lease.vehicle.registrations[0].plate_number if lease.vehicle and lease.vehicle.registrations else "",
        "lease_date": lease.lease_end_date.strftime("%Y-%m-%d") if lease.lease_end_date else None,
        "lease_type":lease.lease_type,
        "driver": [],
        "has_documents": False,
    }

    medallion = format_medallion_response(lease.medallion) if lease.medallion else None
    lease_details["medallion_owner"] = medallion["medallion_owner"] if medallion else None

    for lease_driver in lease.lease_driver:
        if not lease_driver.is_active:
            continue

        documents_count = len(lease_driver.documents)
        if documents_count > 0:
            lease_details["has_documents"] = True

        driver = lease_driver.driver
        lease_details["driver_lease_id"] = lease_driver.id
        lease_details["driver"].append({
            "driver_id_pk": driver.id,
            "tlc_license_no": driver.tlc_license.tlc_license_number if driver.tlc_license else None,
            "dmv_license_no": driver.dmv_license.dmv_license_number if driver.dmv_license else None,
            "ssn": driver.ssn,
            "phone_number": driver.phone_number_1,
            "driver_id": driver.driver_id,
            "driver_name": f"{driver.first_name} {driver.last_name}",
            "is_driver_manager": bool(lease_driver.documents)
        })

    return lease_details

def format_lease_export(db: Session, lease):
    """Format a lease response"""
    lease_details = {
        "lease_id": lease.lease_id,
        "lease_id_pk": lease.id,
        "medallion_number": lease.medallion.medallion_number if lease.medallion else None,
        "vehicle_vin_number": lease.vehicle.vin if lease.vehicle else None,
        "vehicle_plate_number": lease.vehicle.registrations[0].plate_number if lease.vehicle and lease.vehicle.registrations else "",
        "lease_date": lease.lease_end_date.strftime("%Y-%m-%d") if lease.lease_end_date else None,
        "lease_type": lease.lease_type,
        "driver_id":None ,
        "tlc_license_no": None,
        "dmv_license_no": None,
        "ssn": None,
        "phone_number": None,
        "driver_name": None,
        "is_driver_manager": None,
        "has_documents": False,
    }

    for lease_driver in lease.lease_driver:
        if not lease_driver.is_active:
            continue

        documents_count = len(lease_driver.documents)
        if documents_count > 0:
            lease_details["has_documents"] = True

        driver = lease_driver.driver
        lease_details["driver_lease_id"] = lease_driver.id
        lease_details["driver_id"] = driver.driver_id
        lease_details["tlc_license_no"] = driver.tlc_license.tlc_license_number
        lease_details["dmv_license_no"] = driver.dmv_license.dmv_license_number
        lease_details["ssn"] = driver.ssn
        lease_details["phone_number"] = driver.phone_number_1
        lease_details["driver_name"] = f"{driver.first_name} {driver.last_name}"
        lease_details["is_driver_manager"] = bool(lease_driver.documents)
        break


    return lease_details