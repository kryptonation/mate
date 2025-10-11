## app/bpm_flows/create_driver_payments/flows.py

# Standard library imports
from uuid import uuid4
from datetime import datetime, date

# Third party imports
from sqlalchemy.orm import Session

# Local imports
from app.utils.logger import get_logger
from app.bpm.step_info import step
from app.bpm.services import bpm_service
from app.drivers.services import driver_service
from app.medallions.services import medallion_service
from app.curb.services import curb_service
from app.vehicles.services import vehicle_service
from app.ledger.services import ledger_service
from app.leases.services import lease_service
from app.ledger.schemas import LedgerSourceType
from app.ledger.utils import generate_dtr_html_doc, generate_dtr_pdf_doc, generate_dtr_excel_doc_styled

logger = get_logger(__name__)

entity_mapper = {
    "DPC": "dpc",
    "DPC_IDENTIFIER": "id",
}

@step(step_id="167", name="Fetch - Choose Pay Period", operation="fetch")
def fetch_choose_pay_period(db, case_no, case_params=None):
    """Fetch the pay period for the create driver payments step"""
    try:
        return {}
    except Exception as e:
        logger.error("Error fetching pay period: %s", e, exc_info=True)
        raise e

@step(step_id="167", name="Process - Choose Pay Period", operation="process")
def process_choose_pay_period(db, case_no, step_data):
    """Process the choose pay period step"""
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        start_dt = datetime.strptime(step_data["start_date"] + " " + step_data["start_time"], "%Y-%m-%d %I:%M %p")
        end_dt = datetime.strptime(step_data["end_date"] + " " + step_data["end_time"], "%Y-%m-%d %I:%M %p")

        drivers = None

        if step_data.get("include_all_drivers"):
            drivers = driver_service.get_drivers(db, multiple=True)
        else:
            drivers = driver_service.get_drivers(db, driver_id=step_data.get("driver_id"), multiple=True)

        for driver in drivers:
            leases, _ = lease_service.get_lease(db, driver_id=driver.driver_id, multiple=True)
            if len(leases) > 0:
                for lease in leases:
                    medallion = medallion_service.get_medallion(db, medallion_id=lease.medallion_id)
                    vehicle = vehicle_service.get_vehicles(db, vehicle_id=lease.vehicle_id)
                    if not medallion or not vehicle:
                        logger.info("vehicle or medallion not found for lease %s", lease.id)
                        continue
                    dtr = ledger_service.generate_driver_transactions_receipts(
                        db,
                        driver_id=driver.id,
                        medallion_id=medallion.id,
                        vehicle_id=vehicle.id,
                        lease_id=lease.id,
                        start_date=start_dt,
                        end_date=end_dt
                    )
                    dtr_data = ledger_service.generate_dtr_data(db, dtr.receipt_number)
                    dtr_html_key = generate_dtr_html_doc(dtr_data)
                    dtr_pdf_key = generate_dtr_pdf_doc(dtr_data)
                    dtr_excel_key = generate_dtr_excel_doc_styled(dtr_data)
                    ledger_service.update_dtr(db, dtr.id, {
                        "receipt_html_key": dtr_html_key,
                        "receipt_pdf_key": dtr_pdf_key,
                        "receipt_excel_key": dtr_excel_key,
                    })
            else:
                logger.info("No leases found for driver %s", driver.id)
                continue
        if not case_entity:
            case_entity = bpm_service.create_case_entity(
                db=db, case_no=case_no,
                entity_name=entity_mapper['DPC'],
                identifier=entity_mapper["DPC_IDENTIFIER"],
                identifier_value=dtr.id
            )

        return "Ok"
    except Exception as e:
        logger.error("Error processing choose pay period: %s", e, exc_info=True)
        raise e

@step(step_id="168", name="Fetch - View Driver Payments", operation="fetch")
def fetch_driver_payments(db, case_no, case_params=None):
    """Fetch the driver payments for the view driver payments step"""
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        start_date = None
        end_date = None
        page = None
        per_page = None

        if case_params:
            start_date = case_params.get("start_date")
            end_date = case_params.get("end_date")
            per_page = case_params.get("per_page", 10)
            page = case_params.get("page", 1)
        if case_entity:
            dtr = ledger_service.get_dtr(
                db, dtr_id=case_entity.identifier_value
            )
            if dtr:
                start_date = dtr.period_start
                end_date = dtr.period_end

        if not start_date or not end_date:
            logger.error("Start date and end date are required for fetching driver payments.")
            return {}
        
        curb_trips = ledger_service.view_driver_payments(
            db, start_date=start_date, end_date=end_date,
            page=page, per_page=per_page
        )

        if not curb_trips:
            return {}

        return curb_trips
    except Exception as e:
        logger.error("Error fetching driver payments: %s", e, exc_info=True)

@step(step_id="168", name="Process - View Driver Payments", operation="process")
def process_view_driver_payments(db, case_no, step_data):
    """Process the view driver payments step"""
    try:
        return "Ok"
    except Exception as e:
        logger.error("Error processing view driver payments: %s", e, exc_info=True)
        raise e

@step(step_id="169", name="Fetch - Approve Driver Payments", operation="fetch")
def fetch_approve_driver_payments(db, case_no, case_params=None):
    """Fetch the approve driver payments for the approve driver payments step"""
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)
        start_date = None
        end_date = None

        if case_params:
            start_date = case_params.get("start_date")
            end_date = case_params.get("end_date")
        if case_entity:
            dtr = ledger_service.get_dtr(
                db, dtr_id=case_entity.identifier_value
            )
            if dtr:
                start_date = dtr.period_start
                end_date = dtr.period_end

        if not start_date or not end_date:
            logger.error("Start date and end date are required for fetching approve driver payments.")
            return {}
        
        logger.info("Fetching approve driver payments from %s to %s", start_date, end_date)
        curb_trips = curb_service.finalize_driver_payments(
            db, start_date=start_date, end_date=end_date
        )

        if not curb_trips:
            return {}

        return curb_trips
    except Exception as e:
        logger.error("Error fetching approve driver payments: %s", e, exc_info=True)
        raise e

@step(step_id="169", name="Process - Approve Driver Payments", operation="process")
def process_approve_driver_payments(db, case_no, step_data):
    """Process the approve driver payments step"""
    try:
        return "Ok"
    except Exception as e:
        logger.error("Error processing approve driver payments: %s", e, exc_info=True)
        raise e
