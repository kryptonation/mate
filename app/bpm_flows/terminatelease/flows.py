## app/bpm_flows/terminatelease/flows.py

# Local imports
from app.audit_trail.services import audit_trail_service
from app.bpm.services import bpm_service
from app.drivers.services import driver_service
from app.leases.services import lease_service
from app.drivers.utils import format_driver_response
from app.bpm_flows.terminatelease import utils as terminate_lease_utils
from app.bpm.step_info import step
from app.utils.logger import get_logger
from app.drivers.schemas import DriverStatus
from app.vehicles.schemas import VehicleStatus 
from app.leases.schemas import LeaseStatus

logger = get_logger(__name__)

entity_mapper = {
    "DRIVER_TERMINATE_LEASE": "driver",
    "DRIVER_TERMINATE_LEASE_IDENTIFIER": "id"
}

@step(step_id="155", name="Fetch - Leases associated with the driver", operation='fetch')
def fetch_driver_details(db, case_no, case_params=None):
    """
    Fetch the driver address for the update driver address step
    """
    try:
        logger.info("Return Driver Address")
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        driver = None
        if case_params:
            driver = driver_service.get_drivers(db, driver_id=case_params['object_lookup'])
        if case_entity:
            driver = driver_service.get_drivers(db, id=case_entity.identifier_value)

        if not driver:
            return {"driver_info": {}}

        driver_data = format_driver_response(driver, False)
        return {
            "driver_info": {
                "driver_seq_id": driver.id,
                **driver_data["driver_details"],
                **driver_data["dmv_license_details"],
                **driver_data["tlc_license_details"]
            },
            "lease_info": lease_service.fetch_lease_information_for_driver(db, driver.driver_id)
        }
    except Exception as e:
        logger.error("Error fetching driver details: %s", e)
        raise e


@step(step_id="155", name="Process - Driver Address", operation='process')
def process_lease_termination(db, case_no, step_data):
    """
    Terminate driver lease
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        driver_id = step_data.get("driver_id")
        driver = driver_service.get_drivers(db, id=driver_id)
        if not driver:
            raise ValueError("Driver not found for the driver id passed")
        
        driver.driver_status = DriverStatus.INACTIVE

        if case_entity and driver.id != int(case_entity.identifier_value):
            raise ValueError("The driver id passed is not relevant to this case")

        for driver_lease_id in step_data["driver_lease_ids"]:
            driver_lease_object = terminate_lease_utils.fetch_driver_lease(
                db, int(driver_lease_id))
            driver_lease_object.is_active = False
            
            
            lease= terminate_lease_utils.fetch_lease_by_Leasedriver(db, driver_lease_object)
            vehicle= terminate_lease_utils.fetch_vehicle_by_lease(db, lease)
            vehicle.vehicle_status=VehicleStatus.HACKED_UP
            lease.lease_status= LeaseStatus.INACTIVE
            lease.is_active=False
            
            cases = bpm_service.get_cases(db=db , case_no= case_no ,multiple=True)
            if cases:
                case_ids = [case.id for case in cases]
                audits = audit_trail_service.get_audit_trail_by_case_ids(db, case_ids)
                for audit in audits:
                    audit_trail_service.update_audit_trail(db=db , audit_id=audit.id , update_data={"meta_data": {"medallion_id":vehicle.medallions.id ,"vehicle_id":vehicle.id , "driver_id":driver.id , "lease_id":lease.id}})

            db.add(lease)
            db.add(vehicle)
            db.add(driver_lease_object)
            db.flush()

        if not case_entity:
            case_entity = bpm_service.create_case_entity(
                db=db, case_no=case_no,
                entity_name=entity_mapper['DRIVER_TERMINATE_LEASE'],
                identifier=entity_mapper['DRIVER_TERMINATE_LEASE_IDENTIFIER'],
                identifier_value=str(driver.id)
            )

        return "Ok"
    except Exception as e:
        logger.error("Error processing lease termination: %s", e)
        raise e
