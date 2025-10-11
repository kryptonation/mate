# Third party imports
import pandas as pd
from sqlalchemy.orm import Session
import random

# Local imports
from app.core.config import settings
from app.core.db import SessionLocal
from app.utils.logger import get_logger
from app.utils.s3_utils import s3_utils
from app.medallions.models import Medallion
from app.utils.general import generate_random_6_digit

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1

def parse_medallions(db: Session, df: pd.DataFrame):
    """Parse medallions"""
    try:
        for _, row in df.iterrows():
            medallion_numbers = row.get('medallion_number')
            medallion_type = row.get('medallion_type')
            owner_type = row.get('owner_type')
            medallion_status = row.get('medallion_status')
            medallion_renewal_date = row.get('medallion_renewal_date')
            validity_start_date = row.get('validity_start_date')
            validity_end_date = row.get('validity_end_date')
            last_renewal_date = row.get('last_renewal_date')
            fs6_status = row.get('fs6_status')
            fs6_date = row.get('fs6_date')

        # Convert dates to Python datetime objects
            def convert_date(date_str):
                if pd.notnull(date_str) and isinstance(date_str, pd.Timestamp):
                    try:
                        return date_str.to_pydatetime()
                    except ValueError:
                        logger.warning("Invalid date format: %s. Skipping.", date_str)
                        return None
                return None

            medallion_renewal_date = convert_date(medallion_renewal_date)
            validity_start_date = convert_date(validity_start_date)
            validity_end_date = convert_date(validity_end_date)
            last_renewal_date = convert_date(last_renewal_date)
            fs6_date = convert_date(fs6_date)

            # Check if medallion already exists
            medallion = db.query(Medallion).filter(Medallion.medallion_number == medallion_numbers).first()

            if medallion is not None:
                # Update existing medallion
                logger.info("Updating existing medallion: %s", medallion_numbers)
                medallion.medallion_type = medallion_type
                medallion.owner_type = owner_type
                medallion.medallion_status = medallion_status
                medallion.medallion_renewal_date = medallion_renewal_date
                medallion.validity_start_date = validity_start_date
                medallion.validity_end_date = validity_end_date
                medallion.last_renewal_date = last_renewal_date
                medallion.fs6_status = fs6_status
                medallion.fs6_date = fs6_date
                medallion.owner_id = random.randint(1,9)
            else:
                # Insert new medallion
                logger.info("Inserting new medallion: %s", medallion_numbers)
                medallion = Medallion(
                    medallion_number=medallion_numbers,
                    medallion_type=medallion_type,
                    owner_type=owner_type,
                    medallion_status=medallion_status,
                    medallion_renewal_date=medallion_renewal_date,
                    default_amount=generate_random_6_digit(),
                    validity_start_date=validity_start_date,
                    validity_end_date=validity_end_date,
                    last_renewal_date=last_renewal_date,
                    fs6_status=fs6_status,
                    fs6_date=fs6_date,
                    owner_id = random.randint(1,9)
                )
                db.add(medallion)
                db.commit()
    except Exception as e:
        logger.error("Error parsing medallions: %s", e)
        db.rollback()
        raise e

if __name__ == "__main__":
    db_session = SessionLocal()
    excel_file = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    medallion_df = pd.read_excel(excel_file, 'medallion')
    parse_medallions(db_session, medallion_df)
    db_session.close()

    
    