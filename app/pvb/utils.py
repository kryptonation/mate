# app/pvb/utils.py

"""
Utility functions for PVB module
"""

import csv
from io import StringIO
from typing import List, Dict, Any

import pandas as pd
from fastapi import UploadFile

from app.pvb.exceptions import PVBFileValidationException
from app.utils.logger import get_logger

logger = get_logger(__name__)


# Required columns for PVB CSV files
REQUIRED_COLUMNS = [
    "PLATE",
    "STATE", 
    "SUMMONS",
    "ISSUE DATE",
    "AMOUNT DUE"
]

# Optional columns that may be present
OPTIONAL_COLUMNS = [
    "TYPE",
    "TERMINATED",
    "NON PROGRAM",
    "ISSUE TIME",
    "SYS ENTRY",
    "NEW ISSUE",
    "VC",
    "HEARING IND",
    "PENALTY WARNING",
    "JUDGMENT",
    "FINE",
    "PENALTY",
    "INTEREST",
    "REDUCTION",
    "PAYMENT",
    "NG PMT",
    "VIO COUNTY",
    "FRONT OR OPP",
    "HOUSE NUMBER",
    "STREET NAME",
    "INTERSECT STREET",
    "GEO LOC",
    "STREET CODE1",
    "STREET CODE2",
    "STREET CODE3"
]


def validate_pvb_file(file: UploadFile) -> List[Dict[str, Any]]:
    """
    Validate and parse a PVB file (CSV or Excel).
    
    Args:
        file: Uploaded file to validate
        
    Returns:
        List of dictionaries containing validated row data
        
    Raises:
        PVBFileValidationException: If file validation fails
    """
    try:
        logger.info("Validating PVB file", filename=file.filename)

        # Determine file type and parse
        if file.filename.endswith('.csv'):
            rows = _parse_csv_file(file)
        elif file.filename.endswith(('.xlsx', '.xls')):
            rows = _parse_excel_file(file)
        else:
            raise PVBFileValidationException(
                "Unsupported file format. Only CSV and Excel files are supported."
            )

        # Validate parsed data
        validated_rows = _validate_rows(rows)

        logger.info(
            "File validation successful",
            filename=file.filename,
            rows_count=len(validated_rows),
        )

        return validated_rows

    except PVBFileValidationException:
        raise
    except Exception as e:
        logger.error("Error validating file", filename=file.filename, error=str(e))
        raise PVBFileValidationException(f"File validation error: {str(e)}")


def _parse_csv_file(file: UploadFile) -> List[Dict[str, Any]]:
    """Parse CSV file"""
    try:
        content = file.file.read().decode("utf-8")

        # Handle BOM if present
        if content.startswith('\ufeff'):
            content = content[1:]

        csv_reader = csv.DictReader(StringIO(content))
        rows = list(csv_reader)

        logger.debug("CSV file parsed", rows_count=len(rows))
        return rows

    except Exception as e:
        logger.error("Error parsing CSV file", error=str(e))
        raise PVBFileValidationException(f"CSV parsing error: {str(e)}")


def _parse_excel_file(file: UploadFile) -> List[Dict[str, Any]]:
    """Parse Excel file"""
    try:
        df = pd.read_excel(file.file)
        # Drop completely empty rows
        df = df.dropna(how="all")
        rows = df.to_dict("records")

        logger.debug("Excel file parsed", rows_count=len(rows))
        return rows

    except Exception as e:
        logger.error("Error parsing Excel file", error=str(e))
        raise PVBFileValidationException(f"Excel parsing error: {str(e)}")


def _validate_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Validate row data and ensure required columns are present.
    
    Args:
        rows: List of dictionaries from parsed file
        
    Returns:
        List of validated dictionaries
        
    Raises:
        PVBFileValidationException: If validation fails
    """
    if not rows:
        raise PVBFileValidationException("File is empty or contains no data rows")

    # Strip whitespace from all column names
    normalized_rows = []
    for row in rows:
        normalized_row = {k.strip(): v for k, v in row.items() if k is not None}
        normalized_rows.append(normalized_row)

    # Get column names from first row
    first_row_keys = set(normalized_rows[0].keys())

    # Check for required columns
    missing_columns = []
    for required_col in REQUIRED_COLUMNS:
        if required_col not in first_row_keys:
            missing_columns.append(required_col)

    if missing_columns:
        raise PVBFileValidationException(
            f"Missing required columns: {', '.join(missing_columns)}"
        )

    # Validate that at least one row has data in required columns
    valid_row_count = 0
    for row in normalized_rows:
        # Check if row has values for critical fields
        if row.get("PLATE") and row.get("SUMMONS"):
            valid_row_count += 1

    if valid_row_count == 0:
        raise PVBFileValidationException(
            "No valid data rows found. Ensure PLATE and SUMMONS columns have values."
        )

    logger.debug("Row validation successful", valid_rows=valid_row_count)
    return normalized_rows


def clean_plate_number(plate: str) -> str:
    """
    Clean and normalize a plate number.
    
    Args:
        plate: Raw plate number string
        
    Returns:
        Cleaned and normalized plate number
    """
    if not plate:
        return ""
    
    # Remove whitespace and convert to uppercase
    cleaned = str(plate).strip().upper()
    
    # Remove common special characters
    cleaned = cleaned.replace("-", "").replace(".", "").replace(" ", "")
    
    return cleaned


def format_violation_response(violation: Any) -> Dict[str, Any]:
    """
    Format a PVBViolation object for API response.
    
    Args:
        violation: PVBViolation object
        
    Returns:
        Dictionary with formatted violation data
    """
    return {
        "id": violation.id,
        "plate_number": violation.plate_number,
        "state": violation.state,
        "vehicle_type": violation.vehicle_type,
        "summons_number": violation.summons_number,
        "issue_date": str(violation.issue_date) if violation.issue_date else None,
        "issue_time": violation.issue_time,
        "amount_due": violation.amount_due,
        "amount_paid": violation.amount_paid,
        "driver_id": violation.driver_id,
        "medallion_id": violation.medallion_id,
        "vehicle_id": violation.vehicle_id,
        "status": violation.status,
        "associated_failed_reason": violation.associated_failed_reason,
        "post_failed_reason": violation.post_failed_reason,
        "created_on": violation.created_on.isoformat() if violation.created_on else None,
        "updated_on": violation.updated_on.isoformat() if violation.updated_on else None,
    }


def format_log_response(log: Any) -> Dict[str, Any]:
    """
    Format a PVBLog object for API response.
    
    Args:
        log: PVBLog object
        
    Returns:
        Dictionary with formatted log data
    """
    return {
        "id": log.id,
        "log_date": log.log_date.isoformat() if log.log_date else None,
        "log_type": log.log_type,
        "records_impacted": log.records_impacted,
        "success_count": log.success_count,
        "unidentified_count": log.unidentified_count,
        "status": log.status,
        "created_on": log.created_on.isoformat() if log.created_on else None,
        "updated_on": log.updated_on.isoformat() if log.updated_on else None,
    }