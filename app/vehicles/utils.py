### app/vehicles/utils.py

import math

from app.medallions.utils import format_medallion_response
from app.vehicles.schemas import VehicleStatus
from app.medallions.schemas import MedallionStatus

def format_vehicle_response(
        vehicle, has_documents = None, has_medallion = None,
        is_driver_associated = None, registration_details = None,
        vehicle_hackup = None, vehicle_can_rehack = None, has_audit_trail= None
):
    """Helper function to format vehicle response"""
    return {
        "vehicle_id": vehicle.id,
        "vin": vehicle.vin,
        "make": vehicle.make,
        "model": vehicle.model,
        "year": vehicle.year,
        "vehicle_type": vehicle.vehicle_type,
        "color": vehicle.color,
        "cylinders": vehicle.cylinders,
        "entity_name": vehicle.vehicle_entity.entity_name if vehicle.vehicle_entity else "",
        "has_documents": has_documents,
        "has_medallion": has_medallion,
        "is_driver_associated": is_driver_associated,
        "registration_details": {
            'registration_expiry_date': vehicle.registrations[-1].registration_expiry_date if vehicle.registrations else "",
            'registration_date': vehicle.registrations[-1].registration_date if vehicle.registrations else "",
            'plate_number': vehicle.registrations[-1].plate_number if vehicle.registrations else "",
            'registration_state': vehicle.registrations[-1].registration_state if vehicle.registrations else "",
        },
        "vehicle_status": vehicle.vehicle_status,
        "vehicle_hackups": True if vehicle_hackup else False,
        "can_vehicle_rehack": vehicle_can_rehack,
        "audit_trail": has_audit_trail,
        "fuel": None,
        "partition_installed": vehicle_hackup.is_partition_installed if vehicle_hackup else None,
        "partition_selected": vehicle_hackup.partition_type if vehicle_hackup else None
    }

def formate_vehicle_hackup(vehicle_hackup, medallion, vehicle):

    if vehicle.vehicle_status == VehicleStatus.AVAILABLE and vehicle.is_medallion_assigned is False:
        return {
            "vehicle_details": format_vehicle_response(vehicle)
        }

    hackup_details = {
        "vehicle_details": format_vehicle_response(vehicle),
        "medallion_details": format_medallion_response(medallion),
    }

    if vehicle.vehicle_status == VehicleStatus.AVAILABLE and vehicle.is_medallion_assigned is True:
        return hackup_details

    def safe_get(attr):
        return getattr(vehicle_hackup, attr, None) if vehicle_hackup else None

    hackup_data_fields = [
        "id", "vehicle_id", "is_active", "tpep_type", "configuration_type",
        "is_paint_completed", "paint_completed_date", "paint_completed_charges",
        "is_camera_installed", "camera_type", "camera_installed_date", "camera_installed_charges",
        "is_partition_installed", "partition_type", "partition_installed_date", "partition_installed_charges",
        "is_meter_installed", "meter_type", "meter_serial_number", "meter_installed_charges", "meter_installed_date",
        "is_rooftop_installed", "rooftop_type", "rooftop_installed_date", "rooftop_installation_charges",
        "status", "created_on"
    ]

    hackup_details["hackup_data"] = {
        field if field != "id" else "hackup_id": safe_get(field)
        for field in hackup_data_fields
    }

    return hackup_details

def format_vehicle_entity(entity):
    if not entity:
        return {}
    return {
        "id": entity.id,
        "entity_name": entity.entity_name if entity.entity_name else "",
        "owner_id": entity.owner_id if entity.owner_id else "",
        "ein": entity.ein if entity.ein else "",
        "owner_id": entity.owner_id if entity.owner_id else None,
        "status": entity.entity_status if entity.entity_status else None,
        "entity_address": entity.owner_address if entity.owner_address else {},
        "contact_number":entity.contact_number if entity.contact_number else "",
        "contact_email": entity.contact_email if entity.contact_email else ""
    }

def get_vehicles_from_owner(owner , page, per_page):

    page = int(page)
    per_page = int(per_page)

    start = (page - 1) * per_page
    end = start + per_page

    paginated_vehicles = [
        {
            "id": vehicle.id,
            "vin": vehicle.vin,
            "make": vehicle.make,
            "model": vehicle.model,
            "year": vehicle.year,
            "type": vehicle.vehicle_type,
            "color": vehicle.color,
            "status": vehicle.vehicle_status
        }
        for vehicle in owner.vehicles[start:end]
    ]

    total_count = len(owner.vehicles)

    return{
        "items": paginated_vehicles,
        "total_count": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": math.ceil(total_count / per_page)
    }