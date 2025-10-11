# Standard library imports
from datetime import datetime, timezone

# Third party imports
import pandas as pd
from sqlalchemy.orm import Session

# Local imports
from app.core.config import settings
from app.core.db import SessionLocal
from app.utils.logger import get_logger
from app.utils.s3_utils import s3_utils
from app.entities.models import Entity, Address, Individual, Corporation, BankAccount , CorporationPayee

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1

def parse_corporation(db: Session, df: pd.DataFrame):
    """Parse corporation"""
    try:
        for i, row in df.iterrows():
            # Lookup Address by address_line_1
            address = db.query(Address).filter_by(
                address_line_1=row['primary_address']).first()
            if not address:
                logger.info(
                    "Address '%s' not found. Skipping corporation: %s",
                    row['primary_address'],
                    row['corporation_name']
                )
                continue
            # Lookup BankAccount by bank account number
            bank_account = db.query(BankAccount).filter_by(
                bank_account_number=row['bank_account_number']).first()

            # Lookup Entity by entity_ein
            # entity = db.query(Entity).filter_by(ein=row['ein']).first()
            # entity_id = entity.id if entity else None  # Use None if not found

            # Lookup Bank by bank account number
            
            # Check if the corporation exists
            corporation = db.query(Corporation).filter_by(
                name=row['corporation_name']).first()
            
            is_holding_entity = i % 2 == 0  # Example logic for holding entity
            if is_holding_entity:
                logger.info("Corporation %s is a holding entity", row['corporation_name'])

            if corporation:
                # Update existing corporation
                corporation.ein = row['ein']
                corporation.primary_address_id = address.id
                corporation.primary_contact_number = row['primary_contact_number']
                corporation.primary_email_address = row['primary_email_address']
                corporation.is_active = row['is_active'] == 'True'
                corporation.is_holding_entity = is_holding_entity
                # corporation.entity_id = entity_id
                # corporation.member = row['member']
                # corporation.manager = row['manager']
                corporation.linked_pad_owner_id=row['linked_pad_owner_id'] if 'linked_pad_owner_id' in row else None,
                corporation.is_llc = row['is_llc'] == 'Y'
                corporation.modified_by = SUPERADMIN_USER_ID
                corporation.modified_date = datetime.now(timezone.utc)

                logger.info("Updated corporation: %s", corporation.name)
            else:
                # Create new corporation
                corporation = Corporation(
                    name=row['corporation_name'],
                    registered_date=pd.to_datetime(row['registered_date']) if not pd.isna(
                        row['registered_date']) else None,
                    ein=row['ein'],
                    primary_address_id=address.id,
                    primary_contact_number=row['primary_contact_number'],
                    primary_email_address=row['primary_email_address'],
                    is_active=row['is_active'] == 'True',
                    is_holding_entity=is_holding_entity,
                    # entity_id=entity_id,
                    # member=row['member'],
                    # manager=row['manager'],
                    linked_pad_owner_id=row['linked_pad_owner_id'] if 'linked_pad_owner_id' in row else None,
                    is_llc=row['is_llc'] == 'Y',
                    created_by=SUPERADMIN_USER_ID,
                )
                db.add(corporation)
                logger.info("Created new corporation: %s", row['corporation_name'])
                db.flush()

            if bank_account:
                corporation_payee = db.query(CorporationPayee).filter_by(
                    bank_account_id=bank_account.id,
                    corporation_id=corporation.id
                ).first()

                if not corporation_payee:
                    corporation_payee = CorporationPayee(
                        corporation_id=corporation.id,
                        bank_account_id=bank_account.id,
                        pay_to_mode="ACH",
                        payee_type="Corporation",
                        corporation_owner_id=corporation.id,
                        sequence=0,
                        allocation_percentage=100.0,
                        created_by=SUPERADMIN_USER_ID
                    )
                    db.add(corporation_payee)
                else:
                    corporation_payee.pay_to_mode = "ACH"
                    corporation_payee.allocation_percentage = 100.0
                    corporation_payee.modified_by = SUPERADMIN_USER_ID
                    corporation_payee.modified_date = datetime.now(timezone.utc)

            db.commit()
            logger.info("Added Corporation Payee for corporation: %s", row['corporation_name'])
            
    except Exception as e:
        logger.error("Error parsing corporation: %s", e)
        db.rollback()
        raise


if __name__ == "__main__":
    logger.info("Loading Corporation information")
    db_session = SessionLocal()
    excel_file = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    corporation_df = pd.read_excel(excel_file, 'corporation')
    parse_corporation(db_session, corporation_df)

