# app/ezpass/utils.py

import re
import csv
from datetime import datetime
from typing import List, Dict

from fastapi import UploadFile, HTTPException

from app.utils.logger import get_logger

logger = get_logger(__name__)

def extract_amount(value: str) -> float:
    """
    Extracts a numeric amount from a string, handling currency symbols,
    commas, and parentheses for negative values.
    """
    if not value or not isinstance(value, str):
        return 0.0
    
    value = value.strip()
    is_negative = value.startswith('(') and value.endswith(')')
    
    # Remove all non-numeric characters except for the decimal point
    cleaned_value = re.sub(r"[^0-9.]", "", value)
    
    if not cleaned_value:
        return 0.0
        
    amount = float(cleaned_value)
    
    return -amount if is_negative else amount

def validate_ezpass_file(file: UploadFile) -> List[Dict]:
    """
    Validates the new EZPass CSV file format, extracts headers,
    and filters out non-transactional rows.
    """
    try:
        content = file.file.read().decode("utf-8").splitlines()
        
        # The header might have trailing commas, clean it up.
        header_line = content[0].strip().rstrip(',')
        headers = [h.strip() for h in header_line.split(',')]
        
        # Use the cleaned headers with DictReader
        reader = csv.DictReader(content[1:], fieldnames=headers)

        expected_fields = {
            "Lane Txn ID", "Tag/Plate #", "Agency", "Date", "Exit Time", "Amount"
        }

        if not expected_fields.issubset(set(headers)):
            missing = expected_fields - set(headers)
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file format. Missing required fields: {', '.join(missing)}"
            )
        
        # Filter out rows that are not actual transactions
        transactional_rows = []
        for row in reader:
            # A valid transaction must have a Transaction ID. Financial adjustments do not.
            if row.get("Lane Txn ID") and row.get("Lane Txn ID").strip():
                transactional_rows.append(row)

        return transactional_rows

    except Exception as e:
        logger.error(f"Failed to validate or parse EZPass file: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process EZPass file: {str(e)}"
        ) from e