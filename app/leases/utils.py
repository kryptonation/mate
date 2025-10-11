### app/leases/utils.py

# Standard imports
import json
import re
from datetime import date, datetime, timedelta, timezone

from dateutil.rrule import DAILY, WEEKLY, rrule
from sqlalchemy.orm import Session

# Local imports
from app.core.config import settings
from app.leases.models import Lease, LeaseConfiguration
from app.medallions.models import Medallion
from app.utils.lambda_utils import invoke_lambda_function
from app.utils.logger import get_logger
from app.vehicles.models import Vehicle

logger = get_logger(__name__)


def generate_medallion_lease_document(db: Session, lease: Lease, authorized_agent: str):
    """Generate medallion lease document"""
    try:
        for driver in lease.lease_driver:
            # Prepare payload for Lambda function
            payload = {
                "data": prepare_medallion_lease_document(db, lease, authorized_agent),
                "bucket": settings.s3_bucket_name,
                "identifier": f"form_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "template_id": settings.medallion_lease_template_id,
            }

            logger.info("Calling Lambda function with payload: %s", payload)

            response = invoke_lambda_function(
                function_name="pdf_filler", payload=payload
            )

            # Extract s3_key from response
            logger.info("Response from Lambda: %s", response)
            response_body = json.loads(response["body"])
            s3_key = response_body.get("s3_key")  # Use the output key we specified

            return {
                "document_name": f"Medallion Lease Document for Lease ID {lease.lease_id} for Driver ID {driver.driver_id}",
                "document_format": "PDF",
                "document_path": s3_key,
                "document_type": "driver_medallion_lease",
                "object_type": f"co-leasee-{driver.co_lease_seq}",
                "object_lookup_id": str(driver.id),
                "document_note": "Medallion lease document created",
                "document_date": datetime.now(timezone.utc).isoformat().split("T")[0],
            }
    except Exception as e:
        logger.error("Error generating medallion lease document: %s", str(e))
        raise e


def generate_dov_vehicle_lease_document(db, lease, authorized_agent):
    """Generate vehicle lease document"""
    try:
        for driver in lease.lease_driver:
            # Prepare payload for Lambda function
            payload = {
                "data": prepare_vehicle_lease_document(db, lease, authorized_agent),
                "bucket": settings.s3_bucket_name,
                "identifier": f"form_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "template_id": settings.dov_vehicle_lease_template_id,
            }

            logger.info("Calling Lambda function with payload: %s", payload)

            response = invoke_lambda_function(
                function_name="pdf_filler", payload=payload
            )

            # Extract s3_key from response
            logger.info("Response from Lambda: %s", response)
            response_body = json.loads(response["body"])
            s3_key = response_body.get("s3_key")  # Use the output key we specified
            return {
                "document_name": f"Vehicle Lease Document for Lease ID {lease.lease_id} for Driver ID {driver.driver_id}",
                "document_format": "PDF",
                "document_path": s3_key,
                "document_type": "driver_vehicle_lease",
                "object_type": f"co-leasee-{driver.co_lease_seq}",
                "object_lookup_id": str(driver.id),
                "document_date": datetime.now(timezone.utc).isoformat().split("T")[0],
                "document_note": "Vehicle lease document created.",
            }
    except Exception as e:
        logger.error("Error generating vehicle lease document: %s", str(e))
        raise e


def prepare_medallion_lease_document(
    db: Session, lease: Lease = None, authorized_agent: str = ""
):
    driver_lease_assoc = lease.lease_driver[0] if lease.lease_driver else None
    driver = driver_lease_assoc.driver if driver_lease_assoc else None
    vehicle = lease.vehicle
    medallion = lease.medallion

    active_reg = (
        next((reg for reg in vehicle.registrations if reg.is_active), None)
        if vehicle and vehicle.registrations
        else None
    )
    active_hackup = (
        next((hu for hu in vehicle.hackups if hu.is_active), None)
        if vehicle and vehicle.hackups
        else None
    )

    # --- 2. Retrieve all financial components from LeaseConfiguration ---
    configs = (
        db.query(LeaseConfiguration)
        .filter(LeaseConfiguration.lease_id == lease.id)
        .all()
    )

    def get_config_value(key: str) -> float:
        """Helper to safely get a numeric value from the configurations list."""
        config = next((c for c in configs if c.lease_breakup_type == key), None)
        return float(config.lease_limit) if config and config.lease_limit else 0.0

    med_lease = get_config_value("med_lease")

    medallion_lease_document_info = {
        "date_of_agreement": (lease.lease_date or lease.created_on).strftime(
            settings.common_date_format
        ),
        "manager_name": settings.bat_manager_name,
        "driver_name": driver.full_name if driver else "N/A",
        "driver_address": _format_address(driver.primary_driver_address)
        if driver
        else "N/A",
        "driver_primary_phone": _format_us_phone_number(driver.phone_number_1)
        if driver
        else "N/A",
        "driver_email": driver.email_address if driver else "N/A",
        "driver_ssn": driver.ssn if driver else "N/A",
        "driver_dmv_license": driver.dmv_license.dmv_license_number
        if driver and driver.dmv_license
        else "N/A",
        "driver_dmv_expiry": driver.dmv_license.dmv_license_expiry_date.strftime(
            settings.common_date_format
        )
        if driver and driver.dmv_license and driver.dmv_license.dmv_license_expiry_date
        else "N/A",
        "driver_tlc_license": driver.tlc_license.tlc_license_number
        if driver and driver.tlc_license
        else "N/A",
        "driver_tlc_expiry": driver.tlc_license.tlc_license_expiry_date.strftime(
            settings.common_date_format
        )
        if driver and driver.tlc_license and driver.tlc_license.tlc_license_expiry_date
        else "N/A",
        "medallion_number": medallion.medallion_number if medallion else "N/A",
        "plate_number": active_reg.plate_number if active_reg else "N/A",
        "vehicle_make": vehicle.make if vehicle else "N/A",
        "vehicle_vin": vehicle.vin if vehicle else "N/A",
        "vehicle_year": vehicle.year if vehicle else "N/A",
        "vehicle_meter_make": active_hackup.meter_type if active_hackup else "N/A",
        "vehicle_meter_serial_number": active_hackup.meter_serial_number
        if active_hackup
        else "N/A",
        "lease_start_date": lease.lease_start_date.strftime(settings.common_date_format)
        if lease.lease_start_date
        else "N/A",
        "lease_end_date": lease.lease_end_date.strftime(settings.common_date_format)
        if lease.lease_end_date
        else "N/A",
        "medallion_lease_payment": str(f"$ {med_lease:.2f}" or "$ 0.00"),
        "total_weeks": str(lease.duration_in_weeks or 0),
        "total_payment_for_lease_term": str(
            f"$ {med_lease * lease.duration_in_weeks:,.2f}"
        ),
        "payment_due_day": settings.payment_date,
        "security_deposit": str(f"$ {lease.deposit_amount_paid:.2f}" or "$ 0.00"),
        "additional_balance_due": "$ 0.00",
        "security_deposit_holding_account_number": settings.security_deposit_holding_number,
        "authorized_agent": settings.bat_authorized_agent,
        "bat_manager": settings.bat_manager_name,
        "agent_sign_date": date.today().strftime(settings.common_date_format),
        "images": [
            {
                "path": settings.common_signature_file,
                "page": 13,
                "x": 280,
                "y": 165,
                "width": 180,
                "height": 15,
                "opacity": 0.8,
            },
        ],
    }
    return medallion_lease_document_info


def _format_address(address_obj) -> str:
    """Helper function to format an address object into a single string."""
    if not address_obj:
        return "N/A"
    parts = [
        address_obj.address_line_1,
        address_obj.address_line_2,
        address_obj.city,
        address_obj.state,
        address_obj.zip,
    ]
    return ", ".join(part for part in parts if part)


def _format_us_phone_number(phone: str) -> str:
    """
    Formats a US phone number to (XXX) XXX-XXXX if valid.
    If invalid, returns the original input.

    :param phone: Raw phone number string
    :return: Formatted or original phone number
    """
    digits = re.sub(r"\D", "", phone)

    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]

    if len(digits) != 10:
        return phone  # Return original if not valid

    area_code = digits[:3]
    central_office = digits[3:6]
    line_number = digits[6:]

    return f"({area_code}) {central_office}-{line_number}"


def prepare_vehicle_lease_document(
    db: Session, lease: Lease, authorized_agent: str
) -> dict:
    """
    Prepare vehicle lease document with dynamic data from the lease object,
    populating the specific dov_vehicle_lease_template structure.
    """

    # --- 1. Get all related objects from the lease, with safety checks ---
    driver_lease_assoc = lease.lease_driver[0] if lease.lease_driver else None
    driver = driver_lease_assoc.driver if driver_lease_assoc else None
    vehicle = lease.vehicle
    medallion = lease.medallion

    active_reg = (
        next((reg for reg in vehicle.registrations if reg.is_active), None)
        if vehicle and vehicle.registrations
        else None
    )
    active_hackup = (
        next((hu for hu in vehicle.hackups if hu.is_active), None)
        if vehicle and vehicle.hackups
        else None
    )

    # --- 2. Retrieve all financial components from LeaseConfiguration ---
    configs = (
        db.query(LeaseConfiguration)
        .filter(LeaseConfiguration.lease_id == lease.id)
        .all()
    )

    def get_config_value(key: str) -> float:
        """Helper to safely get a numeric value from the configurations list."""
        config = next((c for c in configs if c.lease_breakup_type == key), None)
        return float(config.lease_limit) if config and config.lease_limit else 0.0

    lease_weekly_payment = get_config_value("veh_lease")
    vehicle_sales_tax = get_config_value("veh_sales_tax")
    tlc_inspection_fee = get_config_value("tlc_inspection_fees")
    time_stamps_amount = get_config_value("tax_stamps")
    vehicle_registration_amount = get_config_value("registration")

    total_weekly_lease_amount = get_config_value("total_vehicle_lease")
    term_lease_payment = total_weekly_lease_amount * (lease.duration_in_weeks or 0)

    # --- 4. Populate the template dictionary ---
    dov_vehicle_lease_template = {
        "date_of_agreement": (lease.lease_date or lease.created_on).strftime(
            settings.common_date_format
        ),
        "manager_name": settings.bat_manager_name,
        "driver_name": driver.full_name if driver else "N/A",
        "driver_address": _format_address(driver.primary_driver_address)
        if driver
        else "N/A",
        "driver_primary_phone": _format_us_phone_number(driver.phone_number_1)
        if driver
        else "N/A",
        "driver_email": driver.email_address if driver else "N/A",
        "driver_ssn": driver.ssn if driver else "N/A",
        "driver_dmv_license": driver.dmv_license.dmv_license_number
        if driver and driver.dmv_license
        else "N/A",
        "driver_dmv_expiry": driver.dmv_license.dmv_license_expiry_date.strftime(
            settings.common_date_format
        )
        if driver and driver.dmv_license and driver.dmv_license.dmv_license_expiry_date
        else "N/A",
        "driver_tlc_license": driver.tlc_license.tlc_license_number
        if driver and driver.tlc_license
        else "N/A",
        "driver_tlc_expiry": driver.tlc_license.tlc_license_expiry_date.strftime(
            settings.common_date_format
        )
        if driver and driver.tlc_license and driver.tlc_license.tlc_license_expiry_date
        else "N/A",
        "medallion_number": medallion.medallion_number if medallion else "N/A",
        "plate_number": active_reg.plate_number if active_reg else "N/A",
        "vehicle_make": vehicle.make if vehicle else "N/A",
        "vehicle_vin": vehicle.vin if vehicle else "N/A",
        "vehicle_year": vehicle.year if vehicle else "N/A",
        "vehicle_meter_make": active_hackup.meter_type if active_hackup else "N/A",
        "vehicle_meter_serial_number": active_hackup.meter_serial_number
        if active_hackup
        else "N/A",
        "lease_start_date": lease.lease_start_date.strftime(settings.common_date_format)
        if lease.lease_start_date
        else "N/A",
        "lease_end_date": lease.lease_end_date.strftime(settings.common_date_format)
        if lease.lease_end_date
        else "N/A",
        "vehicle_sales_tax": f"$ {vehicle_sales_tax:.2f}",
        "tlc_inspection_fee": f"$ {tlc_inspection_fee:.2f}",
        "time_stamps_amount": f"$ {time_stamps_amount:.2f}",
        "vehicle_registration_amount": f"$ {vehicle_registration_amount:.2f}",
        "total_weekly_lease_amount": f"$ {total_weekly_lease_amount:.2f}",
        "payment_due_day": settings.payment_date,
        "term_lease_payment": f"$ {term_lease_payment:.2f}",
        "vehicle_base_price": "$ 0.00",  # str(vehicle.base_price or "0.00"),
        "lease_weekly_payment": f"$ {lease_weekly_payment:.2f}",
        "total_weeks": str(lease.duration_in_weeks or 0),
        "lease_additional_dues": "$ 0.00",
        "security_deposit": str(f"$ {lease.deposit_amount_paid}" or "$ 0.00"),
        "located_at": settings.security_deposit_located_at,
        "lease_id": lease.lease_id or "",
        "security_deposit_holding_account_number": settings.security_deposit_holding_number,
        "security_deposit_holding_bank": settings.security_deposit_holding_bank,
        "authorized_agent": settings.bat_authorized_agent,
        "agent_sign_date": date.today().strftime(settings.common_date_format),
        "bat_manager": settings.bat_manager_name,
        "images": [
            {
                "path": settings.common_signature_file,
                "page": 16,
                "x": 300,
                "y": 380,
                "width": 180,
                "height": 15,
                "opacity": 0.8,
            },
        ],
    }

    return dov_vehicle_lease_template


DAY_NAME_TO_NUM = {"mon": 0, "tus": 1, "wen": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def calculate_weekly_lease_schedule(
    lease_start_date: datetime = None,
    duration_weeks: int = 26,
    payment_due_day: str = "mon",
    weekly_lease_amount: float = 1200.00,
):
    try:
        day_num = DAY_NAME_TO_NUM[payment_due_day.strip().lower()]

        # Step 1: Find first due date on the specified payment day
        days_ahead = (day_num - lease_start_date.weekday() + 7) % 7
        first_due_date = lease_start_date + timedelta(days=days_ahead)

        # Step 2: Generate schedule using rrule
        schedule = []
        for i, dt in enumerate(
            rrule(freq=WEEKLY, count=duration_weeks, dtstart=first_due_date)
        ):
            schedule.append(
                {
                    "installment_no": i + 1,
                    "due_date": dt.date(),
                    "amount_due": weekly_lease_amount,
                }
            )

        return schedule
    except Exception as e:
        logger.error("Error calculating weekly lease schedule: %s", str(e))
        raise e


def calculate_short_term_lease_schedule(
    lease_start_date: datetime, duration_days: int, daily_lease_amount: float
):
    try:
        schedule = []
        for i, dt in enumerate(
            rrule(freq=DAILY, count=duration_days, dtstart=lease_start_date)
        ):
            schedule.append(
                {
                    "installment_no": i + 1,
                    "due_date": dt.date(),
                    "amount_due": daily_lease_amount,
                }
            )

        return schedule
    except Exception as e:
        logger.error("Error calculating short term lease schedule: %s", str(e))
        raise e
