## app/bpm_flows/vehicle_hackup/flows.py

# Standard library imports
from datetime import datetime, timedelta

from app.audit_trail.services import audit_trail_service
from app.bpm.services import bpm_service

# Local imports
from app.bpm.step_info import step
from app.utils.logger import get_logger
from app.medallions.schemas import MedallionStatus
from app.medallions.services import medallion_service
from app.medallions.utils import format_medallion_response
from app.uploads.services import upload_service
from app.vehicles.schemas import HackupStatus, RegistrationStatus, VehicleStatus
from app.vehicles.services import vehicle_service

logger = get_logger(__name__)
entity_mapper = {
    "VEHICLE": "vehicles",
    "VEHICLE_IDENTIFIER": "id",
}


@step(step_id="125", name="Fetch - Return vehicle hackup ", operation="fetch")
def fetch_vehicle_hackup_information(db, case_no, case_params=None):
    """
    Fetch the vehicle hackup information for the vehicle hackup step
    """
    try:
        # Get the case entity
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        vehicle = None
        if case_params:
            vehicle = vehicle_service.get_vehicles(db, vin=case_params["object_lookup"])
        if case_entity:
            vehicle = vehicle_service.get_vehicles(
                db, vehicle_id=int(case_entity.identifier_value)
            )

        # Initialize hackup_info as a dict
        hackup_info = {}
        medallion = None
        if vehicle.medallions:
            medallion = format_medallion_response(medallion=vehicle.medallions)
        # Vehicle info section
        hackup_info["vehicle_info"] = {
            **vehicle.to_dict(),
            "medallion_number": medallion["medallion_number"] if medallion else None,
            "medallion_owner": medallion["medallion_owner"] if medallion else None,
        }

        # Hackup info section
        hack_model = vehicle_service.get_vehicle_hackup(db, vehicle_id=vehicle.id)
        hackup_info["hackup_info"] = (
            hack_model.to_dict()
            if hack_model
            else {"message": "No active hackup found for the vehicle."}
        )

        # Register info
        register_info = vehicle_service.get_vehicle_registration(
            db, vehicle_id=vehicle.id
        )
        hackup_info["register_info"] = register_info.to_dict() if register_info else {}

        # Documents section
        hackup_info["documents"] = {
            "register_document": upload_service.get_documents(
                db=db,
                object_type="vehicle",
                object_id=vehicle.id,
                document_type="vehicle_registration_document",
            ),
            "registration_fee_document": upload_service.get_documents(
                db=db,
                object_type="vehicle",
                object_id=vehicle.id,
                document_type="registration_fee_document",
            ),
        }

        hackup_info["upload_info"] = {
            "object_type": entity_mapper["VEHICLE"],
            "object_id": vehicle.id,
            "document_type": [
                "vehicle_registration_document",
                "registration_fee_document",
            ],
        }
        return hackup_info

    except Exception as e:
        logger.error("Error fetching vehicle hackup information: %s", e)
        raise e


@step(step_id="125", name="Process - Create case with new vehicle", operation="process")
def process_vehicle_hackup_information(db, case_no, step_data):
    """
    Process the vehicle hackup information for the vehicle hackup step
    """
    try:
        # If a case already exists for this step then we should not process it
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        vehicle = vehicle_service.get_vehicles(db, vin=step_data["vin"])

        if not case_entity:
            case_entity = bpm_service.create_case_entity(
                db=db,
                case_no=case_no,
                entity_name=entity_mapper["VEHICLE"],
                identifier=entity_mapper["VEHICLE_IDENTIFIER"],
                identifier_value=str(vehicle.id),
            )
            logger.info("Case entity %s created ", case_entity.id)

        if step_data["vin"] != vehicle.vin:
            raise ValueError("VIN in data does not match the vehicle's VIN")

        if vehicle.is_medallion_assigned == False:
            raise ValueError("Medallion not assigned to vehicle")

        hackup = vehicle_service.get_vehicle_hackup(
            db,
            vehicle_id=vehicle.id,
            hackup_status=HackupStatus.ACTIVE,
            sort_order="desc",
        )

        registration = vehicle_service.get_vehicle_registration(
            db,
            vehicle_id=vehicle.id,
            registration_status=RegistrationStatus.ACTIVE,
            sort_order="desc",
        )
        if not registration:
            registration = vehicle_service.upsert_registration(
                db,
                {
                    "vehicle_id": vehicle.id,
                    "status": RegistrationStatus.ACTIVE,
                    "registration_date": datetime.now().date(),
                    "registration_expiry_date": datetime.now().date()
                    + timedelta(days=365),
                    "plate_number": "IG245",
                },
            )

        if not hackup:
            hackup = vehicle_service.upsert_vehicle_hackup(
                db, {"vehicle_id": vehicle.id, "status": HackupStatus.ACTIVE}
            )

        vehicle = vehicle_service.upsert_vehicle(
            db,
            {
                "id": vehicle.id,
                "vehicle_status": VehicleStatus.HACK_UP_IN_PROGRESS,
            },
        )

        fields = [
            "tpep_provider",
            "configuration_type",
            "is_paint_completed",
            "paint_completed_date",
            "paint_completed_charges",
            "is_camera_installed",
            "camera_type",
            "camera_installed_date",
            "camera_installed_charges",
            "is_partition_installed",
            "partition_type",
            "partition_installed_date",
            "partition_installed_charges",
            "is_meter_installed",
            "meter_installed_date",
            "meter_type",
            "meter_serial_number",
            "meter_installed_charges",
            "is_rooftop_installed",
            "rooftop_type",
            "rooftop_installed_date",
            "rooftop_installation_charges",
        ]

        hackup_data = {}

        hackup_details = step_data.get("hackup_details", {})

        for field in fields:
            if field not in hackup_details:
                continue

            value = hackup_details[field]
            if field.endswith("_date"):
                if value:
                    try:
                        hackup_data[field] = datetime.strptime(value, "%Y-%m-%d").date()
                    except ValueError:
                        logger.error(
                            f"Invalid date format for field '{field}': {value}"
                        )
            else:
                hackup_data[field] = value

        # Create vehicle hack up information
        hackup = vehicle_service.upsert_vehicle_hackup(
            db, {"id": hackup.id, **hackup_data}
        )

        vehicle_register_details = step_data.get("vehicle_register_details", {})

        register_fields = [
            "plate_number",
            "registration_date",
            "registration_expiry_date",
            "registration_fee",
        ]

        register_data = {}

        for field in register_fields:
            if field not in vehicle_register_details:
                continue

            value = vehicle_register_details[field]

            if field.endswith("_date") and field in vehicle_register_details.keys():
                if vehicle_register_details[field] == "":
                    continue
                register_data[field] = datetime.strptime(
                    vehicle_register_details[field], "%Y-%m-%d"
                ).date()
            else:
                register_data[field] = value

        # Create vehicle registration information
        registration = vehicle_service.upsert_registration(
            db, {"id": registration.id, **register_data}
        )

        return "Ok"
    except Exception as e:
        logger.error("Error processing vehicle hackup information: %s", e)
        raise e


@step(
    step_id="126", name="Fetch - Return vehicle inspection details ", operation="fetch"
)
def fetch_vehicle_inspection_details(db, case_no, case_params=None):
    """
    Fetch the vehicle registration details for the vehicle hackup step
    """
    try:
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        vehicle = None
        if case_params:
            vehicle = vehicle_service.get_vehicles(db, vin=case_params["object_lookup"])
        if case_entity:
            vehicle = vehicle_service.get_vehicles(
                db, vehicle_id=int(case_entity.identifier_value)
            )

        inspection_info = {}
        inspection_info["vehicle_info"] = {
            **vehicle.to_dict(),
            "medallion_number": "IG245",
            "medallion_owner": "John Smith",
        }
        latest_inspection = vehicle_service.get_inspection(
            db,
            vehicle_id=vehicle.id,
            inspection_status=RegistrationStatus.ACTIVE,
            sort_order="desc",
        )
        inspection_info["inspection_info"] = (
            latest_inspection.to_dict()
            if latest_inspection
            else {"message": "No active inspection found for the vehicle."}
        )
        inspection_info["meter_inspection_report_document"] = (
            upload_service.get_documents(
                db,
                object_type="vehicle",
                object_id=vehicle.id,
                document_type="meter_inspection_report_document",
            )
        )
        inspection_info["rate_card_document"] = upload_service.get_documents(
            db,
            object_type="vehicle",
            object_id=vehicle.id,
            document_type="rate_card_document",
        )
        inspection_info["inspection_receipt_document"] = upload_service.get_documents(
            db,
            object_type="vehicle",
            object_id=vehicle.id,
            document_type="inspection_receipt_document",
        )

        return inspection_info
    except Exception as e:
        logger.error("Error fetching vehicle inspection details: %s", e)
        raise e


@step(
    step_id="126",
    name="process - Return vehicle inspection details ",
    operation="process",
)
def process_vehicle_insepction_details(db, case_no, step_data):
    """
    Process the vehicle registration details for the vehicle hackup step
    """
    try:
        # If a case already exists for this step then we should not process it
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        vehicle = vehicle_service.get_vehicles(
            db, vehicle_id=int(case_entity.identifier_value)
        )

        # Create vehicle inspection information
        inspection = vehicle_service.get_inspection(
            db,
            vehicle_id=vehicle.id,
            inspection_status=RegistrationStatus.ACTIVE,
            sort_order="desc",
        )

        if not inspection:
            inspection = vehicle_service.upsert_inspection(
                db, {"vehicle_id": vehicle.id, "status": RegistrationStatus.ACTIVE}
            )

        vehicle_hackup = vehicle_service.get_vehicle_hackup(
            db=db, vehicle_id=vehicle.id
        )
        if vehicle_hackup:
            vehicle_service.upsert_vehicle_hackup(
                db=db,
                vehicle_hackup_data={
                    "id": vehicle_hackup.id,
                    "status": HackupStatus.ACTIVE,
                },
            )

        inspection_data = {}
        fields = [
            "mile_run",
            "inspection_date",
            "inspection_time",
            "inspection_fee",
            "result",
            "next_inspection_due_date",
        ]
        for field in fields:
            if field in step_data.keys():
                if step_data[field] == "":
                    continue
                if field.endswith("_date") and step_data[field]:
                    inspection_data[field] = datetime.strptime(
                        step_data[field], "%Y-%m-%d"
                    ).date()
                else:
                    inspection_data[field] = step_data[field]

        inspection = vehicle_service.upsert_inspection(
            db, {"id": inspection.id, **inspection_data}
        )

        vehicle = vehicle_service.upsert_vehicle(
            db, {"id": vehicle.id, "vehicle_status": VehicleStatus.HACKED_UP}
        )

        medallion = medallion_service.get_medallion(
            db, medallion_id=vehicle.medallion_id
        )
        medallion_service.upsert_medallion(
            db, {"id": medallion.id, "medallion_status": MedallionStatus.ACTIVE}
        )
        return "Ok"
    except Exception as e:
        logger.error("Error processing vehicle inspection details: %s", e)
        raise e


@step(step_id="127", name="Fetch - Return upload invoices details ", operation="fetch")
def fetch_upload_invoices_fetch(db, case_no, case_params=None):
    """
    Fetch the vehicle inspection details for the vehicle hackup step
    """
    try:
        # If a case already exists for this step then we should not process it
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        vehicle = None
        if case_params:
            vehicle = vehicle_service.get_vehicles(db, vin=case_params["object_lookup"])
        if case_entity:
            vehicle = vehicle_service.get_vehicles(
                db, vehicle_id=int(case_entity.identifier_value)
            )

        hackup_info = {}
        hackup_info["vehicle_info"] = {
            **vehicle.to_dict(),
            "medallion_number": "IG245",
            "medallion_owner": "John Smith",
        }
        hack_info = vehicle_service.get_vehicle_hackup(db, vehicle_id=vehicle.id)
        hackup_info["hackup_info"] = (
            hack_info.to_dict()
            if hack_info
            else {"message": "No active hackup found for the vehicle."}
        )
        camera_invoice_document = upload_service.get_documents(
            db,
            object_type="vehicle",
            object_id=vehicle.id,
            document_type="camera_invoice_document",
        )
        paint_invoice_document = upload_service.get_documents(
            db,
            object_type="vehicle",
            object_id=vehicle.id,
            document_type="paint_invoice_document",
        )
        meter_inspection_report_document = upload_service.get_documents(
            db,
            object_type="vehicle",
            object_id=vehicle.id,
            document_type="meter_inspection_report_document",
        )
        rooftop_invoice_document = upload_service.get_documents(
            db,
            object_type="vehicle",
            object_id=vehicle.id,
            document_type="rooftop_invoice_document",
        )

        hackup_info["documents"] = [
            camera_invoice_document,
            paint_invoice_document,
            meter_inspection_report_document,
            rooftop_invoice_document,
        ]

        hackup_info["upload_info"] = {
            "object_type": entity_mapper["VEHICLE"],
            "object_id": vehicle.id,
            "document_type": [
                "camera_invoice_document",
                "paint_invoice_document",
                "meter_inspection_report_document",
                "rooftop_invoice_document",
            ],
        }

        return hackup_info
    except Exception as e:
        logger.error("Error fetching vehicle hackup information: %s", e)
        raise e


@step(step_id="127", name="Process - upload invoices details ", operation="process")
def process_upload_invoices_process(db, case_no, step_data):
    """
    Process the vehicle inspection details for the vehicle hackup step
    """
    try:
        # If a case already exists for this step then we should not process it
        case_entity = bpm_service.get_case_entity(db, case_no=case_no)

        vehicle = vehicle_service.get_vehicles(
            db, vehicle_id=int(case_entity.identifier_value)
        )

        # Create vehicle inspection information
        inspection = vehicle_service.get_inspection(
            db,
            vehicle_id=vehicle.id,
            inspection_status=RegistrationStatus.ACTIVE,
            sort_order="desc",
        )

        cases = bpm_service.get_cases(db=db , case_no= case_no ,multiple=True)
        if cases:
            case_ids = [case.id for case in cases]
            audits = audit_trail_service.get_audit_trail_by_case_ids(db, case_ids)
            for audit in audits:
                audit_trail_service.update_audit_trail(db=db , audit_id=audit.id , update_data={"meta_data": {"vehicle_id": vehicle.id , "medallion_id": vehicle.medallion_id}})

        return "Ok"
    except Exception as e:
        logger.error("Error processing vehicle inspection details: %s", e)
        raise e
