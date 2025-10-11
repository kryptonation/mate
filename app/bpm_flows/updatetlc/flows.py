## app/bpm_flows/updatetlc/flows.py

# Local imports
from app.utils.logger import get_logger
from app.bpm.step_info import step
from app.audit_trail.services import audit_trail_service
from app.bpm.services import bpm_service
from app.drivers.services import driver_service
from app.uploads.services import upload_service
from app.drivers.utils import format_driver_response
from app.utils.document_processor import document_processor
from app.utils.s3_utils import s3_utils

logger = get_logger(__name__)

entity_mapper = {
    "DRIVER": "drivers",
    "DRIVER_IDENTIFIER": "id",
}

@step(step_id="148" , name = "Fetch - TLC Document" , operation='fetch')
def fetch_tlc_document(db, case_no, case_params=None):
    """
    Fetch the TLC document
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        driver = None

        if case_params:
            driver = driver_service.get_drivers(db, driver_id=case_params['object_lookup'])
        if case_entity:
            driver = driver_service.get_drivers(db, id=int(case_entity.identifier_value))
        if not driver:
            return {}
        driver_data = format_driver_response(driver, False)

        tlc_doc = upload_service.get_documents(db, object_type="driver", object_id=driver.id, document_type="tlc_license")

        if not case_entity:
            case_entity = bpm_service.create_case_entity(
                db=db, case_no=case_no,
                entity_name=entity_mapper['DRIVER'],
                identifier=entity_mapper['DRIVER_IDENTIFIER'],
                identifier_value=str(driver.id)
            )

        return {
            "driver_info": {
                **driver_data["driver_details"],
                "driver_seq_id": driver.id,
                "tlc_license": driver_data['tlc_license_details']['tlc_license_number'] if driver_data['tlc_license_details']['tlc_license_number'] else "",
                "dmv_license": driver_data['dmv_license_details']['dmv_license_number'] if driver_data['dmv_license_details']['dmv_license_number'] else "",
            },
            "tlc_license_info": driver_data['tlc_license_details'],
            "tlc_license_document": tlc_doc
        }
    except Exception as e:
        logger.error("Error fetching tlc document: %s", e, exc_info=True)
        raise e
@step(step_id="148" , name = "Process - TLC Document" , operation='process')
def process_tlc_document(db, case_no, step_data):
    """
    Process the TLC document
    """
    try:
        logger.info("Process- Nothing TO Do Here")
        return "Ok"
    except Exception as e:
        logger.error("Error processing tlc document: %s", e, exc_info=True)
        raise e

@step(step_id="149", name="Fetch - Return TLC License", operation='fetch')
def fetch_tlc_license(db, case_no, case_params=None):
    """
    Fetch the tlc license for the update tlc step
    """
    try:
        logger.info("Return TLC License")
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        driver_info = {
            'driver_info': {},
            'tlc_license_info': {},
            'tlc_license_document': {}
        }
        driver = None
        if case_params:
            driver = driver_service.get_drivers(db, driver_id=case_params['object_lookup'])
        if case_entity:
            driver = driver_service.get_drivers(db, id=int(case_entity.identifier_value))
        if not driver:
            return driver_info

        driver_data = format_driver_response(driver, False)

        tlc_doc = upload_service.get_documents(db, object_type="driver", object_id=driver.id, document_type="tlc_license")


        extracted_data = {}

        if tlc_doc and tlc_doc.get("document_path"):
            metadata = s3_utils.get_file_metadata(tlc_doc["document_path"])
            metadata = metadata if metadata else {}
            metadata = metadata.get("extracted_data" , {}).get("extracted_data" ,{})
            extracted_data[tlc_doc.get("document_type")] = metadata

        logger.info(f"##$#### TLC Data OCR: {extracted_data}")

        if extracted_data.get("tlc_license" , {}):
            tlc_data = extracted_data.get("tlc_license" , {})
            if tlc_data.get("dates", None):
                    driver_data["tlc_license_details"]["tlc_license_expiry_date"] = tlc_data.get("dates", None)[0]
                    driver_data["tlc_license_details"]["tlc_license_number"] = tlc_data.get("license_number", None)

        return {
            "driver_info": {
                **driver_data["driver_details"],
                "driver_seq_id": driver.id,
                "tlc_license": driver_data['tlc_license_details']['tlc_license_number'] if driver_data['tlc_license_details']['tlc_license_number'] else "",
                "dmv_license": driver_data['dmv_license_details']['dmv_license_number'] if driver_data['dmv_license_details']['dmv_license_number'] else "",
            },
            "tlc_license_info": driver_data['tlc_license_details'],
            "tlc_license_document": tlc_doc
        }
    except Exception as e:
        logger.error("Error fetching tlc license: %s", e, exc_info=True)
        return e


@step(step_id="149", name="Process - Update TLC License", operation='process')
def set_tlc_license_information(db, case_no, step_data):
    """
    Process the tlc license information for the update tlc step
    """
    try:
        logger.info("Process - Update TLC License")
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        driver_id = step_data.get("driver_id")
        driver = driver_service.get_drivers(db, driver_id=driver_id)
        if not driver:
            raise ValueError("Driver not found for the driver id passed")

        if case_entity and driver.id != int(case_entity.identifier_value):
            raise ValueError("The driver id passed is not relevant to this case")
        
        license_number = driver.tlc_license.tlc_license_number if driver.tlc_license else None

        if license_number and license_number == step_data.get("tlc_license_number"):
            raise ValueError("New TLC Licensence Number is Same as Old TLC Licensence Number")
        if license_number and step_data.get("previous_tlc_license_number") and license_number != step_data.get("previous_tlc_license_number"):
            raise ValueError("Previous TLC Licensence Number is not Same as Old TLC Licensence Number")

        tlc_license = driver_service.get_tlc_license(db, tlc_license_number=step_data.get("tlc_license_number"))
        del step_data["driver_id"]

        tlc_number = step_data.get("tlc_license_number")

        if not tlc_number or not str(tlc_number).isdigit() or len(str(tlc_number)) > 8 or len(str(tlc_number)) < 7:
            raise ValueError("Invalid TLC License Number: must be exactly 7 to 8 digits")

        if not tlc_license:
            tlc_license = driver_service.upsert_tlc_license(db, {
                **step_data
            })
        else:
            tlc_license = driver_service.upsert_tlc_license(db, {
                "id": tlc_license.id,
                **step_data
            })

        driver_service.upsert_driver(db, {
            "id": driver.id,
            "driver_id": tlc_license.tlc_license_number,
            "tlc_license_number_id": tlc_license.id
        })

        cases = bpm_service.get_cases(db=db , case_no= case_no ,multiple=True)
        if cases:
            case_ids = [case.id for case in cases]
            audits = audit_trail_service.get_audit_trail_by_case_ids(db, case_ids)
            for audit in audits:
                audit_trail_service.update_audit_trail(db=db , audit_id=audit.id , update_data={"meta_data": {"driver_id": driver.id}})


        return "Ok"
    except Exception as e:
        logger.error("Error processing tlc license: %s", e, exc_info=True)
        raise e