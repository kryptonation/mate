# Standard library imports
from datetime import datetime

# Third party imports
import pandas as pd
from sqlalchemy.orm import Session

# Local imports
from app.core.db import SessionLocal
from app.core.config import settings
from app.utils.logger import get_logger
from app.utils.s3_utils import s3_utils
from app.vehicles.models import Vehicle, VehicleHackUp
from app.medallions.models import Medallion
from app.medallions.schemas import MedallionStatus
from app.vehicles.schemas import VehicleStatus

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1

def parse_vehicle_hackup_information(db: Session, df: pd.DataFrame):
    """
    Parses the vehicle hackup information from the excel file and upserts the data into the database.
    """
    try:
        for _, row in df.iterrows():
            vehicle_vin = row.get('vin')
            tpep_provider = row.get('tpep_provider')
            configuration_type = row.get('configuration_type')
            is_paint_completed = row.get('is_paint_completed') if pd.notna(row.get('is_paint_completed')) else False
            paint_completed_date = row.get('paint_completed_date')
            paint_completed_charges = row.get('paint_completed_charges') if pd.notna(row.get('paint_completed_charges')) else None
            is_camera_installed = row.get('is_camera_installed')
            camera_installed_date = row.get('camera_installed_date')
            camera_installed_charges = row.get('camera_installed_charges') if pd.notna(row.get('camera_installed_charges')) else None
            camera_type = row.get('camera_type') if pd.notna(row.get('camera_type')) else None
            is_partition_installed = row.get('is_partition_installed')
            partition_installed_date = row.get('partition_installed_date')
            partition_installed_charges = row.get('partition_installed_charges') if pd.notna(row.get('partition_installed_charges')) else None
            partition_type = row.get('partition_type') if pd.notna(row.get('partition_type')) else None
            is_meter_installed = row.get('is_meter_installed')
            meter_installed_date = row.get('meter_installed_date')
            meter_type = row.get('meter_type') if pd.notna(row.get('meter_type')) else None
            meter_serial_number = row.get('meter_serial_number')
            meter_installed_charges = row.get('meter_installed_charges') if pd.notna(row.get('meter_installed_charges')) else None
            is_rooftop_installed = row.get('is_rooftop_installed')
            rooftop_type = row.get('rooftop_type') if pd.notna(row.get('rooftop_type')) else None
            rooftop_installed_date = row.get('rooftop_installed_date') if pd.notna(row.get('rooftop_installed_date')) else None
            rooftop_installation_charges = row.get('rooftop_installation_charges') if pd.notna(row.get('rooftop_installation_charges')) else None
            status = row.get('status')

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

            paint_completed_date = convert_date(paint_completed_date)
            camera_installed_date = convert_date(camera_installed_date)
            partition_installed_date = convert_date(partition_installed_date)
            meter_installed_date = convert_date(meter_installed_date)
            rooftop_installed_date = convert_date(rooftop_installed_date)

            # Get Vehicle ID from VIN
            vehicle = db.query(Vehicle).filter_by(vin=vehicle_vin).first()
            medallion = db.query(Medallion).filter_by(id=vehicle.medallion_id).first()

            if not vehicle:
                logger.warning("No vehicle found for VIN: %s. Skipping.", vehicle_vin)
                continue

            vehicle_id = vehicle.id

            # Check if vehicle hackup already exists
            vehicle_hackup = db.query(VehicleHackUp).filter_by(
                vehicle_id=vehicle_id).first()

            if vehicle_hackup is not None:
                # Update existing hackup details
                logger.info("Updating existing vehicle installation for VIN: %s", vehicle_vin)
                vehicle_hackup.tpep_provider = tpep_provider
                vehicle_hackup.configuration_type = configuration_type
                vehicle_hackup.is_paint_completed = is_paint_completed
                vehicle_hackup.paint_completed_date = paint_completed_date
                vehicle_hackup.paint_completed_charges = paint_completed_charges
                vehicle_hackup.is_camera_installed = is_camera_installed
                vehicle_hackup.camera_installed_date = camera_installed_date
                vehicle_hackup.camera_installed_charges = camera_installed_charges
                vehicle_hackup.camera_type = camera_type
                vehicle_hackup.is_partition_installed = is_partition_installed
                vehicle_hackup.partition_installed_date = partition_installed_date
                vehicle_hackup.partition_installed_charges = partition_installed_charges
                vehicle_hackup.partition_type = partition_type
                vehicle_hackup.is_meter_installed = is_meter_installed
                vehicle_hackup.meter_installed_date = meter_installed_date
                vehicle_hackup.meter_type = meter_type
                vehicle_hackup.meter_serial_number = meter_serial_number
                vehicle_hackup.meter_installed_charges = meter_installed_charges
                vehicle_hackup.is_rooftop_installed = is_rooftop_installed
                vehicle_hackup.rooftop_type = rooftop_type
                vehicle_hackup.rooftop_installed_date = rooftop_installed_date
                vehicle_hackup.rooftop_installation_charges = rooftop_installation_charges
                vehicle_hackup.status = status
            else:
                # Insert new vehicle hackup
                logger.info("Inserting new vehicle hackup for VIN: %s", vehicle_vin)
                vehicle_hackup = VehicleHackUp(
                    vehicle_id=vehicle_id,
                    tpep_provider=tpep_provider,
                    configuration_type=configuration_type,
                    is_paint_completed=is_paint_completed,
                    paint_completed_date=paint_completed_date,
                    paint_completed_charges=paint_completed_charges,
                    is_camera_installed=is_camera_installed,
                    camera_installed_date=camera_installed_date,
                    camera_installed_charges=camera_installed_charges,
                    camera_type=camera_type,
                    is_partition_installed=is_partition_installed,
                    partition_installed_date=partition_installed_date,
                    partition_installed_charges=partition_installed_charges,
                    partition_type=partition_type,
                    is_meter_installed=is_meter_installed,
                    meter_installed_date=meter_installed_date,
                    meter_type=meter_type,
                    meter_serial_number=meter_serial_number,
                    meter_installed_charges=meter_installed_charges,
                    is_rooftop_installed=is_rooftop_installed,
                    rooftop_type=rooftop_type,
                    rooftop_installed_date=rooftop_installed_date,
                    rooftop_installation_charges=rooftop_installation_charges,
                    status=status
                )
                vehicle.vehicle_status = VehicleStatus.HACKED_UP
                medallion.medallion_status = MedallionStatus.ACTIVE

                db.add(vehicle_hackup)
                db.add(vehicle)
                db.add(medallion)

        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Error parsing vehicle hackup data: %s", e)
        raise


if __name__ == "__main__":
    logger.info("Loading Vehicle Hackup Information")
    session = SessionLocal()
    xls = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    installation_df = pd.read_excel(xls, 'vehicle_hackups')
    parse_vehicle_hackup_information(session, installation_df)
    logger.info("Vehicle Hackup Information Seeded Successfully ✅")
