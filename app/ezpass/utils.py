# app/ezpass/utils.py

"""
Enhanced utility functions for EZPass module with real CSV format support
"""

import csv
import re
from datetime import datetime, date, time
from typing import List, Dict, Any
from io import StringIO
from decimal import Decimal

from fastapi import UploadFile
import pandas as pd

from app.ezpass.exceptions import EZPassFileValidationException
from app.utils.logger import get_logger

logger = get_logger(__name__)


def validate_ezpass_file(file: UploadFile) -> List[Dict[str, Any]]:
    """
    Validate and parse EZPass file (CSV or Excel) matching client format.

    Expected columns from client CSV:
    - Lane Txn ID: Transaction identifier
    - Tag/Plate #: Vehicle plate number
    - Agency: Toll agency
    - Entry Plaza: Entry location
    - Exit Plaza: Exit location
    - Class: Vehicle class
    - Date: Transaction date
    - Exit Time: Transaction time
    - Amount: Transaction amount

    Args:
        file: Uploaded file object

    Returns:
        List of dictionaries containing parsed transaction data

    Raises:
        EZPassFileValidationException: If file format is invalid or required columns are missing
    """
    logger.info("Validating EZPass file", filename=file.filename)

    try:
        # === Check the file extension ===
        filename = file.filename.lower()

        if filename.endswith(".csv"):
            rows = _parse_csv_file(file)
        elif filename.endswith((".xls", ".xlsx")):
            rows = _parse_excel_file(file)
        else:
            raise EZPassFileValidationException(
                "Invalid file format. Only CSV and Excel files are supported."
            )
        
        # === Validate parsed data ===
        validated_rows = _validate_rows(rows)

        logger.info(
            "File validation successful",
            filename=file.filename,
            rows_count=len(validated_rows),
        )

        return validated_rows
    
    except EZPassFileValidationException:
        raise
    except Exception as e:
        logger.error("Error validating file", filename=file.filename, error=str(e))
        raise EZPassFileValidationException(f"File validation error: {str(e)}")
    

def _parse_csv_file(file: UploadFile) -> List[Dict[str, Any]]:
    """Parse CSV file"""
    try:
        content = file.file.read().decode("utf-8")

        # === Hanlde BOM if present ===
        if content.startswith('\ufeff'):
            content = content[1:]

        csv_reader = csv.DictReader(StringIO(content))
        rows = list(csv_reader)

        logger.debug("CSV file parsed", rows_count=len(rows))
        return rows
    
    except Exception as e:
        logger.error("Error parsing CSV file", error=str(e))
        raise EZPassFileValidationException(f"CSV parsing error: {str(e)}")
    

def _parse_excel_file(file: UploadFile) -> List[Dict[str, Any]]:
    """Parse Excel file"""
    try:
        df = pd.read_excel(file.file)
        # === Drop completely empty rows ===
        df = df.dropna(how="all")
        rows = df.to_dict("records")

        logger.debug("Excel file parsed", rows_count=len(rows))
        return rows
    
    except Exception as e:
        logger.error("Error parsing excel file", error=str(e))
        raise EZPassFileValidationException(f"Excel parsing error: {str(e)}")
    

def _validate_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate and normalize row data matching client CSV format.

    Expected columns:
    - Lane Txn ID: Transaction ID (required)
    - Tag/Plate #: Plate number (required)
    - Agency: Agency name (optional)
    - Entry Plaza: Entry location (optional)
    - Exit Plaza: Exit location (optional)
    - Class: Vehicle class (optional)
    - Date: Transaction date (required)
    - Exit Time: Transaction time (optional)
    - Amount: Transaction amount (required)
    """
    if not rows:
        raise EZPassFileValidationException("File is empty")
    
    required_fields = ["date", "amount", "tag_plate"]
    validated_rows = []
    errors = []

    for idx, row in enumerate(rows, start=1):
        try:
            # === Normalize column names (case-insensitive matching) ===
            normalized_row = _normalize_column_names(row)

            # === Skip empty rows ===
            if not any(normalized_row.values()):
                continue

            # === Validate required fields ===
            for field in required_fields:
                if field not in normalized_row or not normalized_row[field]:
                    raise ValueError(f"Missing required field: {field}")
                
            # === Parse and validate data types ===
            validated_row = {
                "transaction_id": _get_value(
                    normalized_row,
                    "lane_txn_id", "lane_transaction_id", "transaction_id", "txn_id"
                ),
                "transaction_date": _parse_date(
                    _get_value(normalized_row, "date", "transaction_date", "txn_date")
                ),
                "transaction_time": _parse_time(
                    _get_value(normalized_row, "exit_time", "time", "transaction_time")
                ),
                "plate_no": _get_value(
                    normalized_row, "tag_plate", "tag_plate_number", "plate_no", "plate_number",
                    "license_plate", "plate",
                ),
                "tag_or_plate": _get_value(
                    normalized_row, "tag_plate", "tag_plate_number", "tag", default="",
                ),
                "agency": _get_value(
                    normalized_row, "agency", "agency_name", "toll_agency",
                ),
                "entry_plaza": _get_value(
                    normalized_row, "entry_plaza", "entry", "entry_location",
                ),
                "exit_plaza": _get_value(
                    normalized_row, "exit_plaza", "exit", "exit_location",
                ),
                "vehicle_class": _get_value(
                    normalized_row, "class", "vehicle_class", "veh_class",
                ),
                "amount": _parse_amount(
                    _get_value(normalized_row, "amount", "toll_amount", "fee"),
                )
            }

            validated_rows.append(validated_row)

        except Exception as e:
            error_msg = f"Row {idx} validation failed: {str(e)}"
            logger.warning(error_msg, row=row)
            errors.append(error_msg)
            # === Continue processing other rows instead of failing completely ===
            continue

    if not validated_rows:
        error_summary = "\n".join(errors[:10]) # === Show first 10 errors ===
        raise EZPassFileValidationException(f"All rows failed validation:\n{error_summary}")
    
    logger.info(
        "Rows validated",
        total_rows=len(rows),
        valid_rows=len(validated_rows),
        invalid_rows=len(errors)
    )

    if errors:
        logger.warning(
            "Some rows failed validation",
            failed_count=len(errors),
            sample_errors=errors[:5]
        )

    return validated_rows


def _normalize_column_names(row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize column names to lowercase with underscores.
    Handles special characters, spaces, and common variations.
    """
    normalized = {}
    for key, value in row.items():
        if key is None or (isinstance(key, float) and pd.isna(key)):
            continue

        # === Convert to String and lowercase ===
        key_str = str(key).lower()

        # === Replace special characters and spaces with underscores ===
        normalized_key = re.sub(r'[^a-z0-9]+', '_', key_str).strip("_")

        # === Handle empty values ===
        if pd.isna(value) or value == "" or value == "nan":
            value = None

        normalized[normalized_key] = value

    return normalized


def _get_value(row: Dict[str, Any], *keys, default=None) -> Any:
    """Get value from row using multiple possible key names"""
    for key in keys:
        if key in row and row[key] not in (None, '', 'nan', 'NaN'):
            return row[key]
    return default


def _parse_date(value: Any) -> date:
    """
    Parse date from various formats.

    Supports:
    - ISO format: 2025-10-11
    - US format: 10/11/2025
    - EU format: 11/10/2025
    - Excel serial date: 45215
    - Datetime objects
    """
    if isinstance(value, date):
        return value
    
    if isinstance(value, datetime):
        return value.date()
    
    if isinstance(value, (int, float)):
        # === Handle Excel Serial Date ===
        try:
            return pd.to_datetime(value, unit="D", origin="1899-12-30").date()
        except:
            pass

    if isinstance(value, str):
        value = value.strip()

        # === Try common date formats ===
        formats = [
            '%Y-%m-%d',      # 2025-10-11
            '%m/%d/%Y',      # 10/11/2025
            '%d/%m/%Y',      # 11/10/2025
            '%Y/%m/%d',      # 2025/10/11
            '%m-%d-%Y',      # 10-11-2025
            '%d-%m-%Y',      # 11-10-2025
            '%m.%d.%Y',      # 10.11.2025
            '%d.%m.%Y',      # 11.10.2025
            '%Y%m%d',        # 20251011
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
    
    raise ValueError(f"Invalid date format: {value}")


def _parse_time(value: Any) -> time:
    """
    Parse time from various formats.
    
    Supports:
    - 24-hour format: 14:30:00, 14:30
    - 12-hour format: 2:30:00 PM, 2:30 PM
    - Excel time: 0.604166667
    - Datetime objects
    """
    if value is None or value == '':
        return None
    
    if isinstance(value, time):
        return value
    
    if isinstance(value, datetime):
        return value.time()
    
    if isinstance(value, float):
        # Handle Excel time (fraction of day)
        try:
            total_seconds = value * 86400  # 24 * 60 * 60
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            return time(hours, minutes, seconds)
        except:
            return None
    
    if isinstance(value, str):
        value = value.strip()
        
        # Try common time formats
        formats = [
            '%H:%M:%S',      # 14:30:00
            '%H:%M',         # 14:30
            '%I:%M:%S %p',   # 2:30:00 PM
            '%I:%M %p',      # 2:30 PM
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).time()
            except ValueError:
                continue
    
    # If parsing fails, return None instead of raising exception
    logger.warning("Could not parse time, returning None", value=value)
    return None


def _parse_amount(value: Any) -> float:
    """
    Parse amount from various formats.
    
    Handles:
    - Numbers: 5.50
    - Strings with currency: $5.50, USD 5.50
    - Strings with commas: 1,234.56
    - Negative values: -5.50, ($5.50)
    - Decimal objects
    """
    if isinstance(value, (int, float)):
        return float(value)
    
    if isinstance(value, Decimal):
        return float(value)
    
    if isinstance(value, str):
        value = value.strip()
        
        # Handle negative values in parentheses: ($5.50) -> -5.50
        if value.startswith('(') and value.endswith(')'):
            value = '-' + value[1:-1]
        
        # Remove currency symbols and common separators
        cleaned = re.sub(r'[^\d.-]', '', value)
        
        if not cleaned:
            raise ValueError(f"Invalid amount format: {value}")
        
        try:
            return float(cleaned)
        except ValueError:
            raise ValueError(f"Invalid amount format: {value}")
    
    raise ValueError(f"Invalid amount format: {value}")


def extract_amount(value: str) -> float:
    """
    Extract amount from string value.
    Legacy function for backward compatibility.
    """
    return _parse_amount(value)


def clean_plate_number(plate_no: str) -> str:
    """
    Clean and standardize plate number for matching.
    
    - Converts to uppercase
    - Removes spaces, dashes, and special characters
    - Keeps only alphanumeric characters
    """
    if not plate_no:
        return ""
    
    # Convert to uppercase and remove spaces/special chars
    cleaned = re.sub(r'[^A-Z0-9]', '', str(plate_no).upper())
    return cleaned


def format_transaction_for_ledger(transaction: dict, lease: dict, driver: dict, vehicle: dict) -> dict:
    """
    Format transaction data for ledger posting.
    
    Args:
        transaction: EZPass transaction data
        lease: Associated lease data
        driver: Associated driver data
        vehicle: Associated vehicle data
        
    Returns:
        Dictionary formatted for ledger entry
    """
    return {
        'transaction_type': 'EZPass',
        'transaction_id': transaction.get('transaction_id'),
        'transaction_date': transaction.get('transaction_date'),
        'amount': transaction.get('amount'),
        'lease_id': lease.get('id'),
        'driver_id': driver.get('id'),
        'vehicle_id': vehicle.get('id'),
        'medallion_id': lease.get('medallion_id'),
        'description': f"EZPass toll - {transaction.get('agency', 'Unknown')} - {transaction.get('plate_no')}",
        'source_type': 'ezpass',
        'source_id': transaction.get('id'),
        'entry_plaza': transaction.get('entry_plaza'),
        'exit_plaza': transaction.get('exit_plaza'),
        'agency': transaction.get('agency')
    }