## app/driver_payment/utils.py

import datetime

def prepare_driver_transaction_payload(dtr: dict):
    """Prepare the driver transaction payload"""
    def format_date(value):
        if isinstance(value, datetime.datetime):  # <- Corrected here
            return value.strftime("%Y-%m-%d")
        return value or ""

    return {
        "driver_name": dtr.get("driver_name", ""),
        "tlc_license_number": dtr.get("tlc_license_number", ""),
        "plate_number": dtr.get("plate_number", ""),
        "medallion_number": dtr.get("medallion_number", ""),
        "lease_id": dtr.get("lease_id", ""),
        "vin": dtr.get("vin", ""),
        "date_from": format_date(dtr.get("date_from")),
        "date_to": format_date(dtr.get("date_to")),
        "transaction_date": format_date(dtr.get("transaction_date", "")),
        "receipt_no": dtr.get("receipt_number", ""),
        "payment_mode": dtr.get("payment_type", "Other"),
        "total_amount": dtr.get("paid", 0),
        "lease_due": dtr.get("due", 0),
        "trip_earnings": dtr.get("trip_earnings", 0),
        "toll_reimbursements": dtr.get("toll_reimbursements", 0),
        "repairs": dtr.get("repairs", 0),
        "other": dtr.get("other", 0),
        "total": dtr.get("applied", 0),
        "processed_by": dtr.get("processed_by", ""),
        "processed_date": format_date(dtr.get("processed_date")),
        "driver_signature": dtr.get("driver_signature", ""),
        "driver_date": format_date(dtr.get("driver_date")),
        "remarks": dtr.get("remarks", ""),
    }
