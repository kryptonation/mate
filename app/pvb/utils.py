### app/pvb/utils.py

# Standard library import
import csv

# Third party imports
from fastapi import HTTPException, UploadFile

# Local imports
from app.utils.logger import get_logger

logger = get_logger(__name__)

def valid_pvb_csv(file: UploadFile) -> list[dict]:
    """Validate the CSV files of the pvb"""
    try:
        content = file.file.read().decode("utf-8").splitlines()
        reader = csv.DictReader(content)

        expected = {
            "SUMMONS", "PLATE", "STATE", "TYPE", "ISSUE DATE",
            "ISSUE TIME", "AMOUNT DUE"
        }
        if not expected.issubset(set(reader.fieldnames)):
            raise HTTPException(status_code=400, detail="Invalid CSV file")
        
        return list(reader)
    except Exception as e:
        logger.error("Error validating PVB CSV file: %s", str(e))
        raise HTTPException(status_code=500, detail="Error validating PVB CSV file") from e