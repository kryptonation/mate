import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound

# Local imports
from app.core.config import settings
from app.core.db import SessionLocal
from app.utils.logger import get_logger
from app.utils.s3_utils import s3_utils
from app.entities.models import Address
from app.vehicles.models import VehicleEntity

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1

def parse_vehicle_entity(db: Session , df : pd.DataFrame):
    """Parse vehicle entity"""
    try:
        for _, row in df.iterrows():
            entity_name = row.get('entity_name')
            ein = row.get("ein")
            entity_address = row.get('entity_address_line_1')
            corporate_officer = row.get('corporate_officer')

            try:
                address = db.query(Address).filter(
                    Address.address_line_1 == entity_address
                ).first()
                entity_address_id = address.id
            except NoResultFound:
                logger.warning(
                    "Address '%s' not found in the database. Skipping entity '%s'.",
                    entity_address, entity_name
                )
                continue
            
            entity = db.query(VehicleEntity).filter(
                VehicleEntity.entity_name == entity_name
            ).first()

            if entity:
                entity.ein = ein
                entity.entity_address_id = entity_address_id
                entity.entity_status = "Active"
            else:
                entity = VehicleEntity(
                    entity_name=entity_name,
                    ein=ein,
                    entity_address_id=entity_address_id,
                    entity_status="Active"
                )
                db.add(entity)
        
        logger.info("Vehicle Entity data parsed and committed successfully.")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Error parsing vehicle entity data: %s", e)
        raise

if __name__ == "__main__":
    logger.info("Loading Entity information")
    db_session = SessionLocal()
    excel_file = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    entity_df = pd.read_excel(excel_file, 'vehicle_entity')
    parse_vehicle_entity(db_session, entity_df)



