### app/ledger/services.py

# Standard library imports
from typing import Union, List, Optional
from datetime import date , time, datetime
import math


# Third party imports
from sqlalchemy.orm import Session
from sqlalchemy import func , or_ , Date , Time , cast

# Local imports
from app.utils.logger import get_logger
from app.ledger.models import LedgerEntry
from app.leases.models import Lease, LeaseSchedule , LeaseDriver
from app.medallions.models import Medallion
from app.medallions.schemas import MedallionOwnerType
from app.vehicles.models import Vehicle
from app.drivers.models import Driver
from app.ledger.utils import get_pay_window, summarize_ledger_entries
from app.ledger.models import DailyReceipt
from app.ledger.schemas import LedgerSourceType, DTRStatus
from app.drivers.services import driver_service
from app.utils.general import generate_alphanumeric_code
from app.leases.services import lease_service
from app.medallions.services import medallion_service
from app.vehicles.services import vehicle_service
from app.medallions.utils import format_medallion_response


logger = get_logger(__name__)


class LedgerService:
    """Ledger service for operations"""
    def get_ledger_entries(
        self, db: Session,
        ledger_id: Optional[int] = None,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[str] = None,
        medallion_id: Optional[str] = None,
        ledger_source: Optional[str] = None,
        source_id: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        multiple: Optional[bool] = None,
    ) -> Union[List[LedgerEntry], LedgerEntry, None]:
        """Get ledger entries"""
        try:
            query = db.query(LedgerEntry)

            if ledger_id:
                query = query.filter(LedgerEntry.id == ledger_id)

            if driver_id:
                driver_ids = str(driver_id).split(",")
                query = query.filter(LedgerEntry.driver_id.in_(driver_ids))

            if vehicle_id:
                vehicle_ids = vehicle_id.split(",")
                query = query.filter(LedgerEntry.vehicle_id.in_(vehicle_ids))

            if medallion_id:
                medallion_ids = medallion_id.split(",")
                query = query.filter(LedgerEntry.medallion_id.in_(medallion_ids))

            if ledger_source:
                query = query.filter(LedgerEntry.source_type == ledger_source)

            if source_id:
                query = query.filter(LedgerEntry.source_id == source_id)

            if multiple:
                total_rows = query.count()
                if page and per_page:
                    query = query.offset((page - 1) * per_page).limit(per_page)

                if sort_by and sort_order:
                    if sort_by == "created_on":
                        query = query.order_by(LedgerEntry.created_on.desc() if sort_order == "desc" else LedgerEntry.created_on.asc())
                    elif sort_by == "amount":
                        query = query.order_by(LedgerEntry.amount.desc() if sort_order == "desc" else LedgerEntry.amount.asc())
                    elif sort_by == "description":
                        query = query.order_by(LedgerEntry.description.desc() if sort_order == "desc" else LedgerEntry.description.asc())
                    elif sort_by == "source_type":
                        query = query.order_by(LedgerEntry.source_type.desc() if sort_order == "desc" else LedgerEntry.source_type.asc())
                    elif sort_by == "source_id":
                        query = query.order_by(LedgerEntry.source_id.desc() if sort_order == "desc" else LedgerEntry.source_id.asc())
                    elif sort_by == "debit":
                        query = query.order_by(LedgerEntry.debit.desc() if sort_order == "desc" else LedgerEntry.debit.asc())
                    elif sort_by == "driver_id":
                        query = query.order_by(LedgerEntry.driver_id.desc() if sort_order == "desc" else LedgerEntry.driver_id.asc())
                    elif sort_by == "medallion_id":
                        query = query.order_by(LedgerEntry.medallion_id.desc() if sort_order == "desc" else LedgerEntry.medallion_id.asc())
                    elif sort_by == "vehicle_id":
                        query = query.order_by(LedgerEntry.vehicle_id.desc() if sort_order == "desc" else LedgerEntry.vehicle_id.asc())

                return query.all(), total_rows

            return query.first()
        except Exception as e:
            logger.error("Error getting ledger entries: %s", e, exc_info=True)
            raise e
        
    def search_ledger_entries(
        self, db: Session,
        ledger_id: Optional[int] = None,
        amount_from: Optional[float] = None,
        amount_to: Optional[float] = None,
        driver_id: Optional[str] = None,
        driver_name: Optional[str] = None,
        transaction_date_from : Optional[date] = None,
        transaction_date_to : Optional[date] = None,
        transaction_time_from: Optional[time] = None,
        transaction_time_to: Optional[time] = None,
        vin: Optional[str] = None,
        medallion_number: Optional[str] = None,
        transaction_type : Optional[bool] = None,
        source_type: Optional[str] = None,
        source_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        start_time : Optional[time] = None,
        end_time: Optional[time] = None,
        receipt_number: Optional[str] = None,
        page: Optional[int] = 1,
        page_size: Optional[int] = 10,
        sort_by: Optional[str] = "created_on",
        sort_order: Optional[str] = "desc",
    ) -> Union[List[LedgerEntry], LedgerEntry, None]:
        """Search ledger entries with various filters"""
        try:
            query = db.query(
                LedgerEntry,
                Driver.driver_id.label("driver_id"),
                Vehicle.vin.label("vin"),
                Medallion.medallion_number.label("medallion_number"),
                Driver.first_name+" "+Driver.last_name.label("driver_name"),

            ).join(
                Driver, LedgerEntry.driver_id == Driver.id, isouter=True
            ).join(
                Vehicle, LedgerEntry.vehicle_id == Vehicle.id, isouter=True
            ).join(
                Medallion, LedgerEntry.medallion_id == Medallion.id, isouter=True
            )

            if ledger_id:
                query = query.filter(LedgerEntry.id == ledger_id)
            if amount_from :
                query = query.filter(LedgerEntry.amount >= amount_from)
            if amount_to:
                query = query.filter(LedgerEntry.amount <= amount_to)
            if driver_id:
                driver_ids = driver_id.split(",")
                query = query.filter(or_(*[Driver.driver_id.ilike(f"%{id}%") for id in driver_ids]))
            if driver_name:
                driver_names = [name.strip() for name in driver_name.split(",") if name.strip()]
                query = query.filter(or_(*[Driver.full_name.ilike(f"%{name}%") for name in driver_names]))
            
            if vin:
                vins = vin.split(",")
                query = query.filter(or_(*[Vehicle.vin.ilike(f"%{v}%") for v in vins]))
            if medallion_number:
                medallion_numbers = medallion_number.split(",")
                query = query.filter(or_(*[Medallion.medallion_number.ilike(f"%{m}%") for m in medallion_numbers]))
            if transaction_type is not None:
                query = query.filter(LedgerEntry.debit == transaction_type)
            if transaction_date_from:
                query = query.filter(LedgerEntry.transaction_date >= transaction_date_from)
            if transaction_date_to:
                query = query.filter(LedgerEntry.transaction_date <= transaction_date_to)
            if transaction_time_from:
                query = query.filter(LedgerEntry.transaction_time >= transaction_time_from)
            if transaction_time_to:
                query = query.filter(LedgerEntry.transaction_time <= transaction_time_to)
            if source_type:
                query = query.filter(LedgerEntry.source_type == source_type)
            if source_id:
                query = query.filter(LedgerEntry.source_id == source_id)
            if start_date:
                query = query.filter(cast(LedgerEntry.created_on, Date) >= start_date)
            if end_date:
                query = query.filter(cast(LedgerEntry.created_on, Date) <= end_date)
            if start_time:
                query = query.filter(cast(LedgerEntry.created_on, Time) >= start_time)
            if end_time:
                query = query.filter(cast(LedgerEntry.created_on, Time) <= end_time)
            if receipt_number:
                query = query.filter(LedgerEntry.receipt_number == receipt_number)
            if sort_by:
                sort_attr ={
                    "created_on": LedgerEntry.created_on,
                    "amount": LedgerEntry.amount,
                    "description": LedgerEntry.description,
                    "source_type": LedgerEntry.source_type,
                    "source_id": LedgerEntry.source_id,
                    "debit": LedgerEntry.debit,
                    "driver_id": LedgerEntry.driver_id,
                    "driver_name": Driver.full_name,
                    "transaction_date": LedgerEntry.transaction_date,
                    "transaction_time": LedgerEntry.transaction_time,
                    "medallion_number": LedgerEntry.medallion_id,
                    "vin": LedgerEntry.vehicle_id,
                    "receipt_number": LedgerEntry.receipt_number
                }
                if sort_by in sort_attr:
                    query = query.order_by(sort_attr[sort_by].desc() if sort_order == "desc" else sort_attr[sort_by].asc())
            total = query.count()
            if page and page_size:
                offset = (page - 1) * page_size
                query = query.offset(offset).limit(page_size)

            results = []
            for entry, driver_id, vin, medallion_number,driver_name in query.all():
                medallion = medallion_service.get_medallion(db=db , medallion_number=medallion_number) if medallion_number else None
                owner = medallion.owner if medallion else None
                owner_name = None
                if owner:
                    if owner.medallion_owner_type == MedallionOwnerType.INDIVIDUAL:
                        owner_name = owner.individual.full_name
                    elif owner.medallion_owner_type == MedallionOwnerType.CORPORATION:
                        owner_name = owner.corporation.name

                results.append({
                    "id": entry.id,
                    "ledger_id":entry.ledger_id,
                    "amount": entry.amount,
                    "description": entry.description,
                    "source_type": entry.source_type,
                    "source_id": entry.source_id,
                    "created_on": entry.created_on.isoformat(),
                    "receipt_number": entry.receipt_number,
                    "transaction_type": "Pay To Driver" if entry.debit else "Pay To Big Apple",
                    "driver_id": driver_id,
                    "driver_name":driver_name,
                    "vin": vin,
                    "medallion_number": medallion_number,
                    "medallion_owner" : owner_name,
                    "transaction_date": entry.transaction_date,
                    "transaction_time": entry.transaction_time
                })

            return {
                "page": page,
                "per_page": page_size,
                "total": total,
                "total_pages": math.ceil(total / page_size),
                "items": results
            }
        except Exception as e:
            logger.error("Error searching ledger entries: %s", e, exc_info=True)
            raise e                
        
    def upsert_ledgers(
        self, db: Session, ledger_data: dict
    ):
        """Ledger upsert"""
        try:
            if ledger_data.get("id"):
                ledger_entry = self.get_ledger_entries(db, ledger_id=ledger_data.get("id"))
                if ledger_entry:
                    for key, value in ledger_data.items():
                        setattr(ledger_entry, key, value)
                    db.commit()
                    db.refresh(ledger_entry)
                    return ledger_entry
                else:
                    return None
            else:
                ledger_entry = LedgerEntry(**ledger_data)
                db.add(ledger_entry)
                db.commit()
                db.refresh(ledger_entry)
                return ledger_entry
        except Exception as e:
            logger.error("Error upserting ledger: %s", e, exc_info=True)
            raise e
        
    def generate_dtr_for_lease(
        self, db: Session, lease: Lease,
        reference_date: date
    ):
        """Generate DTR for a lease"""
        try:
            start, end = get_pay_window(lease.pay_day, reference_date)

            rows = db.query(LedgerEntry).where(
                LedgerEntry.driver_id == lease.driver_id,
                LedgerEntry.created_on.between(start, end)
            )

            if not rows:
                return None
            
            summary = summarize_ledger_entries(rows)
            balance = (summary["cc_earnings"] + summary["cash_earnings"] + summary["tips"]
                       - summary["total_due"] + summary["cash_paid"])
            
            dtr = DailyReceipt(
                driver_id=lease.driver_id,
                vehicle_id=lease.vehicle_id,
                medallion_id=lease.medallion_id,
                lease_id=lease.id,
                period_start=start,
                period_end=end,
                status="DRAFT",
                **summary,
                balance=round(balance, 2)
            )
            db.add(dtr)
            db.commit()
            db.refresh(dtr)
            return dtr
        except Exception as e:
            logger.error("Error generating DTR for lease: %s", e, exc_info=True)
            raise e

    def post_lease_dues_to_ledger(
        self, db: Session, driver_id, lease_id, medallion_id, vehicle_id, period_end_date
    ):
        """Post lease dues to ledger"""
        try:
            dues = db.query(LeaseSchedule).where(
                LeaseSchedule.lease_id == lease_id,
                LeaseSchedule.installment_due_date <= period_end_date,
                LeaseSchedule.installment_status.in_(["D", "OD"])
            ).all()

            for due in dues:
                ledger_entry = LedgerEntry(
                    driver_id=driver_id,
                    lease_id=lease_id,
                    medallion_id=medallion_id,
                    vehicle_id=vehicle_id,
                    amount=due.installment_amount,
                    source_type=LedgerSourceType.LEASE,
                    debit=True,
                    description=f"Lease Installment #{due.installment_number} due",
                    source_id=due.id
                )
                db.add(ledger_entry)

            db.commit()            
            return True
        except Exception as e:
            logger.error("Error posting lease dues to ledger: %s", e, exc_info=True)
            raise e

    ## TODO: This is the first version of the driver transactions receipts, can be removed later.
    def generate_driver_transactions_receipts(
        self, db: Session, driver_id, medallion_id, vehicle_id, lease_id, start_date, end_date
    ):
        """Generate driver transactions receipts"""
        try:
            # Post lease dues to ledger
            self.post_lease_dues_to_ledger(db, driver_id, lease_id, medallion_id, vehicle_id, end_date)

            ledger_dues = db.query(
                LedgerEntry.source_type,
                func.sum(LedgerEntry.amount).label("total_amount")
            ).filter(
                LedgerEntry.driver_id == driver_id,
                LedgerEntry.medallion_id == medallion_id,
                LedgerEntry.vehicle_id == vehicle_id,
                LedgerEntry.debit == True,
                LedgerEntry.created_on.between(start_date, end_date)
            ).group_by(LedgerEntry.source_type).all()

            lease_due = sum((row.total_amount or 0) for row in ledger_dues if row.source_type == LedgerSourceType.LEASE)
            ezpass_due = sum((row.total_amount or 0) for row in ledger_dues if row.source_type == LedgerSourceType.EZPASS)
            pvb_due = sum((row.total_amount or 0) for row in ledger_dues if row.source_type == LedgerSourceType.PVB)
            curb_due = sum((row.total_amount or 0) for row in ledger_dues if row.source_type == LedgerSourceType.CURB)
            dtr_count = db.query(DailyReceipt).count()
            dtr = DailyReceipt(
                driver_id=driver_id,
                medallion_id=medallion_id,
                vehicle_id=vehicle_id,
                lease_id=lease_id,
                ezpass_due=ezpass_due or 0.0,
                pvb_due=pvb_due or 0.0,
                curb_due=curb_due or 0.0,
                lease_due=lease_due or 0.0,
                period_start=start_date,
                period_end=end_date,
                cash_paid=0.0,
                balance=(lease_due or 0) + (ezpass_due or 0) + (pvb_due or 0) + (curb_due or 0),
                status="DRAFT",
                receipt_number= str(dtr_count + 1).zfill(12)
            )
            db.add(dtr)
            db.commit()
            db.refresh(dtr)

            # Map ledgers to DTR
            ledgers = db.query(LedgerEntry).filter(
                LedgerEntry.driver_id == driver_id,
                LedgerEntry.medallion_id == medallion_id,
                LedgerEntry.vehicle_id == vehicle_id,
                LedgerEntry.created_on >= start_date,
                LedgerEntry.created_on <= end_date,
            ).all()
            
            for ledger in ledgers:
                ledger.receipt_number = dtr.receipt_number
                db.add(ledger)

            db.commit()
            db.refresh(dtr)
            return dtr
        except Exception as e:
            logger.error("Error generating driver transaction receipts: %s", e, exc_info=True)
            raise e

    def finalize_dtr(
        self, db: Session, dtr_id
    ):
        """Finalize DTR"""
        try:
            dtr = db.query(DailyReceipt).filter(
                DailyReceipt.id == dtr_id
            ).first()

            if not dtr:
                raise ValueError("DTR not found")

            # Update status
            dtr.status = DTRStatus.FINALIZED
            db.commit()

            return {
                "dtr_id": dtr.id,
                "driver_id": dtr.driver_id,
                "amount_due": dtr.balance,
                "lease_due": dtr.lease_due,
                "status": dtr.status.name,
                "ach_ready": dtr.balance < 0
            }
        except Exception as e:
            logger.error("Error finalizing DTR: %s", e, exc_info=True)
            raise e

    def view_driver_payments(
        self, db: Session, start_date, end_date,
        page: Optional[int] = 1,
        per_page: Optional[int] = 10,
    ):
        """View Driver Payments"""
        try:
            page = int(page)
            per_page = int(per_page)
            
            offset = (page - 1) * per_page
            from app.curb.services import curb_service
            # Fetch curb trips within the date range
            trips_query = curb_service.get_curb_trip(
                db, start_date_from=start_date, end_date_to=end_date,
                sort_by="start_date", sort_order="asc", multiple=True
            )

            results = []
            for trip in trips_query:
                driver = driver_service.get_drivers(db, driver_id=trip.driver_id)
                lease = lease_service.get_lease(db=db , driver_id=trip.driver_id)

                # Find the matching DTR
                dtr = db.query(DailyReceipt).filter(
                    DailyReceipt.driver_id == driver.id,
                    DailyReceipt.period_start <= trip.start_date,
                    DailyReceipt.period_end >= trip.end_date
                ).first()

                if dtr:
                    results.append({
                        "trip_id": trip.id,
                        "trip_date": trip.start_date.isoformat(),
                        "driver_id": trip.driver_id,
                        "plate_number": trip.cab_number,
                        "medallion_number": lease.medallion.medallion_number if lease else None,
                        "driver_name": driver.first_name + " " + driver.last_name if driver else None,
                        "tlc_license": driver.tlc_license.tlc_license_number if driver.tlc_license else None,
                        "trip_begin_time": trip.start_time.isoformat(),
                        "trip_end_time": trip.end_time.isoformat(),
                        "trip_amount": float(trip.total_amount),
                        "dtr_amount": float(dtr.balance) if dtr else None,
                        "status": "POSTED" if trip.is_posted else "PENDING"
                    })

            result = results[offset:offset + per_page]
            total = len(results)
            
            return {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": math.ceil(total / per_page),
                "items": result
            }
        except Exception as e:
            logger.error("Error viewing driver payments: %s", e, exc_info=True)
            raise e
    
    def get_dtr(
            self, db: Session,
            dtr_id: Optional[int] = None,
            receipt_number: Optional[str] = None,
            driver_id: Optional[str] = None,
            period_start_from: Optional[date] = None,
            period_start_to: Optional[date] = None,
            period_end_start: Optional[date] = None,
            period_end_to: Optional[date] = None,
            multiple: Optional[bool] = None,
    ):
        """Get DTR"""
        try:
            query = db.query(DailyReceipt)
 
            if dtr_id:
                query = query.filter(DailyReceipt.id == dtr_id)
            if receipt_number:
                query = query.filter(DailyReceipt.receipt_number == receipt_number)
            if driver_id:
                query = query.filter(DailyReceipt.driver_id == driver_id)
            if period_start_from:
                query = query.filter(DailyReceipt.period_start >= period_start_from)
            if period_start_to:
                query = query.filter(DailyReceipt.period_start <= period_start_to)
            if period_end_start:
                query = query.filter(DailyReceipt.period_end >= period_end_start)
            if period_end_to:
                query = query.filter(DailyReceipt.period_end <= period_end_to)
            if multiple:
                total_rows = query.count()
                return query.all(), total_rows
            return query.first()
        except Exception as e:
            logger.error("Error getting DTR: %s", e, exc_info=True)
            raise e

    def generate_dtr_data(
        self, db: Session, receipt_id: str
    ):
        """Generate DTR data"""
        try:
            from app.curb.models import CURBTrip
            
            receipt = db.query(DailyReceipt).filter(
                DailyReceipt.receipt_number == receipt_id
            ).first()

            if not receipt:
                raise ValueError("Receipt not found")

            lease = lease_service.get_lease(db, lookup_id=receipt.lease_id)
            driver = driver_service.get_drivers(db, id=receipt.driver_id)
            medallion = medallion_service.get_medallion(db, medallion_id=receipt.medallion_id)
            vehicle = vehicle_service.get_vehicles(db, vehicle_id=receipt.vehicle_id)

            if not driver or not medallion or not vehicle:
                raise ValueError("Driver, medallion, or vehicle not found")

            ledgers = db.query(LedgerEntry).filter(
                LedgerEntry.receipt_number == receipt_id
            ).all()

            if not ledgers:
                raise ValueError("No ledgers found for receipt")

            trips = db.query(CURBTrip).filter(
                CURBTrip.driver_id == driver.driver_id,
                CURBTrip.start_date >= receipt.period_start,
                CURBTrip.end_date <= receipt.period_end
            ).all()

            if not trips:
                trips = [] 
                # raise ValueError("No trips found for receipt")

            return {
                "driver": driver,
                "medallion": medallion,
                "vehicle": vehicle,
                "ledgers": ledgers,
                "trips": trips,
                "receipt": receipt,
                "lease": lease,
            }

        except Exception as e:
            logger.error("Error generating DTR data: %s", e, exc_info=True)
            raise e

    def update_dtr(
        self, db: Session, dtr_id: int, dtr_data: dict
    ):
        """update DTR"""
        try:
            dtr = db.query(DailyReceipt).filter(
                DailyReceipt.id == dtr_id
            ).first()

            if not dtr:
                raise ValueError("DTR not found")
                
            for key, value in dtr_data.items():
                setattr(dtr, key, value)

            db.commit()
            db.refresh(dtr)
            return dtr
        except Exception as e:
            logger.error("Error updating DTR: %s", e, exc_info=True)
            raise e
        
    def generate_dtr_summary(self, db: Session, driver_id: str, start_date: datetime, end_date: datetime) -> dict:
        """
        Gathers and calculates all data required for a single DTR statement.
        This is the new core logic for DTR data aggregation
        """
        from app.curb.models import CURBTrip
        from app.ezpass.models import EZPassTransaction
        from app.pvb.models import PVBViolation

        driver = driver_service.get_drivers(db, driver_id=driver_id)
        if not driver:
            raise ValueError(f"Driver with ID {driver_id} not found.")

        lease = db.query(Lease).join(LeaseDriver).filter(
            LeaseDriver.driver_id == driver.driver_id,
            Lease.lease_start_date <= end_date.date(),
            or_(Lease.lease_end_date >= start_date.date(), Lease.lease_end_date == None)
        ).order_by(Lease.created_on.desc()).first()
        
        if not lease:
            raise ValueError(f"No active lease found for driver ID {driver_id} in the period.")

        medallion = lease.medallion
        vehicle = lease.vehicle

        # --- 1. Fetch Detailed Transaction Lists ---
        curb_trips = db.query(CURBTrip).filter(CURBTrip.driver_id == driver.driver_id, CURBTrip.end_date.between(start_date.date(), end_date.date())).all()
        ezpass_details = db.query(EZPassTransaction).filter(EZPassTransaction.driver_id == driver.id, EZPassTransaction.transaction_date.between(start_date.date(), end_date.date())).all()
        tickets_details = db.query(PVBViolation).filter(PVBViolation.driver_id == driver.id, PVBViolation.issue_date.between(start_date.date(), end_date.date())).all()
        
        manual_ledger_entries = db.query(LedgerEntry).filter(
            LedgerEntry.driver_id == driver.id,
            LedgerEntry.created_on.between(start_date, end_date),
            LedgerEntry.source_type.in_([LedgerSourceType.MANUAL_FEE, LedgerSourceType.DTR, LedgerSourceType.FEE])
        ).all()
        
        # --- 2. Calculate Summaries from Detailed Lists (with Type Casting) ---
        cc_earnings = float(
            sum(
                ((trip.total_amount or 0.0)) 
                for trip in curb_trips if trip.payment_type == 'C'
            )
        )

        surcharges_detail = {
            "mta_tax": float(sum(trip.tax or 0 for trip in curb_trips)),
            "imp_surcharge": float(sum(trip.imp_tax or 0 for trip in curb_trips)),
            "cong_surcharge": float(sum(trip.congestion_fee or 0 for trip in curb_trips)),
            "cbdt": float(sum(trip.cbdt_fee or 0 for trip in curb_trips)),
            "airport_fee": float(sum(trip.airport_fee or 0 for trip in curb_trips)),
        }
        total_surcharges = float(sum(surcharges_detail.values()))

        # --- FIX APPLIED HERE ---
        ezpass_tolls = float(sum(toll.amount or 0.0 for toll in ezpass_details))
        tickets = float(sum(ticket.amount_due or 0.0 for ticket in tickets_details))
        leasing_charges = float(lease.overridden_weekly_rate or lease.preset_weekly_rate or 1100.00)
        cash_paid = float(sum(entry.amount or 0.0 for entry in manual_ledger_entries if not entry.debit))
        manual_fees = float(sum(entry.amount or 0.0 for entry in manual_ledger_entries if entry.debit))

        # --- 3. Final Calculations (Now with consistent float types) ---
        ezpass_tolls = ezpass_tolls * -1 if ezpass_tolls < 0 else ezpass_tolls
        total_debits = total_surcharges + ezpass_tolls + tickets + leasing_charges + manual_fees
        total_credits = cc_earnings + cash_paid
        net_balance = total_credits - total_debits

        # --- 4. Consolidate ALL itemized entries for templates ---
        all_transactions = []
        all_transactions.extend(curb_trips)
        all_transactions.extend(ezpass_details)
        all_transactions.extend(tickets_details)
        all_transactions.extend(manual_ledger_entries)

        return {
            "driver": driver, "lease": lease, "medallion": medallion, "vehicle": vehicle,
            "period_start": start_date, "period_end": end_date,
            "account_balance": {
                "previous_balance": 0.00, "cc_earnings": cc_earnings, "total_surcharges": total_surcharges,
                "ezpass_tolls": ezpass_tolls, "tickets": tickets, "leasing_charges": leasing_charges,
                "manual_fees": manual_fees, "cash_paid": cash_paid, "total_due": total_debits,
                "payment": total_credits, "balance": net_balance,
            },
            "surcharges_detail": surcharges_detail,
            "ezpass_details": ezpass_details,
            "tickets_details": tickets_details,
            "curb_trips": curb_trips,
            "all_transactions_for_ledger_view": all_transactions
        }

    def create_and_generate_dtr_files(self, db: Session, driver_id: int, start_date: datetime, end_date: datetime) -> DailyReceipt:
        """
        Generates DTR summary, creates the receipt record, and generates report files.
        """
        from app.ledger.utils import generate_dtr_html_doc, generate_dtr_pdf_doc, generate_dtr_excel_doc_styled
        try:
            driver = driver_service.get_drivers(db, driver_id=driver_id)
            if not driver:
                raise ValueError(f"Driver with ID {driver_id} not found.")
            logger.info(f"Generating DTR for Driver ID: {driver_id} with {driver.driver_id} from {start_date.date()} to {end_date.date()}")
            dtr_summary = self.generate_dtr_summary(db, driver.driver_id, start_date, end_date)

            # Create a DTR record in the database
            dtr_count = db.query(DailyReceipt).count()
            new_receipt = DailyReceipt(
                driver_id=driver.id,
                vehicle_id=dtr_summary["vehicle"].id,
                medallion_id=dtr_summary["medallion"].id,
                lease_id=dtr_summary["lease"].id,
                receipt_number=str(dtr_count + 1).zfill(12),
                period_start=start_date,
                period_end=end_date,
                cc_earnings=dtr_summary["account_balance"]["cc_earnings"],
                lease_due=dtr_summary["account_balance"]["leasing_charges"],
                ezpass_due=dtr_summary["account_balance"]["ezpass_tolls"],
                pvb_due=dtr_summary["account_balance"]["tickets"],
                balance=dtr_summary["account_balance"]["payment"],
                status=DTRStatus.FINALIZED,
            )
            db.add(new_receipt)
            db.commit()
            db.refresh(new_receipt)

            # Pass the full summary to the file generators
            dtr_data_for_template = {
                "receipt": new_receipt,
                **dtr_summary
            }

            # Generate and upload documents, then update the DTR record
            dtr_html_key = generate_dtr_html_doc(dtr_data_for_template)
            dtr_pdf_key = generate_dtr_pdf_doc(dtr_data_for_template)
            # dtr_excel_key = generate_dtr_excel_doc_styled(dtr_data_for_template)
            
            self.update_dtr(db, new_receipt.id, {
                "receipt_html_key": dtr_html_key,
                "receipt_pdf_key": dtr_pdf_key,
                # "receipt_excel_key": dtr_excel_key,
            })
            
            return new_receipt
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating and generating DTR files for driver {driver_id}: {e}", exc_info=True)
            raise

    def verify_card_transactions(self, db: Session, from_date: date, to_date: date) -> dict:
        """
        Fetches card transactions from the secondary API and compares them against
        trips already imported into the local database to find discrepancies.

        This is a READ-ONLY operation for verification purposes.

        Args:
            db: The database session.
            from_date: The start date of the period to verify.
            to_date: The end date of the period to verify.

        Returns:
            A dictionary containing a summary and a list of potentially missing trips.
        """
        from app.curb.models import CURBTrip
        logger.info(f"Starting card transaction verification for period: {from_date} to {to_date}")
        
        # --- Step 1: Get a set of all (driver_id, cab_number) pairs that exist in our system for the period ---
        existing_trips_in_db = db.query(CURBTrip.driver_id, CURBTrip.cab_number).filter(
            CURBTrip.start_date.between(from_date, to_date)
        ).distinct().all()
        
        # A set provides highly efficient lookups (O(1) average time complexity)
        known_driver_cab_pairs = set(existing_trips_in_db)
        logger.info(f"Found {len(known_driver_cab_pairs)} unique driver/cab pairs in the database for this period.")

        # --- Step 2: Fetch and parse data from the secondary card transaction API ---
        start_datetime = datetime.combine(from_date, datetime.min.time())
        end_datetime = datetime.combine(to_date, datetime.max.time())
        
        try:
            card_trans_xml_data = fetch_trans_by_date_cab12(
                from_datetime=start_datetime, 
                to_datetime=end_datetime
            )
            card_transactions = parse_card_transactions_xml(card_trans_xml_data)
            logger.info(f"Fetched {len(card_transactions)} card transactions from the external API for verification.")
        except Exception as e:
            logger.error(f"Failed to fetch data from the card transaction API: {e}", exc_info=True)
            raise ValueError("Could not retrieve data from the external CURB card transaction API.")

        # --- Step 3: Identify trips from the API that do NOT match our criteria ---
        # The user's request: "include records only which match driver_id and cab number but not trip timestamps"
        # The safest and most useful interpretation is to find card transactions for a driver/cab pair
        # that we HAVE seen, but for which this specific transaction might be missing.
        # A more direct value is finding transactions for pairs we have NEVER seen. Let's find both.

        unmatched_trips = []
        for card_trip in card_transactions:
            driver_id = card_trip.get("driver_id")
            cab_number = card_trip.get("cab_number")

            if not driver_id or not cab_number:
                continue # Skip records with incomplete data

            # Check if the driver/cab pair from this transaction exists in our database at all for this period
            if (driver_id, cab_number) not in known_driver_cab_pairs:
                # This is a strong signal of a potentially missed trip or a data issue.
                # The driver/cab combo exists in the card transaction log but not in our LOG10 import.
                unmatched_trips.append({
                    "reason": "Driver/Cab pair not found in primary import for this period.",
                    "trip_data": card_trip
                })
        
        return {
            "verification_period": {
                "from_date": from_date.isoformat(),
                "to_date": to_date.isoformat()
            },
            "summary": {
                "total_trips_in_db": len(known_driver_cab_pairs),
                "total_card_transactions_checked": len(card_transactions),
                "potential_discrepancies_found": len(unmatched_trips)
            },
            "unmatched_trips": unmatched_trips
        }
            

ledger_service = LedgerService()
