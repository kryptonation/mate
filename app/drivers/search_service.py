## app/drivers/search_service.py

from datetime import datetime, timedelta
from typing import List

# Third party imports
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import or_, func , and_, exists, not_ 
from sqlalchemy import desc

# Local imports
from app.drivers.models import Driver, TLCLicense, DMVLicense
from app.leases.models import LeaseDriver, Lease
from app.drivers.schemas import DriverStatus
from app.uploads.models import Document
from app.audit_trail.models import AuditTrail
from app.vehicles.models import Vehicle
from app.medallions.models import Medallion
from app.utils.logger import get_logger

logger = get_logger(__name__)

def driver_lease_report(
    db: Session,
    filters: dict,
    sort_by: str,
    sort_order: str,
):
    """Get a list of drivers with their lease expiry dates"""

    try:
        query = db.query(Driver).options(
            joinedload(Driver.tlc_license),
            joinedload(Driver.dmv_license),
        ).join(
            TLCLicense, 
            Driver.tlc_license_number_id == TLCLicense.id,
             isouter=True 
            ).join(
            DMVLicense, 
            Driver.dmv_license_number_id == DMVLicense.id,
            isouter=True 
            ).filter(
            Driver.driver_status != DriverStatus.INACTIVE,
            Driver.driver_status != DriverStatus.IN_PROGRESS
            )
        
        matched_filters = []

        day_in_advance = filters.get("day_in_advance", 0)

        check_date = datetime.now() + timedelta(days=day_in_advance)

        if license_type := filters.get("license_type"):
            if license_type == "tlc_license":
                Driver.tlc_license.has(and_(
              TLCLicense.tlc_license_expiry_date <= check_date.date(),
              TLCLicense.tlc_license_expiry_date >= datetime.now().date()
        )
    )
            elif license_type == "dmv_license":
                query = query.filter(Driver.dmv_license.has(
                    and_(
                    DMVLicense.dmv_license_expiry_date <= check_date.date(),
                    DMVLicense.dmv_license_expiry_date >= datetime.now().date()
                    )
                ))
            matched_filters.append("license_type")


        
        if driver_id:= filters.get("driver_id"):
            driver_ids=[id.strip() for id in driver_id.split(",") if id.strip()]
            query= query.filter(or_(*[Driver.driver_id.like(f"%{id}%") for id in driver_ids]))
            matched_filters.append("driver_id")

        if tlc_license_number:= filters.get("tlc_license_number"):
            tlc_license_numbers=[id.strip() for id in tlc_license_number.split(",") if id.strip()]
            query= query.filter(or_(*[TLCLicense.tlc_license_number.like(f"%{id}%") for id in tlc_license_numbers]))
            matched_filters.append("tlc_license_number")

        if dmv_license_number:= filters.get("dmv_license_number"):
            dmv_license_numbers=[id.strip() for id in dmv_license_number.split(",") if id.strip()]
            query= query.filter(or_(*[DMVLicense.dmv_license_number.like(f"%{id}%") for id in dmv_license_numbers]))
            matched_filters.append("dmv_license_number")

        sort_mapping = {
            "first_name": Driver.first_name,
            "last_name": Driver.last_name,
            "driver_type": Driver.driver_type,
            "tlc_license_number": TLCLicense.tlc_license_number,
            "dmv_license_number": DMVLicense.dmv_license_number,
            "driver_status": Driver.driver_status,
            "created_on": Driver.created_on,
        }

        if sort_by in sort_mapping:
            sort_column = sort_mapping[sort_by]
            query = query.order_by(sort_column.desc() if sort_order == "desc" else sort_column.asc())
        else:
            query = query.order_by(desc(Driver.created_on))

        return query, matched_filters,check_date
    
    except Exception as e:
        logger.info("Error in driver_lease_expiry: %s", e)
        return None, [] , check_date
    
def get_total_items(db: Session, query):
    """Get the total number of items in the query"""
    return db.query(func.count()).select_from(query.subquery()).scalar()

def get_paginated_results(query, page: int, per_page: int):
    """Get paginated results from the query"""
    return query.offset((page - 1) * per_page).limit(per_page).all()
    
def build_driver_query(
    db: Session,
    filters: dict,
    sort_by: str,
    sort_order: str,
):
    """Build a query to search for drivers"""
    query = db.query(Driver).options(
        joinedload(Driver.tlc_license),
        joinedload(Driver.dmv_license),
        joinedload(Driver.lease_drivers).joinedload(LeaseDriver.lease), 
        joinedload(Driver.primary_driver_address),
        joinedload(Driver.secondary_driver_address),
        joinedload(Driver.driver_bank_account)
    ).outerjoin(TLCLicense, Driver.tlc_license_number_id == TLCLicense.id
    ).outerjoin(DMVLicense, Driver.dmv_license_number_id == DMVLicense.id
    ).filter(
        Driver.driver_status.notin_([DriverStatus.IN_PROGRESS])
    )

    matched_filters = []

    if filters.get("is_archived") is not None:
        query = query.filter(Driver.is_archived.is_(filters["is_archived"]))
    else:
        query = query.filter(Driver.is_archived.is_(False))

    if ids := filters.get("driver_lookup_id"):
        driver_ids = [i.strip() for i in ids.split(",")]
        query = query.filter(or_(*[Driver.driver_id.like(f"%{i}%") for i in driver_ids]))
        matched_filters.append("driver_lookup_id")

    if nums := filters.get("tlc_license_number"):
        tlc_nums = [n.strip() for n in nums.split(",")]
        query = query.filter(or_(*[TLCLicense.tlc_license_number.like(f"%{n}%") for n in tlc_nums]))
        matched_filters.append("tlc_license_number")

    if nums := filters.get("dmv_license_number"):
        dmv_nums = [n.strip() for n in nums.split(",")]
        query = query.filter(or_(*[DMVLicense.dmv_license_number.like(f"%{n}%") for n in dmv_nums]))
        matched_filters.append("dmv_license_number")

    if ssn := filters.get("ssn"):
        query = query.filter(Driver.ssn.like(f"%{ssn}"))
        matched_filters.append("ssn")
    if vin := filters.get("vin"):
        query = (
            query
            .join(LeaseDriver, LeaseDriver.driver_id == Driver.driver_id)
            .join(Lease, Lease.id == LeaseDriver.lease_id)
            .join(Vehicle, Lease.vehicle_id == Vehicle.id)
            .filter(Vehicle.vin.ilike(f"%{vin}%"))
        )
        matched_filters.append("vin")
    if medallion_number := filters.get("medallion_number"):
        query = (
        query
        .join(LeaseDriver, LeaseDriver.driver_id == Driver.driver_id)
        .join(Lease, Lease.id == LeaseDriver.lease_id)
        .join(Medallion, Lease.medallion_id == Medallion.id)
        .filter(Medallion.medallion_number.ilike(f"%{medallion_number}%"))
    )
        matched_filters.append("medallion_number")
    if driver_name := filters.get("driver_name"):
        query = query.filter(Driver.full_name.ilike(f"%{driver_name}%"))
        matched_filters.append("driver_name")

    for field, key in [
        (Driver.driver_type, "driver_type"),
        (Driver.driver_status, "driver_status"),
    ]:
        if val := filters.get(key):
            query = query.filter(field == val)
            matched_filters.append(key)

    if d := filters.get("tlc_license_expiry_from"):
        query = query.filter(TLCLicense.tlc_license_expiry_date >= d)
    if d := filters.get("tlc_license_expiry_to"):
        query = query.filter(TLCLicense.tlc_license_expiry_date <= d)
    if d := filters.get("dmv_license_expiry_from"):
        query = query.filter(DMVLicense.dmv_license_expiry_date >= d)
    if d := filters.get("dmv_license_expiry_to"):
        query = query.filter(DMVLicense.dmv_license_expiry_date <= d)

    if has_documents := filters.get("has_documents") is not None:
        doc_exists_clause = exists().where(and_(
            Document.object_lookup_id == Driver.id,
            Document.object_type == "driver"
        ))
        query = query.filter(doc_exists_clause if has_documents else not_(doc_exists_clause))
        matched_filters.append("has_documents")

    if has_vehicle:= filters.get("has_vehicle") is not None:
        if has_vehicle:
            query = query.filter(Driver.lease_drivers.any(LeaseDriver.lease.has(Lease.vehicle_id != None)))
        else:
            query = query.filter(Driver.lease_drivers.any(LeaseDriver.is_active == False))
        matched_filters.append("has_vehicle")

    if has_active_lease := filters.get("has_active_lease") is not None:
        query=query.filter(Driver.lease_drivers.any(LeaseDriver.is_active == True) if has_vehicle else Driver.lease_drivers.any(LeaseDriver.is_active == False))
        matched_filters.append("has_active_lease")


    if val := filters.get("is_drive_locked"):
        query = query.filter(Driver.drive_locked == val)
        matched_filters.append("is_drive_locked")

    if val := filters.get("lease_type"):
        query = query.join(LeaseDriver).join(Lease)
        query = query.filter(Lease.lease_type == val)
        matched_filters.append("lease_type")

    sort_mapping = {
        "first_name": Driver.first_name,
        "last_name": Driver.last_name,
        "driver_type": Driver.driver_type,
        "tlc_license_number": TLCLicense.tlc_license_number,
        "dmv_license_number": DMVLicense.dmv_license_number,
        "tlc_license_expriy": TLCLicense.tlc_license_expiry_date,
        "dmv_license_expriy": DMVLicense.dmv_license_expiry_date,
        "driver_status": Driver.driver_status,
        "created_on": Driver.created_on,
    }

    if sort_by in sort_mapping:
        sort_col = sort_mapping[sort_by]
        logger.info(f"sorting Columnn is {sort_col}")
        query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())
    else:
        query = query.order_by(Driver.updated_on.desc(),Driver.created_on.desc())

    return query, matched_filters

def get_formatted_drivers(drivers: List[Driver], db: Session):
    """Get formatted drivers"""
    drivers_list = []
    current_date = func.current_date()

    for driver in drivers:
        audit_trail = db.query(AuditTrail).filter(AuditTrail.meta_data.contains({"driver_id": driver.id})).count()
        has_documents = db.query(Document).filter(Document.object_lookup_id == driver.id, Document.object_type == "driver").count()
        has_vehicle = db.query(exists().where(
            and_(
                LeaseDriver.driver_id == driver.driver_id,
                Lease.id == LeaseDriver.lease_id,
                Vehicle.id == Lease.vehicle_id,
                Lease.is_active == True
            )
        )).scalar()

        has_active_lease = db.query(exists().where(
            and_(
                LeaseDriver.driver_id == driver.driver_id,
                Lease.id == LeaseDriver.lease_id,
                Lease.lease_start_date <= current_date,
                Lease.is_active == True,
                or_(
                    Lease.lease_end_date >= current_date,
                    Lease.lease_end_date.is_(None)
                )
            )
        )).scalar()

        drivers_list.append({
            "driver_details": {
                "driver_id": driver.id,
                "driver_lookup_id": driver.driver_id,
                "first_name": driver.first_name,
                "middle_name": driver.middle_name,
                "last_name": driver.last_name,
                "full_name": driver.full_name,
                "driver_type": driver.driver_type,
                "driver_status": driver.driver_status,
                "driver_ssn": f"XXX-XX-{driver.ssn[-4:]}",
                "dob": driver.dob,
                "phone_number_1": driver.phone_number_1,
                "phone_number_2": driver.phone_number_2,
                "email_address": driver.email_address,
                "primary_emergency_contact_person": driver.primary_emergency_contact_person,
                "primary_emergency_contact_relationship": driver.primary_emergency_contact_relationship,
                "primary_emergency_contact_number": driver.primary_emergency_contact_number,
                "additional_emergency_contact_person": driver.additional_emergency_contact_person,
                "additional_emergency_contact_relationship": driver.additional_emergency_contact_relationship,
                "additional_emergency_contact_number": driver.additional_emergency_contact_number,
                "violation_due_at_registration": driver.violation_due_at_registration,
                "is_drive_locked": driver.drive_locked,
                "has_audit_trail": bool(audit_trail),  # Default to True as requested
            },
            "dmv_license_details": {
                "is_dmv_license_active": bool(driver.dmv_license),
                "dmv_license_number": driver.dmv_license.dmv_license_number if driver.dmv_license else None,
                "dmv_license_issued_state": driver.dmv_license.dmv_license_issued_state if driver.dmv_license else None,
                "dmv_license_expiry_date": driver.dmv_license.dmv_license_expiry_date if driver.dmv_license else None,
            },
            "tlc_license_details": {
                "is_tlc_license_active": bool(driver.tlc_license),
                "tlc_license_number": driver.tlc_license.tlc_license_number if driver.tlc_license else None,
                "tlc_license_expiry_date": driver.tlc_license.tlc_license_expiry_date if driver.tlc_license else None,
            },
            "primary_address_details": {
                "address_line_1": driver.primary_driver_address.address_line_1 if driver.primary_driver_address else None,
                "address_line_2": driver.primary_driver_address.address_line_2 if driver.primary_driver_address else None,
                "city": driver.primary_driver_address.city if driver.primary_driver_address else None,
                "state": driver.primary_driver_address.state if driver.primary_driver_address else None,
                "zip": driver.primary_driver_address.zip if driver.primary_driver_address else None,
                "latitude": driver.primary_driver_address.latitude if driver.primary_driver_address else None,
                "longitude": driver.primary_driver_address.longitude if driver.primary_driver_address else None
            },
            "secondary_address_details": {
                "latitude": driver.secondary_driver_address.latitude if driver.secondary_driver_address else None,
                "longitude": driver.secondary_driver_address.longitude if driver.secondary_driver_address else None
            },
            "payee_details": {
                "pay_to_mode": driver.pay_to_mode,
                "bank_name": driver.driver_bank_account.bank_name if driver.driver_bank_account else None,
                "bank_account_number": driver.driver_bank_account.bank_account_number if driver.driver_bank_account else None,
                "address_line_1": "",
                "address_line_2": "",
                "city": "",
                "state": "",
                "zip": "",
                "pay_to": driver.pay_to,
            },
            "lease_info": {
                "has_active_lease": has_active_lease,
                "lease_type": driver.lease_drivers[0].lease.lease_type if driver.lease_drivers else None,
            },
            "has_documents": has_documents,
            "has_vehicle": has_vehicle,
            "is_archived": driver.is_archived
        })

    return drivers_list

