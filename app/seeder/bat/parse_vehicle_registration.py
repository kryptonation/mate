# Standard library imports
from datetime import datetime

# Third party imports
import pandas as pd
from sqlalchemy.orm import Session

# Local imports
from app.core.db import SessionLocal
from app.utils.logger import get_logger
from app.core.config import settings
from app.vehicles.models import Vehicle, VehicleRegistration  # Import models
from app.utils.s3_utils import s3_utils

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1


def parse_vehicle_registration_information(db: Session, df: pd.DataFrame):
    """
    Parses the vehicle registration information from the excel file and upserts the data into the database.
    """
    try:
        for _, row in df.iterrows():
            vehicle_vin = row.get('vin')
            registration_date = row.get('registration_date')
            registration_expiry_date = row.get('registration_expiry_date')
            registration_fee = row.get('registration_fee')
            plate_number = row.get('plate_number')
            status = row.get('status')
            registration_state = row.get('registration_state')
            registration_class = row.get('registration_class')

            # Convert dates to datetime objects
            def convert_date(date_str):
                if pd.notnull(date_str):
                    try:
                        if hasattr(date_str, 'to_pydatetime'):
                            return date_str.to_pydatetime()
                        elif isinstance(date_str, datetime):
                            return date_str
                        else:
                            logger.warning("Unexpected date format: %s. Skipping.", date_str)
                            return None
                    except ValueError:
                        logger.warning("Invalid date format: %s. Skipping.", date_str)
                        return None
                return None

            registration_date = convert_date(registration_date)
            registration_expiry_date = convert_date(registration_expiry_date)

            # Get vehicle_id using VIN
            vehicle = db.query(Vehicle).filter_by(vin=vehicle_vin).first()
            if not vehicle:
                logger.warning("No vehicle found for VIN: %s. Skipping.", vehicle_vin)
                continue

            vehicle_id = vehicle.id

            # Check if vehicle registration already exists
            vehicle_registration = db.query(VehicleRegistration).filter_by(
                vehicle_id=vehicle_id).first()

            if vehicle_registration:
                # Update Existing Record
                logger.info("Updating existing vehicle registration for VIN: %s", vehicle_vin)
                vehicle_registration.registration_date = registration_date
                vehicle_registration.registration_expiry_date = registration_expiry_date
                vehicle_registration.registration_fee = registration_fee
                vehicle_registration.plate_number = plate_number
                vehicle_registration.status = status
                vehicle_registration.registration_class = registration_class
                vehicle_registration.registration_state = registration_state
            else:
                # Insert New Record
                logger.info("Inserting new vehicle registration for VIN: %s", vehicle_vin)
                vehicle_registration = VehicleRegistration(
                    vehicle_id=vehicle_id,
                    registration_date=registration_date,
                    registration_expiry_date=registration_expiry_date,
                    registration_fee=registration_fee,
                    plate_number=plate_number,
                    registration_state=registration_state,
                    registration_class=registration_class,
                    created_by=SUPERADMIN_USER_ID,
                    status=status
                )
                db.add(vehicle_registration)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Error parsing vehicle registration data: %s", e)
        raise


if __name__ == "__main__":
    logger.info("Loading Vehicle Registration Information")
    db_session = SessionLocal()
    excel_file = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    registration_df = pd.read_excel(excel_file, 'vehicle_registration')
    parse_vehicle_registration_information(db_session, registration_df)
    db_session.close()
    logger.info("Vehicle Registration Information Seeded Successfully ✅")