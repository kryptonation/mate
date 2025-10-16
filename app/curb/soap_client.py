# app/curb/soap_client.py

"""
Async SOAP Client for CURB API

This module provides async SOAP client functions for interacting with the CURB Taxi Fleet API.
"""

import httpx
from lxml import etree

from app.core.config import settings
from app.curb.exceptions import CURBSOAPException
from app.utils.logger import get_logger

logger = get_logger(__name__)

# SOAP timeout in seconds
SOAP_TIMEOUT = 30.0


async def fetch_trips_log10(
    from_date: str,
    to_date: str,
    recon_stat: int = -1,
    cab_number: str = "",
    driver_id: str = ""
) -> str:
    """
    Fetch trips from CURB API using GET_TRIPS_LOG10 method.
    
    Args:
        from_date: Start date in MM/DD/YYYY format
        to_date: End date in MM/DD/YYYY format
        recon_stat: Reconciliation status filter (-1=all, 0=unreconciled, >0=specific)
        cab_number: Optional cab number filter
        driver_id: Optional driver ID filter
        
    Returns:
        XML string containing trip data
        
    Raises:
        CURBSOAPException: If API call fails
    """
    logger.debug(
        "Fetching trips log10",
        from_date=from_date,
        to_date=to_date,
        recon_stat=recon_stat
    )

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "https://www.taxitronic.org/VTS_SERVICE/GET_TRIPS_LOG10"
    }

    body = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body>
            <GET_TRIPS_LOG10 xmlns="https://www.taxitronic.org/VTS_SERVICE/">
                <UserId>{settings.curb_username}</UserId>
                <Password>{settings.curb_password}</Password>
                <Merchant>{settings.curb_merchant}</Merchant>
                <DRIVERID>{driver_id}</DRIVERID>
                <CABNUMBER>{cab_number}</CABNUMBER>
                <DATE_FROM>{from_date}</DATE_FROM>
                <DATE_TO>{to_date}</DATE_TO>
                <RECON_STAT>{recon_stat}</RECON_STAT>
            </GET_TRIPS_LOG10>
        </soap:Body>
    </soap:Envelope>"""

    try:
        async with httpx.AsyncClient(timeout=SOAP_TIMEOUT) as client:
            response = await client.post(
                settings.curb_url,
                headers=headers,
                content=body
            )
            response.raise_for_status()

        tree = etree.fromstring(response.content)
        result = tree.find('.//{https://www.taxitronic.org/VTS_SERVICE/}GET_TRIPS_LOG10Result')
        
        xml_data = result.text if result is not None and result.text else ""
        logger.debug("Trips log10 fetched successfully", data_length=len(xml_data))
        
        return xml_data

    except httpx.HTTPError as e:
        logger.error("HTTP error fetching trips log10", error=str(e), exc_info=True)
        raise CURBSOAPException(f"Failed to fetch trips: {str(e)}") from e
    except etree.XMLSyntaxError as e:
        logger.error("XML parsing error", error=str(e), exc_info=True)
        raise CURBSOAPException(f"Invalid XML response: {str(e)}") from e
    except Exception as e:
        logger.error("Unexpected error fetching trips log10", error=str(e), exc_info=True)
        raise CURBSOAPException(f"Unexpected error: {str(e)}") from e


async def fetch_trans_by_date_cab12(
    from_datetime: str,
    to_datetime: str,
    cab_number: str = "",
    tran_type: str = "ALL"
) -> str:
    """
    Fetch card transactions using Get_Trans_By_Date_Cab12 method.
    
    Args:
        from_datetime: Start datetime in MM/DD/YYYY format
        to_datetime: End datetime in MM/DD/YYYY format
        cab_number: Optional cab number filter
        tran_type: Transaction type (AP=Approved, DC=Declined, ALL=All)
        
    Returns:
        XML string containing transaction data
        
    Raises:
        CURBSOAPException: If API call fails
    """
    logger.debug(
        "Fetching card transactions",
        from_datetime=from_datetime,
        to_datetime=to_datetime,
        tran_type=tran_type
    )

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "https://www.taxitronic.org/VTS_SERVICE/Get_Trans_By_Date_Cab12"
    }

    body = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body>
            <Get_Trans_By_Date_Cab12 xmlns="https://www.taxitronic.org/VTS_SERVICE/">
                <UserId>{settings.curb_username}</UserId>
                <Password>{settings.curb_password}</Password>
                <Merchant>{settings.curb_merchant}</Merchant>
                <fromDateTime>{from_datetime}</fromDateTime>
                <ToDateTime>{to_datetime}</ToDateTime>
                <CabNumber>{cab_number}</CabNumber>
                <TranType>{tran_type}</TranType>
            </Get_Trans_By_Date_Cab12>
        </soap:Body>
    </soap:Envelope>"""

    try:
        async with httpx.AsyncClient(timeout=SOAP_TIMEOUT) as client:
            response = await client.post(
                settings.curb_url,
                headers=headers,
                content=body
            )
            response.raise_for_status()

        tree = etree.fromstring(response.content)
        result_node = tree.find('.//{https://www.taxitronic.org/VTS_SERVICE/}Get_Trans_By_Date_Cab12Result')
        
        xml_data = result_node.text if result_node is not None and result_node.text else ""
        logger.debug("Card transactions fetched successfully", data_length=len(xml_data))
        
        return xml_data

    except httpx.HTTPError as e:
        logger.error("HTTP error fetching card transactions", error=str(e), exc_info=True)
        raise CURBSOAPException(f"Failed to fetch card transactions: {str(e)}") from e
    except etree.XMLSyntaxError as e:
        logger.error("XML parsing error", error=str(e), exc_info=True)
        raise CURBSOAPException(f"Invalid XML response: {str(e)}") from e
    except Exception as e:
        logger.error("Unexpected error fetching card transactions", error=str(e), exc_info=True)
        raise CURBSOAPException(f"Unexpected error: {str(e)}") from e


async def reconcile_trips_on_server(
    record_ids: list[str],
    recon_stat: int
) -> bool:
    """
    Reconcile trips on CURB server using Reconciliation_TRIP_LOG method.
    
    Args:
        record_ids: List of trip record IDs to reconcile
        recon_stat: Reconciliation receipt number (must be positive)
        
    Returns:
        True if successful
        
    Raises:
        CURBSOAPException: If API call fails
    """
    logger.debug(
        "Reconciling trips on server",
        count=len(record_ids),
        recon_stat=recon_stat
    )

    if recon_stat <= 0:
        raise CURBSOAPException("recon_stat must be a positive receipt number")

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "https://www.taxitronic.org/VTS_SERVICE/Reconciliation_TRIP_LOG"
    }

    # Convert list to comma-separated string
    list_ids = ",".join(str(rid) for rid in record_ids)

    body = f"""<?xml version="1.0" encoding="utf-8"?>
    <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                   xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                   xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body>
            <Reconciliation_TRIP_LOG xmlns="https://www.taxitronic.org/VTS_SERVICE/">
                <UserId>{settings.curb_username}</UserId>
                <Password>{settings.curb_password}</Password>
                <Merchant>{settings.curb_merchant}</Merchant>
                <DATE_FROM></DATE_FROM>
                <RECON_STAT>{recon_stat}</RECON_STAT>
                <ListIDs>{list_ids}</ListIDs>
            </Reconciliation_TRIP_LOG>
        </soap:Body>
    </soap:Envelope>"""

    try:
        async with httpx.AsyncClient(timeout=SOAP_TIMEOUT) as client:
            response = await client.post(
                settings.curb_url,
                headers=headers,
                content=body
            )
            response.raise_for_status()

        logger.info("Trips reconciled on server successfully", count=len(record_ids))
        return True

    except httpx.HTTPError as e:
        logger.error("HTTP error reconciling trips", error=str(e), exc_info=True)
        raise CURBSOAPException(f"Failed to reconcile trips on server: {str(e)}") from e
    except Exception as e:
        logger.error("Unexpected error reconciling trips", error=str(e), exc_info=True)
        raise CURBSOAPException(f"Unexpected error: {str(e)}") from e
    
