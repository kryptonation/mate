## app/driver_payment/services.py

from typing import Optional, Union, List

# Third party imports
from sqlalchemy.orm import Session
from sqlalchemy import func

# Local imports
from app.drivers.models import Driver, TLCLicense, DMVLicense
from app.leases.models import Lease , LeaseDriver
from app.vehicles.models import Vehicle , VehicleRegistration
from app.medallions.models import Medallion
from app.drivers.schemas import DriverStatus
from app.ledger.models import LedgerEntry , DailyReceipt
from app.utils.logger import get_logger

logger = get_logger(__name__)

class DriverPaymentService:
    """Service for driver payments"""

    def search_driver_payments(
        self,
        db: Session,
        page: int = 1,
        per_page: int = 10,
        receipt_number: Optional[str] = None,
        medallion_number: Optional[str] = None,
        tlc_license_number: Optional[str] = None,
        plate_number: Optional[str] = None,
        mode: Optional[str] = None,
        multiple: Optional[bool] = False,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None
    ):
        """
        Get driver payments with optional filters and include TLC and Medallion numbers.
        """
        try:
            query = (
                db.query(
                    DailyReceipt,
                    TLCLicense.tlc_license_number.label("tlc_license_number"),
                    Medallion.medallion_number.label("medallion_number"),
                    VehicleRegistration.plate_number.label("plate_number"),
                    Driver.bank_account_id.label("bank_account_id"),
                    Driver.driver_id.label("driver_id"),
                    Vehicle.vin.label("vin"),
                    Lease.lease_id.label("lease_id"),
                    Driver.first_name.label("first_name"),
                    Driver.last_name.label("last_name"),
                )
                .outerjoin(Driver, Driver.id == DailyReceipt.driver_id)
                .outerjoin(TLCLicense, TLCLicense.id == Driver.tlc_license_number_id)
                .outerjoin(LeaseDriver, LeaseDriver.driver_id == Driver.driver_id)
                .outerjoin(Lease , Lease.id == LeaseDriver.lease_id)
                .outerjoin(Medallion, Medallion.id == Lease.medallion_id)
                .outerjoin(Vehicle, Vehicle.id == Lease.vehicle_id)
                .outerjoin(VehicleRegistration, VehicleRegistration.vehicle_id == Vehicle.id)
            )

            def parse_csv(value):
                return [v.strip() for v in value.split(",") if v.strip()]

            if receipt_number:
                query = query.filter(DailyReceipt.receipt_number.in_(parse_csv(receipt_number)))

            if medallion_number:
                query = query.filter(Medallion.medallion_number.in_(parse_csv(medallion_number)))

            if tlc_license_number:
                query = query.filter(TLCLicense.tlc_license_number.in_(parse_csv(tlc_license_number)))

            if plate_number:
                query = query.join(Vehicle).join(VehicleRegistration).filter(
                    VehicleRegistration.plate_number.in_(parse_csv(plate_number))
                )
            if mode:
                mode = mode.lower()
                if mode == "ach":
                    query = query.filter(Driver.bank_account_id.isnot(None))
                else:
                    query = query.filter(Driver.bank_account_id.is_(None))


            if sort_by:
                if hasattr(DailyReceipt, sort_by):
                    sort_col = getattr(DailyReceipt, sort_by)
                    query = query.order_by(sort_col.asc() if sort_order == "asc" else sort_col.desc())
                else:
                    raise ValueError(f"Invalid sort_by field: {sort_by}")
                
            total_count = query.count()
                
            if page and per_page:
                query = query.offset((page - 1) * per_page).limit(per_page)

            results = query.all()

            if not multiple and results:
                receipt, tlc_num, med_num , plate_number , bank , driver_id , vin , lease_id , first_name , last_name = results[0]
                return {
                    "receipt_number": receipt.receipt_number,
                    "date_from":receipt.period_start,
                    "date_to":receipt.period_end,
                    "driver_id": driver_id,
                    "driver_name": f"{first_name} {last_name}",
                    "lease_id": lease_id,
                    "vin": vin,
                    "ledger_id":receipt.ledger_snapshot_id,
                    "paid": receipt.cash_paid or 0.0,
                    "due": receipt.balance or 0.0,
                    # --- FIX APPLIED HERE ---
                    "applied": (receipt.cash_paid or 0.0) + (receipt.balance or 0.0),
                    "tlc_license_number": tlc_num,
                    "medallion_number": med_num,
                    "plate_number": plate_number,
                    "payment_type" : "Check" if not bank else "ACH",
                    "receipt_html_url": receipt.receipt_html_url,
                    "receipt_pdf_url": receipt.receipt_pdf_url,
                    # "receipt_excel_url": receipt.receipt_excel_url,
                    "created_on": receipt.created_on
                }

            items = [
                {
                    "receipt_number": receipt.receipt_number,
                    "date_from":receipt.period_start,
                    "date_to":receipt.period_end,
                    "driver_id": driver_id,
                    "driver_name": f"{first_name} {last_name}",
                    "lease_id": lease_id,
                    "vin": vin,
                    "ledger_id":receipt.ledger_snapshot_id,
                    "paid": receipt.cash_paid or 0.0,
                    "due": receipt.balance or 0.0,
                    # --- FIX APPLIED HERE ---
                    "applied": (receipt.cash_paid or 0.0) + (receipt.balance or 0.0),
                    "tlc_license_number": tlc_num,
                    "medallion_number": med_num,
                    "plate_number": plate_number,
                    "payment_type" : "Check" if not bank else "ACH",
                    "receipt_html_url": receipt.receipt_html_url,
                    "receipt_pdf_url": receipt.receipt_pdf_url,
                    # "receipt_excel_url": receipt.receipt_excel_url,
                    "created_on": receipt.created_on
                }
                for receipt, tlc_num, med_num , plate_number , bank , driver_id , vin , lease_id  , first_name , last_name in results
            ]

            return {
                "items": items,
                "total_items": total_count,
                "page": page,
                "per_page": per_page,
                "total_pages": (total_count + per_page - 1) // per_page
            }

        except Exception as e:
            logger.error("Error getting driver payments: %s", e)
            raise

driver_payment_service = DriverPaymentService()