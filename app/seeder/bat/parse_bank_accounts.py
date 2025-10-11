# Third party imports
import pandas as pd
from sqlalchemy.orm import Session

# Local imports
from app.core.config import settings
from app.core.db import SessionLocal
from app.utils.logger import get_logger
from app.utils.s3_utils import s3_utils
from app.entities.models import BankAccount, Address

logger = get_logger(__name__)
SUPERADMIN_USER_ID = 1

def parse_bank_accounts(db: Session, df: pd.DataFrame):
    """Parse bank accounts"""
    try:
        for _, row in df.iterrows():
            # Lookup or create the address
            address = db.query(Address).filter(
                Address.address_line_1 == row['bank_address']).first()
            if not address:
                address = Address(address_line_1=row['bank_address'])
                db.add(address)
                db.flush()
                db.refresh(address)
                logger.info(
                    "Address '%s' added to the Address table.", row['bank_address']
                )

            # Check if a bank account exists with the same bank name and account number
            bank_account = db.query(BankAccount).filter(
                BankAccount.bank_name == row['bank_name'],
                BankAccount.bank_account_number == row['bank_account_number']
            ).first()

            if bank_account:
                # Update existing bank account
                logger.info(
                    "Updating bank account for '%s' with account number '%s'.",
                    row['bank_name'], row['bank_account_number']
                )
                bank_account.bank_account_status = row['bank_account_status']
                bank_account.bank_routing_number = row['bank_routing_number']
                bank_account.bank_account_type = row['bank_account_type']
                bank_account.bank_address_id = address.id
            else:
                # Insert new bank account
                logger.info(
                    "Adding new bank account for '%s' with account number '%s'.",
                    row['bank_name'], row['bank_account_number']
                )
                new_bank_account = BankAccount(
                    bank_name=row['bank_name'],
                    bank_account_number=row['bank_account_number'],
                    bank_account_status=row['bank_account_status'],
                    bank_routing_number=row['bank_routing_number'],
                    bank_account_type=row['bank_account_type'],
                    bank_address_id=address.id
                )
                db.add(new_bank_account)

        db.commit()
    except Exception as e:
        logger.error("Error parsing bank accounts: %s", e)
        raise


if __name__ == "__main__":
    logger.info("Loading Bank Account information")
    db_session = SessionLocal()
    excel_file = pd.ExcelFile(s3_utils.download_file(settings.bat_file_key))
    bank_accounts_df = pd.read_excel(excel_file, 'bank_accounts')
    parse_bank_accounts(db_session, bank_accounts_df)