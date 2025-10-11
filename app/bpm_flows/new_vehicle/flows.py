## app/bpm_flows/new_vehicle/flows.py

# Standard imports
from datetime import datetime

# Third party imports
from fastapi import HTTPException

# Local imports
from app.utils.logger import get_logger
from app.bpm.step_info import step
from app.audit_trail.services import audit_trail_service
from app.bpm.services import bpm_service
from app.vehicles.services import vehicle_service
from app.vehicles.schemas import VehicleStatus
from app.uploads.services import upload_service
from app.bpm_flows.allocate_medallion_vehicle.utils import format_vehicle_details

logger = get_logger(__name__)
entity_mapper = {
    "VEHICLE": "vehicles",
    "VEHICLE_IDENTIFIER": "id",
}

@step(step_id="121", name="Fetch - Vehicle Documents", operation='fetch')
def fetch_vehicle_documents(db, case_no, case_params=None):
    """
    Fetch the vehicle information for the new vehicle step
    """
    try:
        logger.info("Fetch vehicle information")
        vehicle = None
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        if case_entity :
            vehicle = vehicle_service.get_vehicles(
                db, vehicle_id=int(case_entity.identifier_value)
            )
        
        if not vehicle:
            if case_params and case_params.get("object_name") == "entityId":
                vehicle = vehicle_service.upsert_vehicle(
                    db, {"entity_id": int(case_params['object_lookup'])}
                )
                
        if not vehicle:
            return {}
        
        vehicle_invoice = upload_service.get_documents(db=db , object_type="vehicle",
                                            object_id=vehicle.id,document_type="vehicle_invoice")
        
        if not case_entity:
            case_entity = bpm_service.create_case_entity(
                db=db, case_no=case_no,
                entity_name=entity_mapper["VEHICLE_IDENTIFIER"],
                identifier=entity_mapper["VEHICLE_IDENTIFIER"],
                identifier_value=str(vehicle.id)
            )
        
        return {
            "documents":[vehicle_invoice],
            "document_type":["vehicle_invoice"],
            "required_documents":["vehicle_invoice"],
            "object_type":"vehicle",
            "object_id":vehicle.id
        }
    except Exception as e:
        logger.error("Error fetching vehicle information: %s", e)
        raise e

@step(step_id="121", name="Process - Upload vehicle Documents", operation='process')
def upload_vehicle_documents(db, case_no, step_data):
    """
    Process the vehicle information for the new vehicle step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        logger.info("Nothing TO DO Here")
    
        return "Ok"
    except Exception as e:
        logger.error("Error creating or updating vehicle information: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

@step(step_id="122", name="Process - Enter Vehilce Details", operation='process')
def process_vehicle_details(db, case_no, step_data):
    """
    Process the vehicle delivery details for the new vehicle step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        if not case_entity:
            return {}

        vehicle = vehicle_service.get_vehicles(
            db, vehicle_id=int(case_entity.identifier_value)
        )

        if not vehicle:
            raise ValueError("Vehicle not found")
        
        vehicle_data = vehicle_service.upsert_vehicle(db=db , vehicle_data={
            "id": vehicle.id,
            **step_data
        })

        if not vehicle_data:
            raise ValueError("Error updating vehicle")
        
        return "Ok"
    except Exception as e:
        logger.error("Error processing vehicle delivery details: %s", e)
        raise e

@step(step_id="122", name="fetch - Vehilce Details", operation='fetch')
def fetch_vehicle_details(db, case_no, step_data):
    """
    Fetch the vehicle delivery details for the new vehicle step
    """
    try:
        logger.info("Fetch vehicle delivery details")
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        if not case_entity:
            return {}

        vehicle = vehicle_service.get_vehicles(
            db, vehicle_id=int(case_entity.identifier_value)
        )
        if not vehicle:
            return {}
        
        return format_vehicle_details(vehicle)
    except Exception as e:
        logger.error("Error fetching vehicle delivery details: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    
@step(step_id="123", name="Process - vehicle delivery details", operation='process')
def process_vehicle_delivery_details(db, case_no, step_data):
    """
    Process the vehicle delivery details for the new vehicle step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        if not case_entity:
            return {}

        vehicle = vehicle_service.get_vehicles(
            db, vehicle_id=int(case_entity.identifier_value)
        )

        if not vehicle:
            raise ValueError("Vehicle not found")
        
        vehicle_data = vehicle_service.upsert_vehicle(db=db , vehicle_data={
            "id": vehicle.id,
            "vehicle_status": VehicleStatus.AVAILABLE,
            **step_data
        })

        if not vehicle_data:
            raise ValueError("Error updating vehicle")
        
        cases = bpm_service.get_cases(db=db , case_no= case_no ,multiple=True)
        if cases:
            case_ids = [case.id for case in cases]
            audits = audit_trail_service.get_audit_trail_by_case_ids(db, case_ids)
            for audit in audits:
                audit_trail_service.update_audit_trail(db=db , audit_id=audit.id , update_data={"meta_data": {"vehicle_id": vehicle_data.id}})
        
        return "Ok"
    except Exception as e:
        logger.error("Error processing vehicle delivery details: %s", e)
        raise e

@step(step_id="123", name="Fetch - vehicle delivery details", operation='fetch')
def fetch_vehicle_delivery_details(db, case_no, step_data):
    """
    Fetch the vehicle delivery details for the new vehicle step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        if not case_entity:
            return {}

        vehicle = vehicle_service.get_vehicles(
            db, vehicle_id=int(case_entity.identifier_value)
        )

        if not vehicle:
            return {}
        
        return {
            "vehicle_details": format_vehicle_details(vehicle),
            "delivery_details": {
                "expected_delivery_date": vehicle.expected_delivery_date,
                "delivery_location": vehicle.delivery_location,
                "delivery_note": vehicle.delivery_note
            }
        }
    except Exception as e:
        logger.error("Error fetching vehicle documents: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e