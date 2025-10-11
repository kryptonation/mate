## app/bpm_flows/update_individual/flows.py

# Third party imports
from fastapi import HTTPException
from sqlalchemy.orm import Session

# Local imports
from app.bpm.services import bpm_service
from app.bpm.step_info import step
from app.utils.logger import get_logger
from app.audit_trail.services import audit_trail_service
from app.medallions.services import medallion_service
from app.entities.services import entity_service
from app.uploads.services import upload_service
from app.medallions.utils import format_medallon_owner

logger = get_logger(__name__)

entity_mapper = {
    "UPDATE_OWNER": "update_individual",
    "IDENTIFIER": "id"
}

@step(step_id="185" , name="fetch-upload documents" , operation="fetch")
def fetch_uploaded_documents(db: Session, case_no: str, case_params: dict):
    try:
        case_entity = bpm_service.get_case_entity(db=db , case_no=case_no)
        owner = None
        if case_entity:
            owner = medallion_service.get_medallion_owner(db=db , medallion_owner_id=case_entity.identifier_value)
        if case_params and case_params.get("object_lookup"):
            owner = medallion_service.get_medallion_owner(db=db , medallion_owner_id=case_params.get("object_lookup"))

        if not owner:
            return {}

        license = upload_service.get_documents(db=db , object_type="medallion_owner" , object_id=owner.id , document_type="license")
        payee_proof = upload_service.get_documents(db=db , object_type="medallion_owner" , object_id=owner.id , document_type="payee_proof")

        if not case_entity:
            case_entity = bpm_service.create_case_entity(
                db=db,
                case_no=case_no,
                identifier_value= owner.id,
                entity_name=entity_mapper["UPDATE_OWNER"],
                identifier=entity_mapper["IDENTIFIER"]
            )

        return {
            "documents":[license , payee_proof],
            "object_type": "medallion_owner",
            "object_id": owner.id,
            "document_type": ["license", "payee_proof"],
            "required_documents": ["license", "payee_proof"]
        }
    except Exception as e:
        logger.error(f"Error fetching uploaded documents: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@step(step_id="185" , name="process-upload documents" , operation="process")
def process_uploaded_documents(db: Session, case_no: str, step_data: dict):
    try:
        logger.info("Nothing To Do Here")
        return "OK"
    except Exception as e:
        logger.error(f"Error processing uploaded documents: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@step(step_id="186" , name= "fetch- Individual Details" , operation="fetch")
def fetch_individual_details(db: Session, case_no: str, case_params: dict):
    try:
        case_entity = bpm_service.get_case_entity(db=db , case_no=case_no)
        if not case_entity:
            return {}
        owner = medallion_service.get_medallion_owner(db=db , medallion_owner_id=case_entity.identifier_value)
        if not owner:
            return {}
        
        license = upload_service.get_documents(db=db , object_type="medallion_owner" , object_id=owner.id , document_type="license")
        payee_proof = upload_service.get_documents(db=db , object_type="medallion_owner" , object_id=owner.id , document_type="payee_proof")

        owner_details = format_medallon_owner(owner)
        owner_details["documents"]= [license , payee_proof]
        return owner_details
    except Exception as e:
        logger.error(f"Error fetching individual details: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@step(step_id="186" , name= "process- Individual Details" , operation="process")
def process_individual_details(db: Session, case_no: str, step_data: dict):
    try:
        case_entity = bpm_service.get_case_entity(db=db , case_no=case_no)
        if not case_entity:
            return {}
        owner = medallion_service.get_medallion_owner(db=db , medallion_owner_id=case_entity.identifier_value)
        if not owner:
            return {}
        individual_data = {
            "id":owner.individual.id,
        }
        address_data = step_data.get("address", {})
        if address_data:
            individual_data["primary_contact_number"] = address_data.get("primary_contact_number")
            individual_data["primary_email_address"] = address_data.get("primary_email_address")
            individual_data["additional_phone_number_1"] = address_data.get("additional_phone_number_1")
            individual_data["additional_phone_number_2"] = address_data.get("additional_phone_number_2")
            individual_data["driving_license"] = address_data.get("driving_license")

            primary_address = address_data.get("primary_address", {})
            if primary_address:
                primary_add = {
                    "address_line_1": primary_address.get("address_line_1"),
                    "address_line_2": primary_address.get("address_line_2"),
                    "city": primary_address.get("city"),
                    "state": primary_address.get("state"),
                    "zip": primary_address.get("zip"),
                }
                if primary_add:
                    address = entity_service.upsert_address(db=db , address_data=primary_add)
                    individual_data["primary_address_id"] = address.id
            secondary_address = address_data.get("secondary_address", {})
            if secondary_address:
                secondary_add = {
                    "address_line_1": secondary_address.get("address_line_1"),
                    "address_line_2": secondary_address.get("address_line_2"),
                    "city": secondary_address.get("city"),
                    "state": secondary_address.get("state"),
                    "zip": secondary_address.get("zip"),
                }
                if secondary_add:
                    address = entity_service.upsert_address(db=db , address_data=secondary_add)
                    individual_data["secondary_address_id"] = address.id

        payee_details = step_data.get("payee_details" , {})
        if payee_details:
            if payee_details.get("pay_to_mode") == "ACH":
                bank_data = {
                    "bank_name": payee_details.get("bank_name"),
                    "bank_account_number": payee_details.get("bank_account_number"),
                    "bank_routing_number": payee_details.get("bank_routing_number"),
                    "bank_account_name": payee_details.get("bank_account_name"),
                    "effective_from": payee_details.get("effective_from")
                }
                if bank_data:
                    bank = entity_service.upsert_bank_account(db=db , bank_account_data=bank_data)
                    individual_data["bank_account_id"] = bank.id
            else:
                individual_data["payee"] = payee_details.get("payee")

        if individual_data:
            ind = entity_service.upsert_individual(db=db , individual_data=individual_data)
            if not ind:
                raise HTTPException(status_code=400 , detail="Failed to update individual details")
        
        medallion_owner = medallion_service.upsert_medallion_owner(db=db , medallion_owner_data={
            "id": owner.id,
            "primary_phone": ind.primary_contact_number,
            "primary_email_address": ind.primary_email_address
        })
            
        cases = bpm_service.get_cases(db=db , case_no= case_no ,multiple=True)
        if cases:
            case_ids = [case.id for case in cases]
            audits = audit_trail_service.get_audit_trail_by_case_ids(db, case_ids)
            for audit in audits:
                audit_trail_service.update_audit_trail(db=db , audit_id=audit.id , update_data={"meta_data": {"medallion_owner_id": owner.id}})

        return "OK"
    except Exception as e:
        logger.error(f"Error processing individual details: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")