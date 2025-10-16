# app/curb/utils.py

"""
Utility functions for CURB module

This module provides XML parsing and data transformation utilities.
"""

from datetime import datetime, date, time
from typing import List, Dict, Any, Optional

import xml.etree.ElementTree as ET

from app.curb.exceptions import CURBXMLParseException
from app.utils.logger import get_logger

logger = get_logger(__name__)


def parse_trips_xml(xml_data: str) -> List[Dict[str, Any]]:
    """
    Parse XML response from GET_TRIPS_LOG10 method.
    
    Args:
        xml_data: XML string containing trip data
        
    Returns:
        List of trip dictionaries
        
    Raises:
        CURBXMLParseException: If XML parsing fails
    """
    if not xml_data:
        logger.warning("Empty XML data provided to parse_trips_xml")
        return []

    try:
        # Wrap in root element if needed
        if not xml_data.strip().startswith("<"):
            xml_data = f"<root>{xml_data}</root>"

        root = ET.fromstring(xml_data)
        trip_records = []

        # Find all RECORD elements
        for record in root.findall(".//RECORD"):
            try:
                # Parse dates and times
                start_datetime_str = record.get("START_DATE", "")
                end_datetime_str = record.get("END_DATE", "")

                start_date, start_time = parse_datetime(start_datetime_str)
                end_date, end_time = parse_datetime(end_datetime_str)

                trip = {
                    "record_id": record.get("ID"),
                    "period": record.get("PERIOD"),
                    "cab_number": record.get("CABNUMBER"),
                    "driver_id": record.get("DRIVER"),
                    "trip_number": record.get("NUM_SERVICE"),
                    "start_date": start_date,
                    "end_date": end_date,
                    "start_time": start_time,
                    "end_time": end_time,
                    "trip_amount": to_float(record.get("TRIP")),
                    "tips": to_float(record.get("TIPS")),
                    "extras": to_float(record.get("EXTRAS")),
                    "tolls": to_float(record.get("TOLLS")),
                    "tax": to_float(record.get("TAX")),
                    "imp_tax": to_float(record.get("IMPTAX")),
                    "total_amount": to_float(record.get("TOTAL_AMOUNT")),
                    "gps_start_lat": to_float(record.get("GPS_START_LA")),
                    "gps_start_lon": to_float(record.get("GPS_START_LO")),
                    "gps_end_lat": to_float(record.get("GPS_END_LA")),
                    "gps_end_lon": to_float(record.get("GPS_END_LO")),
                    "from_address": record.get("FROM_ADDRESS"),
                    "to_address": record.get("TO_ADDRESS"),
                    "payment_type": record.get("T", "T"),  # T=$, C=Card, P=Private
                    "cc_number": record.get("CCNUMBER"),
                    "auth_code": record.get("AUTHCODE"),
                    "auth_amount": to_float(record.get("AUTHAMT")),
                    "ehail_fee": to_float(record.get("EHAILFEE")),
                    "health_fee": to_float(record.get("HEALTHFEE")),
                    "passengers": to_int(record.get("PASSENGER_NUM")),
                    "distance_service": to_float(record.get("DIST_SERVCE")),
                    "distance_bs": to_float(record.get("DIST_BS")),
                    "reservation_number": record.get("RESNUM"),
                    "congestion_fee": to_float(record.get("CONGFEE")),
                    "airport_fee": to_float(record.get("airportFee")),
                    "cbdt_fee": to_float(record.get("cbdt")),
                }
                
                trip_records.append(trip)

            except Exception as e:
                logger.error(
                    "Failed to parse trip record",
                    record_id=record.get("ID"),
                    error=str(e)
                )
                continue

        logger.info("Parsed trips XML", count=len(trip_records))
        return trip_records

    except ET.ParseError as e:
        logger.error("XML parse error in parse_trips_xml", error=str(e), exc_info=True)
        raise CURBXMLParseException(f"Failed to parse trips XML: {str(e)}")
    except Exception as e:
        logger.error("Unexpected error in parse_trips_xml", error=str(e), exc_info=True)
        raise CURBXMLParseException(f"Unexpected error parsing trips XML: {str(e)}")


def parse_card_transactions_xml(xml_data: str) -> List[Dict[str, Any]]:
    """
    Parse XML response from Get_Trans_By_Date_Cab12 method.
    
    Args:
        xml_data: XML string containing card transaction data
        
    Returns:
        List of transaction dictionaries
        
    Raises:
        CURBXMLParseException: If XML parsing fails
    """
    if not xml_data:
        logger.warning("Empty XML data provided to parse_card_transactions_xml")
        return []

    try:
        # Wrap in root element for parsing
        root = ET.fromstring(f"<root>{xml_data}</root>")
        transactions = []

        # Find all tran elements
        for record in root.findall(".//tran"):
            try:
                # Get ROWID attribute
                record_id = record.get("ROWID")

                # Parse dates and times
                trip_date_str = record.findtext("TRIPDATE", "")
                trip_start_time_str = record.findtext("TRIPTIMESTART", "")
                trip_end_time_str = record.findtext("TRIPTIMEEND", "")

                start_date = parse_date(trip_date_str)
                start_time = parse_time(trip_start_time_str)
                end_time = parse_time(trip_end_time_str)

                # End date is usually the same as start date unless trip crosses midnight
                end_date = start_date

                transaction = {
                    "record_id": record_id,
                    "period": None,  # Card transactions don't have period
                    "cab_number": record.findtext("CABNUMBER"),
                    "driver_id": record.findtext("TRIPDRIVERID"),
                    "trip_number": record.findtext("NUM_SERVICE"),
                    "start_date": start_date,
                    "end_date": end_date,
                    "start_time": start_time,
                    "end_time": end_time,
                    "trip_amount": to_float(record.findtext("TRIPFARE")),
                    "tips": to_float(record.findtext("TRIPTIPS")),
                    "extras": to_float(record.findtext("TRIPEXTRAS")),
                    "tolls": to_float(record.findtext("TRIPTOLL")),
                    "tax": to_float(record.findtext("TAX")),
                    "imp_tax": to_float(record.findtext("IMPTAX")),
                    "total_amount": to_float(record.findtext("AMOUNT")),
                    "gps_start_lat": to_float(record.findtext("FromLa")),
                    "gps_start_lon": to_float(record.findtext("FromLo")),
                    "gps_end_lat": to_float(record.findtext("ToLa")),
                    "gps_end_lon": to_float(record.findtext("ToLo")),
                    "from_address": None,  # Not provided in card transactions
                    "to_address": None,
                    "payment_type": "C",  # Card transaction
                    "cc_number": record.findtext("CRNUMBER"),
                    "auth_code": record.findtext("BANK_APPROVAL"),
                    "auth_amount": to_float(record.findtext("AMOUNT")),
                    "ehail_fee": to_float(record.findtext("EHAIL_FEE")),
                    "health_fee": 0.0,  # Not in card transactions
                    "passengers": 1,  # Not provided
                    "distance_service": to_float(record.findtext("TRIPDIST")),
                    "distance_bs": 0.0,
                    "reservation_number": None,
                    "congestion_fee": to_float(record.findtext("CongFee")),
                    "airport_fee": to_float(record.findtext("airportFee")),
                    "cbdt_fee": to_float(record.findtext("cbdt")),
                }

                transactions.append(transaction)

            except Exception as e:
                logger.error(
                    "Failed to parse transaction record",
                    record_id=record.get("ROWID"),
                    error=str(e)
                )
                continue

        logger.info("Parsed card transactions XML", count=len(transactions))
        return transactions

    except ET.ParseError as e:
        logger.error("XML parse error in parse_card_transactions_xml", error=str(e), exc_info=True)
        raise CURBXMLParseException(f"Failed to parse card transactions XML: {str(e)}")
    except Exception as e:
        logger.error("Unexpected error in parse_card_transactions_xml", error=str(e), exc_info=True)
        raise CURBXMLParseException(f"Unexpected error parsing card transactions XML: {str(e)}")


def parse_datetime(datetime_str: str) -> tuple[Optional[date], Optional[time]]:
    """
    Parse a datetime string into date and time objects.
    
    Args:
        datetime_str: Datetime string in format "MM/DD/YYYY HH:MM:SS"
        
    Returns:
        Tuple of (date, time) or (None, None) if parsing fails
    """
    if not datetime_str:
        return None, None

    try:
        dt = datetime.strptime(datetime_str, "%m/%d/%Y %H:%M:%S")
        return dt.date(), dt.time()
    except ValueError:
        try:
            # Try without seconds
            dt = datetime.strptime(datetime_str, "%m/%d/%Y %H:%M")
            return dt.date(), dt.time()
        except ValueError:
            logger.warning("Failed to parse datetime", datetime_str=datetime_str)
            return None, None


def parse_date(date_str: str) -> Optional[date]:
    """
    Parse a date string into a date object.
    
    Args:
        date_str: Date string in format "MM/DD/YYYY"
        
    Returns:
        date object or None if parsing fails
    """
    if not date_str:
        return None

    try:
        return datetime.strptime(date_str, "%m/%d/%Y").date()
    except ValueError:
        logger.warning("Failed to parse date", date_str=date_str)
        return None


def parse_time(time_str: str) -> Optional[time]:
    """
    Parse a time string into a time object.
    
    Args:
        time_str: Time string in format "HH:MM" or "HH:MM:SS"
        
    Returns:
        time object or None if parsing fails
    """
    if not time_str:
        return None

    try:
        # Try with seconds first
        if len(time_str.split(":")) == 3:
            return datetime.strptime(time_str, "%H:%M:%S").time()
        else:
            return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        logger.warning("Failed to parse time", time_str=time_str)
        return None


def to_float(value: Optional[str]) -> float:
    """
    Convert a string to float, returning 0.0 on failure.
    
    Args:
        value: String value to convert
        
    Returns:
        Float value or 0.0
    """
    if not value:
        return 0.0

    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def to_int(value: Optional[str]) -> int:
    """
    Convert a string to int, returning 0 on failure.
    
    Args:
        value: String value to convert
        
    Returns:
        Int value or 0
    """
    if not value:
        return 0

    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def clean_plate_number(plate: str) -> str:
    """
    Clean and normalize plate number.
    
    Args:
        plate: Raw plate number string
        
    Returns:
        Cleaned plate number
    """
    if not plate:
        return ""

    # Remove whitespace and convert to uppercase
    cleaned = plate.strip().upper()

    # Remove common separators
    cleaned = cleaned.replace("-", "").replace("_", "").replace(" ", "")

    return cleaned


def format_date_for_soap(dt: date) -> str:
    """
    Format a date object for SOAP API calls.
    
    Args:
        dt: Date object
        
    Returns:
        Formatted date string in MM/DD/YYYY format
    """
    return dt.strftime("%m/%d/%Y")


def format_datetime_for_soap(dt: datetime) -> str:
    """
    Format a datetime object for SOAP API calls.
    
    Args:
        dt: Datetime object
        
    Returns:
        Formatted datetime string in MM/DD/YYYY HH:MM:SS format
    """
    return dt.strftime("%m/%d/%Y %H:%M:%S")