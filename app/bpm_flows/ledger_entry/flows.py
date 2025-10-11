## app/bpm_flows/ledger_entry/flows.py

from datetime import datetime
# Third party imports
from fastapi import HTTPException

# Local imports
from app.utils.logger import get_logger
from app.bpm.step_info import step
from app.audit_trail.services import audit_trail_service
from app.bpm.services import bpm_service
from app.drivers.services import driver_service
from app.uploads.services import upload_service
from app.drivers.utils import format_driver_response
from app.ledger.schemas import LedgerSourceType
from app.ledger.services import ledger_service
from app.leases.services import lease_service

logger = get_logger(__name__)

entity_mapper = {
    "LEDGER": "ledger",
    "LEDGER_IDENTIFIER": "id"
}


@step(step_id="165", name="Fetch- driver details", operation="fetch")
def fetch_driver_data(db, case_no, case_params=None):
    try:
        # Fetch existing case entity
        case_entity = bpm_service.get_case_entity(db, case_no)

        driver = None
        ledger = None

        # Fetch driver if we have a case entity
        if case_entity:
            ledger = ledger_service.get_ledger_entries(db=db, ledger_id=case_entity.identifier_value)
            if ledger:
                driver = driver_service.get_drivers(db=db, driver_id=str(ledger.driver_id))

        # Fetch driver if we have params
        elif case_params:
            # Driver ID
            if not any([
            case_params.get("driver_id"),
            case_params.get("medallion_number"),
            case_params.get("vin"),
            case_params.get("driver_name")
            ]):
                return {}
            
            if case_params.get("driver_id"):
                driver = driver_service.get_drivers(db=db, driver_id=case_params["driver_id"])
            elif case_params.get("driver_name"):
                driver = driver_service.get_drivers(db=db ,driver_name=case_params["driver_name"])
            # Medallion Number
            elif case_params.get("medallion_number"):
                driver = driver_service.get_drivers(db=db , medallion_number=case_params["medallion_number"])
            # VIN
            elif case_params.get("vin"):
                driver = driver_service.get_drivers(db=db , vin=case_params["vin"])

        # Validate driver
        if not driver:
            return {}

        return format_driver_response(driver, False)

    except Exception as e:
        logger.error(f"Error fetching driver data for case_no={case_no}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@step(step_id="165", name="process - driver details", operation="process")
def process_driver_data(db, case_no, step_data):
    try:
        case_entity = bpm_service.get_case_entity(db, case_no)
        driver = None
        ledger = None


        if case_entity:
            ledger = ledger_service.get_ledger_entries(db=db, ledger_id=case_entity.identifier_value)
            driver = driver_service.get_drivers(db=db, id= str(ledger.driver_id))
        if step_data.get("driverId"):
            driver = driver_service.get_drivers(db=db , id=step_data["driverId"])

        if not driver:
            raise ValueError("Driver not found")
        
        driver_lease = lease_service.get_lease_drivers(db=db , driver_id=driver.driver_id)

        lease = driver_lease.lease if driver_lease else None
        vehicle = lease.vehicle if lease else None
        medallion = lease.medallion if lease else None
        
        data = {
            "ledger_id":f"{datetime.today().strftime('%d-%m-%y')}-{driver.tlc_license.tlc_license_number}",
            "driver_id": driver.id,
            "medallion_id": medallion.id if medallion else None,
            "vehicle_id":vehicle.id if vehicle else None,            
            "amount": 0,
            "debit":True
        }
        if not ledger:
            ledger = ledger_service.upsert_ledgers( db=db , ledger_data=data)
        if not case_entity:
            case_entity = bpm_service.create_case_entity(
                db=db,
                case_no=case_no,
                entity_name=entity_mapper["LEDGER"],
                identifier_value=ledger.id,
                identifier=entity_mapper["LEDGER_IDENTIFIER"]
            )
        
        return "ok"
    except Exception as e:
        logger.error(f"Error processing driver data for case_no={case_no}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@step(step_id="166" , name="fetch - Ledger Details" , operation="fetch")
def fetch_ledger_details(db , case_no , case_params=None):
    try:
        case_entity = bpm_service.get_case_entity(db, case_no)

        driver = None
        ledger = None

        if case_params and case_params.get("driver_id"):
            driver = driver_service.get_drivers(db=db, driver_id=case_params["driver_id"])

        if case_entity :
            ledger = ledger_service.get_ledger_entries(db=db, ledger_id=case_entity.identifier_value)
            driver = driver_service.get_drivers(db=db, id= str(ledger.driver_id))


        if not driver:
            return {}
        
        if not ledger:
            raise {}
        
        invoice_document = upload_service.get_documents(db=db , document_type= "invoice" , object_type= "ledger" , object_id= ledger.id)

        ledger_data = {
            "driver_details" : format_driver_response(driver, False),
            "ledger_details" : ledger ,
            "ledger_document" : invoice_document,
            "source_type" : [LedgerSourceType.value for LedgerSourceType in LedgerSourceType],
            "upload_details" :{
                "object_type" : "ledger",
                "object_id" : ledger.id if ledger else None,
                "document_type" : "invoice"
            }
        }
        return ledger_data
    except Exception as e:
        logger.error(f"Error fetching ledger data for case_no={case_no}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    

@step(step_id="166" , name="process - Ledger Details" , operation="process")
def process_ledger_details(db , case_no , step_data):
    try:
        case_entity = bpm_service.get_case_entity(db, case_no)
        driver = None
        ledger = None

        if case_entity:
            ledger = ledger_service.get_ledger_entries(db=db, ledger_id=case_entity.identifier_value)
            driver = driver_service.get_drivers(db=db, id= str(ledger.driver_id))

        if not driver:
            raise ValueError("Driver not found")
        
        if not ledger:
            raise ValueError("Ledger not found")
        
        raw_time = step_data.get("transaction_time")
        formatted_time = None
        if raw_time:
            if isinstance(raw_time, str):
                dt_obj = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
                formatted_time = dt_obj.strftime("%H:%M:%S")
            else:
                formatted_time = raw_time.strftime("%H:%M:%S")
        

        data = {
            "amount": step_data.get("amount"),
            "debit": step_data.get("debit"),
            "transaction_date": step_data.get("transaction_date"),
            "transaction_time": formatted_time,
            "description": step_data.get("description"),
            "source_type": step_data.get("source_type"),
            "source_id": step_data.get("source_id")
        }

        cases = bpm_service.get_cases(db=db , case_no= case_no ,multiple=True)
        if cases:
            case_ids = [case.id for case in cases]
            audits = audit_trail_service.get_audit_trail_by_case_ids(db, case_ids)
            for audit in audits:
                audit_trail_service.update_audit_trail(db=db , audit_id=audit.id , update_data={"meta_data": {"ledger_id": ledger.id , "driver_id": driver.id , "vehicle_id": ledger.vehicle_id , "medallion_id": ledger.medallion_id}})
        
        ledger = ledger_service.upsert_ledgers(db=db, ledger_data={"id":ledger.id , **data})

        return "ok"
    except Exception as e:
        logger.error(f"Error processing ledger data for case_no={case_no}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

        
        

        
        


        