## app/curb/soap_client.py

"""
SOAP Client for CURB

This module provides a SOAP client for interacting with the CURB API.
"""
# Third party imports
import requests
from lxml import etree

# Local imports
from app.core.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

def fetch_trips_log10(
    from_date, to_date, recon_stat=-1, cab_number="", driver_id=""
):
    """fetch trips from log10"""
    try:
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": "https://www.taxitronic.org/VTS_SERVICE/GET_TRIPS_LOG10"
        }

        body = f"""<?xml version="1.0" encoding="utf-8"?>
        <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XML_Schema-instance"
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

        response = requests.post(settings.curb_url, headers=headers, data=body, timeout=30)
        response.raise_for_status()

        tree = etree.fromstring(response.content)
        result = tree.find('.//{https://www.taxitronic.org/VTS_SERVICE/}GET_TRIPS_LOG10Result')
        logger.debug("Response from CURB API: %s", etree.tostring(result, pretty_print=True).decode('utf-8'))
        return result.text if result is not None else ""
    except Exception as e:
        logger.error("Error fetching trips from log10: %s", str(e), exc_info=True)
        raise e
    

def fetch_trans_by_date_cab12(
    from_datetime: str,
    to_datetime: str,
    cab_number: str = "",
    tran_type: str = "ALL"  # AP: Approved, DC: Declined, ALL
) -> str:
    """
    Synchronously fetches card transactions using Get_Trans_By_Date_Cab12.
    """
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
        response = requests.post(settings.curb_url, data=body, headers=headers, timeout=30)
        response.raise_for_status()

        tree = etree.fromstring(response.content)
        result_node = tree.find('.//{https://www.taxitronic.org/VTS_SERVICE/}Get_Trans_By_Date_Cab12Result')
        
        return result_node.text if result_node is not None and result_node.text else ""
    except requests.RequestException as e:
        logger.error("Error fetching CURB transactions", error=str(e), exc_info=True)
        raise


