## app/bpm_flows/new_correspondence/flows.py

# Third party imports
from fastapi import HTTPException

# Local imports
from app.utils.logger import get_logger
from app.bpm.step_info import step
from app.audit_trail.services import audit_trail_service
from app.bpm.services import bpm_service
from app.correspondence.services import correspondence_service

logger = get_logger(__name__)
entity_mapper = {
    "CORRENSPONDENCE": "correspondence",
    "CORRENSPONDENCE_IDENTIFIER": "id",
}

@step(step_id="154", name="Fetch - Return correspondence details", operation="fetch")
def fetch_correspondence(db, case_no, case_params=None):
    """Fetch correspondence details"""
    try:
        logger.info("Fetching correspondence details")
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        if not case_entity:
            return {}

        correspondence = correspondence_service.get_correspondence(
            db, correspondence_id=int(case_entity.identifier_value)
        )

        if not correspondence:
            return {}

        return correspondence
    except Exception as e:
        logger.error("Error fetching correspondence details: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    
@step(step_id="154", name="Process - Create correspondence", operation="process")
def process_correspondence(db, case_no, step_data):
    """Process correspondence"""
    try:
        logger.info("Processing the correspondence data")
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        correspondence = correspondence_service.upsert_correspondence(db, step_data)

        if not case_entity:
            bpm_service.create_case_entity(
                db, case_no=case_no,
                entity_name=entity_mapper['CORRENSPONDENCE'],
                identifier=entity_mapper['CORRENSPONDENCE_IDENTIFIER'],
                identifier_value=int(correspondence.id)
            )
        
        cases = bpm_service.get_cases(db=db , case_no= case_no ,multiple=True)
        if cases:
            case_ids = [case.id for case in cases]
            audits = audit_trail_service.get_audit_trail_by_case_ids(db, case_ids)
            for audit in audits:
                audit_trail_service.update_audit_trail(db=db , audit_id=audit.id , update_data={"meta_data": {"correspondence_id": correspondence.id}})
        
        return "Ok"
    except Exception as e:
        logger.error("Error processing correspondence: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e
    