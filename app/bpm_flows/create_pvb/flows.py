## app/bpm_flows/create_pvb/flows.py

# Standard library imports
from datetime import datetime, date

# Third party imports
from fastapi import HTTPException

# Local imports
from app.utils.logger import get_logger
from app.bpm.step_info import step
from app.audit_trail.services import audit_trail_service
from app.bpm.services import bpm_service
from app.drivers.services import driver_service
from app.uploads.services import upload_service
from app.leases.services import lease_service
from app.pvb.services import pvb_service
from app.bpm_flows.create_pvb.utils import format_pvb_details


logger = get_logger(__name__)

entity_mapper = {
    "PVB": "pvb",
    "PVB_IDENTIFIER": "id",
}


@step(step_id="159" , name="Fetch - Verify PVB details", operation='fetch')
def fetch_pvb_information(db, case_no, case_params=None):
    """
    Fetch the PVB information for the create PVB step
    """
    try:
        if not case_params:
            return {}
        
        if not any([
            case_params.get("plate_number"),
            case_params.get("medallion_number"),
            case_params.get("tlc_license_number")
        ]):
            return {}
        
        return  pvb_service.fetch_driver_id_pvb(db, case_params)
    except Exception as e:
        logger.error("Error fetching PVB information: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@step(step_id="159", name="Process - choose Driver", operation='process')
def process_choose_driver(db, case_no, step_data):
    """
    Process the choose driver details for the create PVB step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        if case_entity:
            raise ValueError(
                "Cannot process this step for because a driver_id cannot be reselected for this case")
        
        driver_id = step_data.get("driver_id")
        driver = driver_service.get_drivers(db, driver_id=driver_id)
        if not driver:
            raise ValueError(
                f"Driver not found for the provided driver_id {driver_id}")
        
        driver_lease = lease_service.get_lease_drivers(
            db, driver_id=driver_id, sort_order="desc"
        )

        lease = lease_service.get_lease(db ,lookup_id=driver_lease.lease_id)

        data = {
            "plate_number": step_data.get("plate_number"),
            "state" : "NY",
            "medallion_id" : lease.medallion_id if lease else None,
            "driver_id" : driver.id,
            "vehicle_type" : "OMT",
            "issue_date" : date.today(),
            "issue_time" : datetime.now().time(),
            "status" : "Associated",
            "vehicle_id" : lease.vehicle_id if lease else None,
        }
        # Process pvb details
        pvb = pvb_service.upsert_pvb_violation(db, violation_data=data)
        
        # Create case entity if not exists
        if not case_entity:
            case_entity = bpm_service.create_case_entity(
                db=db, case_no=case_no,
                entity_name=entity_mapper['PVB'],
                identifier=entity_mapper["PVB_IDENTIFIER"],
                identifier_value=str(pvb.id)
        )

        # Create lease entity if not exists
        # if not case_entity.lease_id:
        #     lease_service.upsert_lease(db, lease_data={"id": case_entity.lease_id, **step_data})
        return "Ok"
    except Exception as e:
        logger.error("Error processing choose driver: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@step(step_id="160", name="fetch - attach document", operation='fetch')
def fetch_attach_document(db, case_no, case_params=None):
    """
    Fetch the attach document details for the create PVB step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        if not case_entity:
            return {}

        # Fetch the PVB details using the PVB ID from the case entity
        pvb = pvb_service.get_pvb(
            db, violation_id = int(case_entity.identifier_value)
        )
        if not pvb:
            return {}
        
        pvb_documents= upload_service.get_documents(
            db, object_type="PVB",
            object_id=str(pvb.id),
            document_type="PVB"
        )
        
        # Fetch the PVB details
        return format_pvb_details(db=db, pvb=pvb, documents=pvb_documents)
    except Exception as e:
        logger.error("Error fetching attach document: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@step(step_id="160", name="Process - attach document", operation='process')
def process_attach_document(db, case_no, step_data):
    """
    Process the attach document details for the create PVB step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        if not case_entity:
            return {}

        pvb = pvb_service.get_pvb(
            db, violation_id = int(case_entity.identifier_value)
        )
        pvb_documents= upload_service.get_documents(
            db, object_type="PVB",
            object_id=str(pvb.id),
            document_type="PVB"
        )
        if not pvb or not pvb_documents:
            return {}
                
        return "Ok"
    except Exception as e:
        logger.error("Error processing attach document: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@step(step_id="161", name="fetch - enter PVB details", operation='fetch')
def fetch_enter_pvb_details(db, case_no, case_params=None):
    """
    Fetch the enter PVB details for the create PVB step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        if not case_entity:
            return {}

        # Fetch the PVB details using the PVB ID from the case entity
        pvb = pvb_service.get_pvb(
            db, violation_id = int(case_entity.identifier_value)
        )
        if not pvb:
            return {}
        
        # Fetch the PVB details
        pvb_documents= upload_service.get_documents(
            db, object_type="PVB",
            object_id=str(pvb.id),
            document_type="PVB"
        )
        
        # Fetch the PVB details
        return format_pvb_details(db=db , pvb=pvb, documents=pvb_documents)
    except Exception as e:
        logger.error("Error fetching enter PVB details: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@step(step_id="161", name="Process - enter PVB details", operation='process')
def process_enter_pvb_details(db, case_no, step_data):
    """
    Process the enter PVB details for the create PVB step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        if not case_entity:
            return {}

        # Fetch the PVB details using the PVB ID from the case entity
        pvb = pvb_service.get_pvb(
            db, violation_id = int(case_entity.identifier_value)
        )

        pvb_data = pvb_service.get_pvb(db= db , summons_number= step_data.get("summons_number"))

        if pvb_data:
            raise ValueError(
                f"PVB with summons number {step_data.get('summons_number')} already exists"
            )
        
        if not pvb:
            return {}
        
        cases = bpm_service.get_cases(db=db , case_no= case_no ,multiple=True)
        if cases:
            case_ids = [case.id for case in cases]
            audits = audit_trail_service.get_audit_trail_by_case_ids(db, case_ids)
            for audit in audits:
                audit_trail_service.update_audit_trail(db=db , audit_id=audit.id , update_data={"meta_data": {"pvb_id": pvb.id , "driver_id": pvb.driver_id , "medallion_id": pvb.medallion_id , "vehicle_id": pvb.vehicle_id}})

        
        pvb_service.upsert_pvb_violation(db, {
            "id": pvb.id,
            **step_data
        })
            
        return "Ok"
    except Exception as e:
        logger.error("Error processing enter PVB details: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
