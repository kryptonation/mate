# Third party imports
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy.exc import NoResultFound

# Local imports
from app.core.config import settings
from app.core.db import SessionLocal
from app.utils.logger import get_logger
from app.utils.s3_utils import s3_utils
from app.entities.models import Address, Individual, BankAccount

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1

def get_address_id(db: Session, address_line_1: str):
    """
    Lookup address ID using address_line_1.

    Args:
        session: The database session
        address_line_1: The address line to lookup

    Returns:
        ID of the address if found, else None
    """
    try:
        logger.info("Looking up address %s", address_line_1)
        address = db.query(Address).filter_by(address_line_1=address_line_1).first()
        return address.id if address else None
    except NoResultFound:
        logger.warning("Address '%s' not found in the database.", address_line_1)
        return None

def parse_individuals(db: Session, df: pd.DataFrame):
    """Parse individuals"""
    try:
        for _, row in df.iterrows():
            full_name = row.get('full_name')
            first_name = row.get('first_name')
            middle_name = row.get('middle_name')
            last_name = row.get('last_name')
            primary_address_line_1 = row.get('primary_address')
            secondary_address_line_1 = row.get('secondary_address') if pd.notna(row.get('secondary_address')) else None
            masked_ssn = row.get('masked_ssn')
            dob = row.get('dob')
            passport = row.get('passport')
            passport_expiry_date = row.get('passport_expiry_date')
            primary_contact_number = row.get('primary_contact_number')
            additional_phone_number_1 = row.get('additional_phone_number_1')
            additional_phone_number_2 = row.get('additional_phone_number_2')
            primary_email_address = row.get('primary_email_address')

            # Lookup Address ID
            primary_address_id = get_address_id(db, primary_address_line_1)
            secondary_address_id = get_address_id(db, secondary_address_line_1) if secondary_address_line_1 else None

            if not primary_address_id:
                logger.warning("Skipping individual '%s' due to missing primary address.", full_name)
                continue
            # Lookup Bank by bank account number
            bank_account = db.query(BankAccount).filter_by(
                bank_account_number=row['bank_account_number']).first()
            # Check if individual already exists
            individual = db.query(Individual).filter_by(full_name=full_name).one_or_none()

            if individual:
                # Update existing individual
                logger.info("Updating existing individual: %s", full_name)
                individual.first_name = first_name
                individual.middle_name = middle_name
                individual.last_name = last_name
                individual.primary_address_id = primary_address_id
                individual.secondary_address_id = secondary_address_id
                individual.masked_ssn = masked_ssn
                individual.dob = dob
                individual.passport = passport
                individual.passport_expiry_date = pd.to_datetime(passport_expiry_date) if pd.notna(passport_expiry_date) else None
                individual.primary_contact_number = primary_contact_number
                individual.additional_phone_number_1 = additional_phone_number_1 if pd.notna(additional_phone_number_1) else None
                individual.additional_phone_number_2 = additional_phone_number_2 if pd.notna(additional_phone_number_2) else None
                individual.primary_email_address = primary_email_address
                individual.is_active = True
                individual.modified_by = SUPERADMIN_USER_ID  # Update modified_by for updates
                individual.bank_account = bank_account if bank_account else None
            else:
                # Insert new individual
                logger.info("Inserting new individual: %s", full_name)
                new_individual = Individual(
                    first_name=first_name,
                    middle_name=middle_name if pd.notna(middle_name) else None,
                    last_name=last_name,
                    primary_address_id=primary_address_id,
                    secondary_address_id=secondary_address_id,
                    masked_ssn=masked_ssn,
                    dob=dob,
                    passport=passport,
                    passport_expiry_date=pd.to_datetime(passport_expiry_date) if pd.notna(passport_expiry_date) else None,
                    full_name=full_name,
                    primary_contact_number=primary_contact_number,
                    additional_phone_number_1=additional_phone_number_1 if pd.notna(additional_phone_number_1) else None,
                    additional_phone_number_2=additional_phone_number_2 if pd.notna(additional_phone_number_2) else None,
                    primary_email_address=primary_email_address,
                    is_active=True,
                    created_by=SUPERADMIN_USER_ID,  # Set created_by for new records
                    bank_account = bank_account if bank_account else None,
                )
                db.add(new_individual)

        logger.info("Individual data parsed and committed successfully.")
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("Error parsing individual data: %s", e)
        raise

if __name__ == "__main__":
    logger.info("Loading Individual information")
    db_session = SessionLocal()
    excel_file = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    individual_df = pd.read_excel(excel_file, 'individual')
    parse_individuals(db_session, individual_df)