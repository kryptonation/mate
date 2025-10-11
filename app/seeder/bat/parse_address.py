# Standard library imports
from datetime import datetime

# Third party imports
import pandas as pd
from sqlalchemy.orm import Session

# Local imports
from app.core.config import settings
from app.core.db import SessionLocal
from app.utils.logger import get_logger
from app.utils.s3_utils import s3_utils
from app.entities.models import Address, Entity
from app.vehicles.models import Vehicle
from app.medallions.models import MedallionOwner
from app.drivers.models import Driver
from app.leases.models import Lease

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1

def parse_address(db: Session, df: pd.DataFrame):
    """Parse address"""
    try:
        for _, row in df.iterrows():
            # Check if the address already exists
            existing_address = db.query(Address).filter_by(
                address_line_1=row['address_line_1']).first()
            if existing_address:
                logger.info(
                    "Address already exists: %s. Skipping.", row['address_line_1']
                )
                continue

            # Create a new Address object
            new_address = Address(
                address_line_1=row['address_line_1'],
                address_line_2=row.get('address_line_2') if pd.notna(row['address_line_2']) else None,
                city=row.get('city'),
                state=row.get('state'),
                zip=row.get('zip'),
                latitude=row.get('latitude'),
                longitude=row.get('longitude'),
                from_date=row["from_date"].to_pydatetime() if pd.notna(row['from_date']) else None,
                to_date=row["to_date"].to_pydatetime() if pd.notna(row['to_date']) else None,
                is_active=True,
                created_by=SUPERADMIN_USER_ID,
                created_on=datetime.now()
            )

            # Add the new address to the session
            db.add(new_address)
            logger.info("Added new address: %s", row['address_line_1'])

        # Commit all changes to the database
        db.commit()
    except Exception as e:
        logger.error("Error parsing address: %s", e)
        raise


if __name__ == "__main__":
    logger.info("Loading Address from excel")
    db_session = SessionLocal()
    excel_file = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    address_df = pd.read_excel(excel_file, 'address')
    parse_address(db=db_session, df=address_df)
            