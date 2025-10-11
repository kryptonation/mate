## app/bpm_flows/additionaldriver/flows.py

# Local imports
from app.bpm.services import bpm_service
from app.bpm_flows.additionaldriver import utils as additionaldriver_utils
from app.leases.services import lease_service
from app.leases.search_service import format_lease_response
from app.drivers.services import driver_service
from app.bpm.step_info import step
from app.audit_trail.services import audit_trail_service
from app.utils.logger import get_logger

logger = get_logger(__name__)

entity_mapper = {
    "LEASE": "lease",
    "LEASE_IDENTIFIER": "id",
}


@step(step_id="163", name="Fetch - Search Driver Information", operation='fetch')
def choose_additional_driver(db, case_no, case_params=None):
    """
    Fetch the driver information for the driver lease step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no= case_no)

        lease = None
        if case_params.get('object_lookup') :
            lease = lease_service.get_lease(db=db , lease_id=case_params.get('object_lookup'))

        if case_entity:
            lease = lease_service.get_lease(db=db , lookup_id=int(case_entity.identifier_value))

        if not lease:
            return {'lease_case_details': {}, 'driver_info': {}}

        if not case_entity:
            case_entity = bpm_service.create_case_entity(
                db=db, case_no=case_no,
                entity_name=entity_mapper['LEASE'],
                identifier=entity_mapper['LEASE_IDENTIFIER'],
                identifier_value=str(lease.id)
            )

        lease_case_details = format_lease_response(db, lease)

        if not set(case_params.keys()).intersection(['ssn', 'tlc_license_number', 'dmv_license_number']):
            return {"lease_case_details": lease_case_details}
        
        if not case_params.get("ssn"):
            raise ValueError("SSN is required")
            
        driver_details = driver_service.get_drivers(
            db=db, ssn=case_params.get("ssn", None), tlc_license_number=case_params.get('tlc_license_number', None), dmv_license_number=case_params.get('dmv_license_number', None))
        

        # Check if driver has already signed a valid lease
        if not driver_details:
            return {"lease_case_details": lease_case_details, "driver_info": {}}
        if additionaldriver_utils.has_driver_signed_lease(db, lease, driver_details):
            return {"lease_case_details": lease_case_details, "driver_info": {}}


        return {
            "lease_case_details": lease_case_details,
            "driver_info": {
                "driver_id": driver_details.id,
                "driver_lookup_id": driver_details.driver_id,
                "first_name": driver_details.first_name,
                "last_name": driver_details.last_name,
                "driver_type": driver_details.driver_type,
                "driver_ssn": driver_details.ssn,
                "tlc_license_number": driver_details.tlc_license.tlc_license_number,
                "dmv_license_number": driver_details.dmv_license.dmv_license_number,
                "contact_number": driver_details.phone_number_1
            }
        }
    except Exception as e:
        logger.error("Error fetching driver information: %s", str(e))
        raise e

@step(step_id="163", name="Process - Add additional drivers to lease", operation='process')
def set_additional_driver(db, case_no, step_data):
    """
    Process the driver information for the additional driver step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        if not case_entity:
            return {}

        lease = lease_service.get_lease(db=db, lookup_id=int(case_entity.identifier_value))
        
        cases = bpm_service.get_cases(db=db , case_no= case_no ,multiple=True)

        driver = driver_service.get_drivers(db=db , driver_id=step_data['selected_driver']['driver_id'])

        if cases:
            case_ids = [case.id for case in cases]
            audits = audit_trail_service.get_audit_trail_by_case_ids(db, case_ids)
            for audit in audits:
                audit_trail_service.update_audit_trail(db=db , audit_id=audit.id , update_data={"meta_data": {"driver_id": driver.id, "lease_id": lease.id}})
            logger.info("Audit trail created successfully for Additional Driver Flow")
        additionaldriver_utils.add_additional_driver(db, lease, step_data['selected_driver'])
        return "Ok"
    except Exception as e:
        logger.error("Error processing driver information: %s", str(e))
        raise e
