# Standard library imports
from datetime import datetime

# Third party imports
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session

# Local imports
from app.core.config import settings
from app.core.db import SessionLocal
from app.utils.logger import get_logger
from app.entities.services import entity_service
from app.utils.s3_utils import s3_utils
from app.entities.models import Address, BankAccount
from app.drivers.models import DMVLicense, Driver, TLCLicense

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1


def parse_date(date_val):
    """
    Parses a date value into a datetime object.
    If the value is invalid or empty, returns None.
    """
    try:
        return date_val.to_pydatetime() if pd.notnull(date_val) else None
    except Exception:
        return None


def parse_drivers(db: Session, df: pd.DataFrame):
    """
    Parse the drivers dataframe and insert into the database.
    """
    try:
        # Clean column names and replace NaNs
        df.columns = df.columns.str.strip().str.lower()
        df = df.replace({np.nan: None})

        # Operation counters
        created_drivers = 0
        updated_drivers = 0
        created_dmv_licenses = 0
        updated_dmv_licenses = 0
        created_tlc_licenses = 0
        updated_tlc_licenses = 0
        created_addresses = 0
        updated_addresses = 0
        created_bank_accounts = 0
        updated_bank_accounts = 0

        for _, row in df.iterrows():
            # Fetch or create Driver
            driver_id = row.get("driver_id")
            driver = db.query(Driver).filter(Driver.driver_id == driver_id).first()

            if not driver:
                driver = Driver(driver_id=driver_id)
                db.add(driver)
                created_drivers += 1
            else:
                updated_drivers += 1

            # Update Driver personal details
            driver.first_name = row.get("first_name")
            driver.middle_name = row.get("middle_name")
            driver.last_name = row.get("last_name")
            driver.ssn = row.get("ssn")
            driver.full_name = " ".join(filter(None, [part.strip() if part else None for part in [driver.first_name, driver.middle_name, driver.last_name]]))
            driver.dob = parse_date(row.get("dob"))
            driver.phone_number_1 = row.get("phone_number_1")
            driver.phone_number_2 = row.get("phone_number_2")
            driver.email_address = row.get("email_address")
            driver.driver_status = row.get("driver_status")
            driver.drive_locked = row.get("driver_locked") or False

            # DMV License details
            dmv_license = driver.dmv_license or DMVLicense()
            dmv_license.dmv_license_number = row.get("dmv_license_number")
            dmv_license.dmv_license_issued_state = row.get("dmv_license_issued_state")
            dmv_license.is_dmv_license_active = row.get("is_dmv_license_active") == "True"
            dmv_license.dmv_license_expiry_date = parse_date(row.get("dmv_license_expiry_date"))

            if not driver.dmv_license:
                db.add(dmv_license)
                driver.dmv_license = dmv_license
                created_dmv_licenses += 1
            else:
                updated_dmv_licenses += 1

            # TLC License details
            tlc_license = driver.tlc_license or TLCLicense()
            tlc_license.tlc_license_number = row.get("tlc_license_number")
            tlc_license.tlc_issued_state = row.get("tlc_issued_state")
            tlc_license.is_tlc_license_active = row.get("is_tlc_license_active") == "True"
            tlc_license.tlc_license_expiry_date = parse_date(row.get("tlc_license_expiry_date"))

            if not driver.tlc_license:
                db.add(tlc_license)
                driver.tlc_license = tlc_license
                created_tlc_licenses += 1
            else:
                updated_tlc_licenses += 1

            # Address details
            primary_address = entity_service.get_address(db=db , address_line_1=row.get("primary_address_line_1"))
            if not primary_address:
                primary_address = entity_service.upsert_address(db=db , address_data={"address_line_1": row.get("primary_address_line_1")})
                driver.primary_address_id = primary_address.id
                created_addresses += 1
            else:
                driver.primary_address_id = primary_address.id
                updated_addresses += 1

            # Bank Account details
            if row.get("pay_to_mode") == "ACH":
                bank_account = driver.driver_bank_account or BankAccount()
                bank_account.bank_name = row.get("bank_name")
                bank_account.bank_account_number = row.get("bank_account_number")
                if not driver.driver_bank_account:
                    db.add(bank_account)
                    driver.driver_bank_account = bank_account
                    created_bank_accounts += 1
                else:
                    updated_bank_accounts += 1

            db.commit()

        return {
            "drivers_created": created_drivers,
            "drivers_updated": updated_drivers,
            "dmv_licenses_created": created_dmv_licenses,
            "dmv_licenses_updated": updated_dmv_licenses,
            "tlc_licenses_created": created_tlc_licenses,
            "tlc_licenses_updated": updated_tlc_licenses,
            "addresses_created": created_addresses,
            "addresses_updated": updated_addresses,
            "bank_accounts_created": created_bank_accounts,
            "bank_accounts_updated": updated_bank_accounts,
        }
    except Exception as e:
        logger.error(f"Error parsing driver dataframe: {e}")
        raise e


if __name__ == "__main__":
    db_session = SessionLocal()
    excel_file = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    drivers_df = pd.read_excel(excel_file, 'drivers')
    parse_drivers(db_session, drivers_df)
    db_session.close()
