## app/curb/utils.py

"""
CURB Utility Functions

This module contains utility functions for CURB data processing.
"""
# Standard library imports
from datetime import datetime

# Third party imports
import xml.etree.ElementTree as ET

# Local imports
from app.utils.logger import get_logger

logger = get_logger(__name__)

def parse_trips_xml(xml_data: str) -> list[dict]:
    """Parse trips XML data and return a list of trips."""
    try:
        root = ET.fromstring(xml_data)
        trip_records = []


        for record in root.findall(".//RECORD"):
            trip = {
                "record_id": record.get("ID"),
                "period": record.get("PERIOD"),
                "cab_number": record.get("CABNUMBER"),
                "driver_id": record.get("DRIVER"),
                "start_date": parse_date(record.get("START_DATE").split(' ')[0] if record.get("START_DATE") else None),
                "start_time": parse_time(record.get("START_DATE").split(' ')[1] if record.get("START_DATE") else None),
                "end_date": parse_date(record.get("END_DATE").split(' ')[0] if record.get("END_DATE") else None),
                "end_time": parse_time(record.get("END_DATE").split(' ')[1] if record.get("END_DATE") else None),
                "trip_amount": to_float(record.get("TRIP")),
                "tips": to_float(record.get("TIPS")),
                "extras": to_float(record.get("EXTRAS")),
                "tolls": to_float(record.get("TOLLS")),
                "tax": to_float(record.get("TAX")),
                "imp_tax": to_float(record.get("IMPTAX")),
                "total_amount": to_float(record.get("TOTAL_AMOUNT")),
                "payment_type": record.get("T"),
                "cc_number": record.get("CCNUMBER"),
                "auth_code": record.get("AUTHCODE"),
                "auth_amount": to_float(record.get("AUTHAMT")),
                "gps_start_lat": to_float(record.get("GPS_START_LA")),
                "gps_start_lon": to_float(record.get("GPS_START_LO")),
                "gps_end_lat": to_float(record.get("GPS_END_LA")),
                "gps_end_lon": to_float(record.get("GPS_END_LO")),
                "from_address": record.get("FROM_ADDRESS"),
                "to_address": record.get("TO_ADDRESS"),
                "ehail_fee": to_float(record.get("EHAILFEE")),
                "health_fee": to_float(record.get("HEALTHFEE")),
                "passengers": int(record.get("PASSENGER_NUM") or 0),
                "distance_service": to_float(record.get("DIST_SERVCE")),
                "distance_bs": to_float(record.get("DIST_BS")),
                "reservation_number": record.get("RESNUM"),
                "congestion_fee": to_float(record.get("CONGFEE")),
                "airport_fee": to_float(record.get("airportFee")),
                "cbdt_fee": to_float(record.get("cbdt")),
                "trip_number": record.get("NUM_SERVICE"),
            }
            logger.info("Start date time split ***** ", start_date=trip["start_date"], start_time=trip["start_time"])
            logger.info("End date time split ***** ", end_date=trip["end_date"], end_time=trip["end_time"])
            trip_records.append(trip)

        return trip_records
    except Exception as e:
        logger.error("Error parsing trips XML: %s", str(e), exc_info=True)
        raise e

def parse_datetime(date_str: str) -> datetime:
    """Parse a datetime string into a datetime object."""
    try:
        return datetime.strptime(date_str, "%m/%d/%Y %H:%M:%S")
    except Exception:
        return None

def to_float(value: str) -> float:
    """Convert a string to a float."""
    try:
        return float(value)
    except Exception:
        return 0.0
    
def parse_date(date_str: str) -> datetime.date:
    """Parse a date string into a date object."""
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").date()
    except Exception:
        return None
    
def parse_time(time_str: str) -> datetime.time:
    """Parse a time string into a time object."""
    try:
        if len(time_str.split(":")) == 2:
            return datetime.strptime(time_str, "%H:%M").time()
        return datetime.strptime(time_str, "%H:%M:%S").time()
    except Exception:
        return None

def parse_end_datetime(date_str: str) -> datetime:
    """Parse an end datetime string into a datetime object."""
    try:
        return datetime.strptime(date_str, "%m/%d/%Y %H:%M:%S:%f").date()
    except Exception:
        return None

def parse_card_transactions_xml(xml_data: str) -> list[dict]:
    """
    Parses the XML response from Get_Trans_By_Date_Cab12.
    The response is an XML string embedded within the main XML response.
    """
    try:
        if not xml_data:
            return []
            
        # The data is inside a <trans> wrapper
        root = ET.fromstring(f"<root>{xml_data}</root>") # Wrap to handle multiple <tran> at root
        transactions = []

        for record in root.findall(".//tran"):
            tran = {
                "record_id": record.get("ROWID"),
                "cab_number": record.findtext("CABNUMBER"),
                "driver_id": record.findtext("TRIPDRIVERID"),
                "trip_number": record.findtext("NUM_SERVICE"),
                "total_amount": to_float(record.findtext("AMOUNT")),
                "start_date": parse_date(record.findtext("TRIPDATE")),
                "start_time": parse_time(record.findtext("TRIPTIMESTART")),
                "end_date": parse_date(record.findtext("DATETIME").split(' ')[0] if record.findtext("DATETIME") else record.findtext("TRIPDATE")),
                "end_time": parse_time(record.findtext("TRIPTIMEEND")),
                "tax": to_float(record.findtext("TAX")),
                "imp_tax": to_float(record.findtext("IMPTAX")),
                "congestion_fee": to_float(record.findtext("CongFee")),
                "airport_fee": to_float(record.findtext("airportFee")),
                "cbdt_fee": to_float(record.findtext("cbdt")),
                "ehail_fee": to_float(record.findtext("EHAIL_FEE")),
                "tips": to_float(record.findtext("TRIPTIPS")),
                "trip_amount": to_float(record.findtext("TRIPFARE")),
                "extras": to_float(record.findtext("TRIPEXTRAS")),
                "tolls": to_float(record.findtext("TRIPTOLL")),
                "gps_start_lat": to_float(record.findtext("TO_LA")),
                "gps_start_lon": to_float(record.findtext("TO_LO")),
                "gps_end_lat": to_float(record.findtext("FROM_LA")),
                "gps_end_lon": to_float(record.findtext("FROM_LO")),
                "cc_number": record.findtext("CRNUMBER"),
                "payment_type": "C"
            }
            transactions.append(tran)
        return transactions
    except Exception as e:
        logger.error("Error parsing card transactions XML", error=str(e), exc_info=True)
        raise