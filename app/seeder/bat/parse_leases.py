# Third party imports
import pandas as pd
import datetime
from sqlalchemy.orm import Session

# Local imports
from app.core.config import settings
from app.core.db import SessionLocal
from app.utils.logger import get_logger
from app.utils.s3_utils import s3_utils
from app.leases.models import Lease
from app.vehicles.models import Vehicle
from app.vehicles.schemas import VehicleStatus
from app.medallions.models import Medallion

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1

def parse_lease(db:Session , df: pd.DataFrame) :
    """parse Lease"""

    try:
        for _, row in df.iterrows():
            lease_id = row.get('lease_id')
            lease_type = row.get('lease_type')
            medallion_number = row.get('medallion_number')
            vin = row.get('vin')
            lease_start_date = row.get('lease_start_date')
            lease_end_date = row.get('lease_end_date')
            duration_in_weeks = row.get('duration_in_weeks')
            is_auto_renewed = row.get('is_auto_renewed')
            lease_date = row.get('lease_date')
            lease_status = row.get("lease_status")
            lease_pay_day = row.get("lease_pay_day")
            lease_payments_type = row.get("lease_payments_type")
            cancellation_fee = row.get("cancellation_fee")

            # convert data to datetime form
            def convert_date(date_str):
                if pd.notnull(date_str):
                    try:
                        if hasattr(date_str , "to_pydatetime"):
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
            
            lease_start_date = convert_date(lease_start_date)
            lease_end_date = convert_date(lease_end_date)
            lease_date = convert_date(lease_date)


            medallion = db.query(Medallion).filter_by(medallion_number=medallion_number).first()
            if not medallion:
                logger.warning("No medallion found for medallion number: %s. Skipping.", medallion_number)
                continue

            medallion_id = medallion.id

            vehicle = db.query(Vehicle).filter_by(vin=vin).first()
            if not vehicle:
                logger.warning("No vehicle found for VIN: %s. Skipping.", vin)
                continue

            vehicle_id = vehicle.id
            vehicle.vehicle_status = VehicleStatus.ACTIVE
            vehicle.is_active = True

            vehicle_lease = db.query(Lease).filter_by(vehicle_id=vehicle_id, medallion_id=medallion_id).first()

            if vehicle_lease is not None :
                # update the exiting Lease
                vehicle_lease.lease_type = lease_type
                vehicle_lease.lease_start_date = lease_start_date
                vehicle_lease.lease_end_date = lease_end_date
                vehicle_lease.duration_in_weeks = duration_in_weeks
                vehicle_lease.is_auto_renewed = is_auto_renewed
                vehicle_lease.lease_date = lease_date 
                vehicle_lease.is_active = True
                vehicle_lease.lease_status = lease_status
                vehicle_lease.lease_pay_day = lease_pay_day
                vehicle_lease.lease_payments_type = lease_payments_type
                vehicle_lease.cancellation_fee = cancellation_fee
            
            else:
                # create a new lease
                logger.info("Creating new lease for VIN: %s and medallion number: %s")
                lease = Lease(
                    lease_id=lease_id,
                    lease_type=lease_type,
                    medallion_id=medallion_id,
                    vehicle_id=vehicle_id,
                    lease_start_date=lease_start_date,
                    lease_end_date=lease_end_date,
                    duration_in_weeks=duration_in_weeks,
                    is_auto_renewed=is_auto_renewed,
                    lease_date=lease_date,
                    lease_status=lease_status,
                    lease_pay_day=lease_pay_day,
                    lease_payments_type=lease_payments_type,
                    cancellation_fee=cancellation_fee ,
                    is_active = True
                )

                db.add(lease)

        db.commit()
    except Exception as e :
        db.rollback()
        logger.error("Error parsing Lease data: %s", e)
        raise

if __name__ == "__main__":
    logger.info("Loading Lease Information")
    session = SessionLocal()
    xls = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    installation_df = pd.read_excel(xls, 'leases')
    parse_lease(session, installation_df)
    logger.info("Lease Information loaded successfully ✅")


