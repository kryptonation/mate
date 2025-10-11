## app/bpm_flows/create_pvb/utils.py

# Local imports
from app.pvb.models import PVBViolation 
from app.medallions.services import medallion_service
from app.drivers.services import driver_service
from app.drivers.utils import format_driver_response
from app.medallions.utils import format_medallion_response


def get_attr(obj, key):
    """Safely get an attribute from a model or dict."""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def format_pvb_details(db, pvb, documents: list[dict] = None) -> dict:
    """
    Formats PVB details whether `pvb` is a dict or model.
    """
    driver_id = get_attr(pvb, "driver_id")
    medallion_id = get_attr(pvb, "medallion_id")

    driver_details = driver_service.get_drivers(db=db, id=driver_id)
    medallion_details = medallion_service.get_medallion(db=db, medallion_id=medallion_id)
    medallion_response = format_medallion_response(medallion_details, False) if medallion_details else {}


    driver_response = format_driver_response(driver_details, False) if driver_details else {}
    driver_persional_data = driver_response["driver_details"]
    tlc_data = driver_response["tlc_license_details"]
    dmv_data = driver_response["dmv_license_details"]

    other_details = {
        "plate_number": get_attr(pvb, "plate_number"),
        "medallion_number": medallion_details.medallion_number if medallion_details else None,
        "driver_id": driver_persional_data["driver_lookup_id"] if driver_persional_data else None,
        "driver_name": f'{driver_persional_data["first_name"]} {driver_persional_data["middle_name"]} {driver_persional_data["last_name"]}' if driver_persional_data else "",
        "tlc_license_number": tlc_data["tlc_license_number"] if tlc_data else None,
        "dmv_license_number": dmv_data["dmv_license_number"] if dmv_data else None,
        "medallion_owner" : medallion_response["medallion_owner"] if medallion_response else None,
    }


    pvb_details = {
        "pvb_id": get_attr(pvb, "id"),
        "plate_number": get_attr(pvb, "plate_number"),
        "issue_date": get_attr(pvb, "issue_date"),
        "issue_time": get_attr(pvb, "issue_time"),
        "registration_state": get_attr(pvb, "state"),
        "summons_number": get_attr(pvb, "summons_number"),
        "amount_due": get_attr(pvb, "amount_due"),
        "status": get_attr(pvb, "status"),
        "vehicle_id": get_attr(pvb, "vehicle_id"),
        "medallion_id": get_attr(pvb, "medallion_id"),
        "driver_id": get_attr(pvb , "driver_id")
    }

    return {"pvb_details": pvb_details ,"documents": documents , "other_details": other_details}
