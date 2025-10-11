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
    "MEDALLION_OWNER": "medallion_owner",
    "IDENTIFIER": "identifier"
}

@step(step_id="187" , name="Fetch-Uploded Documents" , operation="fetch")
def fetch_uploaded_documents(db: Session, case_no: str, case_params: dict):
    try:
        case_entity = bpm_service.get_case_entity(db=db , case_no=case_no)
        
        owner = None
        if case_entity :
            owner = medallion_service.get_medallion_owner(db=db , medallion_owner_id=case_entity.identifier_value)
        if case_params and case_params.get("object_lookup"):
            owner = medallion_service.get_medallion_owner(db=db , medallion_owner_id=case_params.get("object_lookup"))

        if not owner:
            return {}
        

        ssn = upload_service.get_documents(db=db , object_type="medallion_owner" , object_id=owner.id , document_type="ssn")
        payee_proof = upload_service.get_documents(db=db , object_type="medallion_owner" , object_id=owner.id , document_type="payee_proof")

        if not case_entity :
            case_entity = bpm_service.create_case_entity(
                db=db , case_no=case_no,
                entity_name= entity_mapper["MEDALLION_OWNER"],
                identifier_value= owner.id,
                identifier= entity_mapper["IDENTIFIER"]
            )

        return {
            "documents":[ssn , payee_proof],
            "object_type": "medallion_owner",
            "object_id": owner.id,
            "document_type": ["ssn", "payee_proof"],
            "required_documents": ["ssn", "payee_proof"]
        }
    except Exception as e:
        logger.error(f"Error fetching uploaded documents: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@step(step_id="187" , name="process-upload documents" , operation="process")
def process_uploaded_documents(db: Session, case_no: str, step_data: dict):
    try:
        logger.info("Nothing To Do Here")
        return "OK"
    except Exception as e:
        logger.error(f"Error processing uploaded documents: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@step(step_id="188" , name="fetch-Corporation details" , operation="fetch")
def fetch_corporation_details(db: Session, case_no: str, case_params: dict):
    try:
        case_entity = bpm_service.get_case_entity(db=db , case_no=case_no)
        
        owner = None
        if case_entity :
            owner = medallion_service.get_medallion_owner(db=db , medallion_owner_id=case_entity.identifier_value)
        if case_params and case_params.get("object_lookup"):
            owner = medallion_service.get_medallion_owner(db=db , medallion_owner_id=case_params.get("object_lookup"))

        if not owner:
            return {}
        
        corporation = entity_service.get_corporation(db=db , corporation_id=owner.corporation_id)
        if not corporation:
            return {}
        
        ssn = upload_service.get_documents(db=db , object_type="medallion_owner" , object_id=owner.id , document_type="ssn")
        payee_proof = upload_service.get_documents(db=db , object_type="medallion_owner" , object_id=owner.id , document_type="payee_proof")
        owner_details = format_medallon_owner(owner)
        owner_details["documents"] = [ssn , payee_proof]

        return owner_details
    except Exception as e:
        logger.error(f"Error fetching corporation details: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
@step(step_id="188" , name="process-Corporation details" , operation="process")
def process_corporation_details(db: Session, case_no: str, step_data: dict):
    try:
        case_entity = bpm_service.get_case_entity(db=db , case_no=case_no)

        if not case_entity:
            return {}
        owner = medallion_service.get_medallion_owner(db=db , medallion_owner_id=case_entity.identifier_value)
        if not owner:
            raise HTTPException(status_code=404, detail="Medallion Owner not found")
        
        corporation = entity_service.get_corporation(db=db , corporation_id=owner.corporation_id)
        
        corporation_details = step_data.get("corporation_details" , {})

        corporation_data ={
            "id": owner.corporation_id
        }

        if corporation_details:
            corporation_data.update({
                "primary_contact_number": corporation_details.get("primary_contact_number"),
                "primary_email_address": corporation_details.get("primary_email_address"),
                "is_llc": corporation_details.get("is_llc")
            })

            corporation_address = {
                "id": corporation.primary_address_id,
                "address_line_1": corporation_details.get("address_line_1"),
                "address_line_2": corporation_details.get("address_line_2"),
                "city": corporation_details.get("city"),
                "state": corporation_details.get("state"),
                "zip": corporation_details.get("zip")
            }

            if corporation_address:
                add = entity_service.upsert_address(db=db , address_data=corporation_address)
                if add :
                    corporation_data["primary_address_id"] = add.id

        contact_person = step_data.get("contact_person_details" , {})

        if contact_person:
            contact_person_data = {
                "id": corporation.primary_contact_person_id,
                "first_name": contact_person.get("first_name"),
                "middle_name": contact_person.get("middle_name"),
                "last_name": contact_person.get("last_name"),
                "full_name" : " ".join(filter(None , [contact_person.get("first_name"), contact_person.get("middle_name"), contact_person.get("last_name")])),
                "primary_contact_number": contact_person.get("primary_contact_number"),
                "primary_email_address": contact_person.get("primary_email_address"),
                "additional_phone_number_1": contact_person.get("additional_phone_number_1")
            }
            person = entity_service.upsert_individual(db=db , individual_data= contact_person_data)
            if person:
                corporation_data["primary_contact_person_id"] = person.id
            corporation_data["is_contact_same_as_key_people"] = contact_person.get("is_contact_same_as_key_people", False)

        bank_payee_details = step_data.get("payee_details")
        if bank_payee_details:
            if bank_payee_details.get("pay_to_mode") == "ACH":
                bank_account = {
                    "id": corporation.bank_account_id,
                    "bank_name": bank_payee_details.get("bank_name"),
                    "bank_account_number": bank_payee_details.get("bank_account_number"),
                    "bank_routing_number": bank_payee_details.get("bank_routing_number"),
                    "bank_account_name": bank_payee_details.get("bank_account_name"),
                    "effective_from": bank_payee_details.get("effective_from"),
                    "bank_account_status": "Active"
                }

                if bank_account:
                    acc = entity_service.upsert_bank_account(db=db , bank_account_data=bank_account)
                    if acc:
                        corporation_data["bank_account_id"] = acc.id
            else:
                corporation_data["payee"] = bank_payee_details.get("payee")

        if corporation_data.get("is_llc") == True:
            peoples = step_data.get("peoples")

            if peoples and len(peoples) > 0:
                for key , value in peoples.items():
                    data = {
                        "id": getattr(corporation , key , None),
                        "first_name": value.get("first_name"),
                        "middle_name": value.get("middle_name"),
                        "last_name": value.get("last_name"),
                        "full_name":" ".join(filter(None , [value.get("first_name"), value.get("middle_name"), value.get("last_name")])),
                        "masked_ssn": value.get("ssn"),
                        "dob": value.get("dob"),
                        "primary_contact_number": value.get("phone"),
                        "primary_email_address": value.get("email"),
                    }
                    address_data = {
                        "address_line_1": value.get("address_line_1"),
                        "address_line_2": value.get("address_line_2"),
                    }
                    if address_data:
                        address= entity_service.upsert_address(db=db , address_data=address_data)
                        data["primary_address_id"] = address.id
                    if data:
                        ind = entity_service.upsert_individual(db=db , individual_data=data)
                        if ind:
                            corporation_data[key] = ind.id
                corporation_data["key_people"]= None
        else:
            key_people = step_data.get("key_people")
            if key_people:
                corporation_data["key_people_type"]= key_people.get("key_people_type")
                key_people_details = {
                    "id": corporation.key_people,
                    "first_name": key_people.get("first_name"),
                    "middle_name": key_people.get("middle_name"),
                    "last_name": key_people.get("last_name"),
                    "masked_ssn": key_people.get("ssn"),
                    "dob": key_people.get("dob"),
                    "full_name":" ".join(filter(None , [key_people.get("first_name"), key_people.get("middle_name"), key_people.get("last_name")]))
                }

                if key_people_details:
                    address_data = {
                        "address_line_1": key_people.get("address_line_1"),
                        "address_line_2": key_people.get("address_line_2")
                    }
                    if address_data:
                        key_people_address=entity_service.upsert_address(db=db , address_data= address_data)
                        key_people_details["primary_address_id"] = key_people_address.id

                    individual = entity_service.upsert_individual(db=db , individual_data= key_people_details)
                    if individual:
                        corporation_data["key_people"] = individual.id
                        corporation_data["president"] = None
                        corporation_data["secretary"] = None
                        corporation_data["corporate_officer"] = None
        corporation_owner = entity_service.upsert_corporation(db=db , corporation_data= corporation_data)

        if not corporation_owner:
            raise HTTPException(status_code=500, detail="Error creating Corporation")
        
        medallion_owner = medallion_service.upsert_medallion_owner(
            db=db,
            medallion_owner_data={
                "id": owner.id,
                "primary_phone": corporation_owner.primary_contact_number,
                "primary_email_address": corporation_owner.primary_email_address
            }
        )
        
        cases = bpm_service.get_cases(db=db , case_no= case_no ,multiple=True)
        if cases:
            case_ids = [case.id for case in cases]
            audits = audit_trail_service.get_audit_trail_by_case_ids(db, case_ids)
            for audit in audits:
                audit_trail_service.update_audit_trail(db=db , audit_id=audit.id , update_data={"meta_data": {"medallion_owner_id": owner.id}})


        return "OK"
    except Exception as e:
        logger.error(f"Error processing corporation details: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")