## app/bpm_flows/create_new_corporation/utils.py

from app.utils.logger import get_logger

logger = get_logger(__name__)

def prepare_rider_payload(corporation , authorized_signer=None):
    """
    Prepare the payload for the rider.
    """
    primary_address = corporation.primary_address if corporation and corporation.primary_address else None
    payload = {
        "lesse_dba_name": "BIG APPLE TAXI MANAGEMENT LLC",
        "name": corporation.name or "",
        "leasor_dba_president": authorized_signer.name if authorized_signer else "",
        "leasor_dba_description": authorized_signer.owner_type if authorized_signer else "",
        "leasor_mailing_address": primary_address.address_line_1 or "",
        "leasor_city": primary_address.city if primary_address else "",
        "leasor_state": primary_address.state if primary_address else "",
        "leasor_zipcode" : primary_address.zip if primary_address else "",
        "employer_identification_number" : corporation.ein or "",
        "leasor_dba_name": "",
    }
    

    logger.info("Prepared rider payload", payload=payload)

    return payload
