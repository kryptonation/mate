## app/curb/services.py

"""
CURB Services

This module provides services for CURB data operations.
"""
# Standard library imports
from typing import List, Optional, Union
from datetime import datetime, timezone, date
from math import ceil

# Third party imports
from sqlalchemy.orm import Session 
from sqlalchemy import String , desc, asc , func


# Local imports
from app.utils.logger import get_logger
from app.curb.models import CURBTrip, CURBImportLog, CURBTripReconcilation
from app.ledger.models import LedgerEntry
from app.medallions.models import Medallion
from app.drivers.models import Driver , TLCLicense
from app.curb.utils import parse_trips_xml, parse_card_transactions_xml
from app.leases.models import Lease , LeaseDriver
from app.leases.services import lease_service
from app.medallions.services import medallion_service
from app.drivers.services import driver_service
from app.ledger.models import DailyReceipt
from app.ledger.schemas import LedgerSourceType
from app.curb.soap_client import fetch_trips_log10

logger = get_logger(__name__)


class CURBService:
    """Service for CURB data operations."""
    def import_curb_trips(
        self, db: Session, xml_data: str, cash_xml_data: str = None, import_source: str = "SOAP", import_by: str = "SYSTEM"
    ) -> dict:
        """Import CURB trips from XML data."""
        try:
            from app.vehicles.services import vehicle_service
            trips = parse_card_transactions_xml(xml_data)
            if cash_xml_data:
                cash_trips = parse_trips_xml(cash_xml_data)
                cash_trips = [t for t in cash_trips if t.get("payment_type") == "$"]
                logger.info(f"*** Found {len(cash_trips)} cash trips to merge")
                trips = trips + cash_trips

            # dedup by record_id and period
            existing_keys = {
                (r.record_id) for r in db.query(CURBTrip.record_id).all()
            }

            new_trips = []
            for t in trips:
                key = (t.get("curb_record_id", None))
                if key not in existing_keys:

                    medallion_number_from_curb = t.get("cab_number", None)
                    plate_number = medallion_number_from_curb

                    if medallion_number_from_curb:
                        # Find the medallion in the database
                        medallion = medallion_service.get_medallion(db, medallion_number=medallion_number_from_curb)
                        if medallion:
                            # Find the active vehicle associated with this medallion
                            vehicle = vehicle_service.get_vehicles(db, medallion_id=medallion.id)
                            if vehicle and vehicle.registrations:
                                # Find the currently active registration to get the plate number
                                active_registration = next((reg for reg in vehicle.registrations if reg.is_active), None)
                                if active_registration and active_registration.plate_number:
                                    plate_number = active_registration.plate_number
                                else:
                                    logger.info(f"Medallion {medallion_number_from_curb} has a vehicle, but no active registration with a plate number was found.")
                            else:
                                logger.info(f"No active vehicle is associated with medallion {medallion_number_from_curb} during CURB import.")
                        else:
                             logger.info(f"Medallion {medallion_number_from_curb} from CURB data not found in the system.")

                    new_trips.append(CURBTrip(
                        record_id=t.get("record_id", None),
                        period=t.get("period", None),
                        cab_number=plate_number,
                        driver_id=t.get("driver_id", None),
                        trip_number=t.get("trip_number", None),
                        # Separate date and time components
                        start_date=t.get("start_date"),
                        start_time=t.get("start_time"),
                        end_date=t.get("end_date"),
                        end_time=t.get("end_time"),
                        # Add other trip data fields
                        trip_amount=t.get("trip_amount", None),
                        tips=t.get("tips", None),
                        extras=t.get("extras", None),
                        tolls=t.get("tolls", None),
                        tax=t.get("tax", None),
                        imp_tax=t.get("imp_tax", None),
                        total_amount=t.get("total_amount", None),
                        gps_start_lat=t.get("gps_start_lat", None),
                        gps_start_lon=t.get("gps_start_lon", None),
                        gps_end_lat=t.get("gps_end_lat", None),
                        gps_end_lon=t.get("gps_end_lon", None),
                        from_address=t.get("from_address", None),
                        to_address=t.get("to_address", None),
                        payment_type=t.get("payment_type", None),
                        cc_number=t.get("cc_number", None),
                        auth_code=t.get("auth_code", None),
                        auth_amount=t.get("auth_amount", None),
                        ehail_fee=t.get("ehail_fee", None),
                        health_fee=t.get("health_fee", None),
                        passengers=t.get("passengers", None),
                        distance_service=t.get("distance_service", None),
                        distance_bs=t.get("distance_bs", None),
                        reservation_number=t.get("reservation_number", None),
                        congestion_fee=t.get("congestion_fee", None),
                        airport_fee=t.get("airport_fee", None),
                        cbdt_fee=t.get("cbdt_fee", None)
                    ))

            logger.info("*** Processing trip: %s", len(new_trips))

            log = CURBImportLog(
                import_source=import_source,
                imported_by=import_by,
                total_records=len(new_trips),
                status="IN_PROGRESS"
            )

            db.add(log)
            db.commit()

            for trip in new_trips:
                trip.import_id = log.id

            db.bulk_save_objects(new_trips)

            log.import_end = datetime.now()
            log.status = "COMPLETED"
            db.commit()

            return {"inserted": len(new_trips), "total": len(trips) - len(new_trips)}
        except Exception as e:
            logger.error("Error importing CURB trips: %s", str(e), exc_info=True)
            raise e

    def reconcile_curb_trips(
        self, db: Session, trip_ids: list[str], recon_stat: int, recon_by: str = "SYSTEM"
    ) -> dict:
        """Reconcile CURB trips locally in the database only."""
        try:
            if recon_stat < 0:
                raise ValueError("RECON_STAT must be a positive receipt number")

            # Step 1: Fetch the matching trips
            trips = db.query(CURBTrip).filter(CURBTrip.id.in_(trip_ids)).all()
            if not trips:
                raise ValueError("No valid trips found for reconcilation")

            # Step 2: Local reconciliation - Update database records only
            now = datetime.now(timezone.utc)
            reconciled_trip_ids = []
            
            for trip in trips:
                # Skip if already reconciled
                if trip.is_reconciled:
                    logger.info("Trip %s already reconciled, skipping", trip.id)
                    continue
                    
                # Mark trip as reconciled locally
                trip.recon_stat = recon_stat
                trip.is_reconciled = True
                
                # Create reconciliation record
                db.add(CURBTripReconcilation(
                    trip_id=trip.id,
                    recon_stat=recon_stat,
                    reconciled_at=now,
                    reconciled_by=recon_by
                ))
                
                reconciled_trip_ids.append(trip.id)

            db.commit()
            
            logger.info("Successfully reconciled %s trips locally with recon_stat: %s", len(reconciled_trip_ids), recon_stat)

            return {
                "success": True,
                "trip_ids": reconciled_trip_ids,
                "recon_stat": recon_stat,
                "reconciled_count": len(reconciled_trip_ids),
                "message": f"Local reconciliation completed for {len(reconciled_trip_ids)} trips"
            }
        except Exception as e:
            logger.error("Error reconciling CURB trips locally: %s", str(e), exc_info=True)
            raise e

    def bulk_associate_and_post_trips(
        self, db: Session, posted_by="SYSTEM"
    ) -> dict:
        """Bulk associate and post trips to CURB"""
        try:
            from app.ledger.services import ledger_service
            
            # Step 1: Fetch unreconciled but not posted trips
            trips = db.query(CURBTrip).filter(
                CURBTrip.is_reconciled == True,
                CURBTrip.is_posted == False
            )

            posted, skipped, errors = [], [], []

            for trip in trips:
                # Step 2: Resolve active lease
                lease = lease_service.get_lease(db, driver_id=trip.driver_id, plate_number=trip.cab_number)
                if not lease:
                    skipped.append((trip.id, "Lease not found"))
                    continue

                # Step 3: Avoid duplicate posting
                ledger_entry = ledger_service.get_ledger_entries(
                    db=db,ledger_source=LedgerSourceType.CURB, source_id=trip.id
                )

                if ledger_entry:
                    skipped.append((trip.id, "Already exists in ledger"))
                    trip.is_posted = True
                    continue

                driver = driver_service.get_drivers(db, driver_id=trip.driver_id)
                ledger_entry = ledger_service.upsert_ledgers(db, {
                    "driver_id": driver.id,
                    "medallion_id": lease.medallion_id,
                    "vehicle_id": lease.vehicle_id,
                    "amount": trip.total_amount or 0.0,
                    "debit": True,
                    "source_type": LedgerSourceType.CURB,
                    "source_id": trip.id,
                    "description":f"CURB trip {trip.record_id}-{trip.period} posted"
                })

                db.add(ledger_entry)
                trip.is_posted = True
                posted.append(trip.id)
            
            db.commit()

            return {
                "posted_count": len(posted),
                "skipped": skipped,
                "errors": errors
            }
        except Exception as e:
            logger.error("Error bulk associating and posting trips to CURB: %s", str(e), exc_info=True)
            raise e

    def associate_and_post_trip(
        self, db: Session, trip_id: int, posted_by="SYSTEM"
    ):
        """Associate and post a single trip to CURB"""
        try:
            from app.ledger.services import ledger_service
            
            # Step 1: Fetch the trip
            trip = db.query(CURBTrip).filter(
                CURBTrip.id == trip_id,
                CURBTrip.is_reconciled == True,
                CURBTrip.is_posted == False
            ).first()
            if not trip:
                raise ValueError("Trip not found or already posted")
            
            # Step 2: Resolve active lease
            lease = lease_service.get_lease(db, driver_id=trip.driver_id, plate_number=trip.cab_number)
            if not lease:
                raise ValueError("Lease not found")
            
            # Step 3: Avoid duplicate posting
            ledger_entry = ledger_service.get_ledger_entries(
                db, ledger_source=LedgerSourceType.CURB, source_id=trip.id
            )

            if ledger_entry:
                raise ValueError("Already exists in ledger")

            ledger_entry = ledger_service.upsert_ledgers(db, {
                "driver_id": trip.driver_id,
                "medallion_id": lease.medallion_id,
                "vehicle_id": lease.vehicle_id,
                "amount": trip.total_amount or 0.0,
                "debit": True,
                "source_type": LedgerSourceType.CURB,
                "source_id": trip.id,
                "description":f"CURB trip {trip.curb_record_id}-{trip.period} posted"
            })

            db.add(ledger_entry)
            trip.is_posted = True

            db.commit()

            return {
                "success": True,
            }
        except Exception as e:
            logger.error("Error associating and posting trip to CURB: %s", str(e), exc_info=True)
            raise e

    def parse_comma_values(self, val: Optional[str]):
        """Parse comma-separated values into a list."""
        return [v.strip() for v in val.split(",") if v.strip()] if val else []

    def list_curb_trips(
        self, db: Session, page: int, per_page: int,
        sort_by: str, sort_order: str, filters: dict
    ):
        """List CURB trips with optional filters, sort, and pagination."""
        try:
            logger.debug("list_curb_trips called with: page=%d, per_page=%d, sort_by=%s, sort_order=%s", 
                        page, per_page, sort_by, sort_order)
            
            # First, get the trip IDs with pagination applied
            trip_ids_query = db.query(CURBTrip.id)

            # Apply filters to the trip_ids_query
            if filters.get("driver_id"):
                trip_ids_query = trip_ids_query.filter(
                    CURBTrip.driver_id.in_(self.parse_comma_values(filters["driver_id"]))
                )
            if filters.get("cab_number"):
                trip_ids_query = trip_ids_query.filter(
                    CURBTrip.cab_number.in_(self.parse_comma_values(filters["cab_number"]))
                )
            if filters.get("trip_id"):
                trip_ids = [int(t) for t in self.parse_comma_values(filters["trip_id"])]
                trip_ids_query = trip_ids_query.filter(CURBTrip.id.in_(trip_ids))
            if filters.get("from_date") and filters.get("to_date"):
                trip_ids_query = trip_ids_query.filter(
                    CURBTrip.start_date.between(filters["from_date"], filters["to_date"])
                )
            if filters.get("start_time_from") and filters.get("start_time_to"):
                trip_ids_query = trip_ids_query.filter(
                    CURBTrip.start_time.between(
                        filters["start_time_from"], filters["start_time_to"]
                    )
                )
            if filters.get("end_time_from") and filters.get("end_time_to"):
                trip_ids_query = trip_ids_query.filter(
                    CURBTrip.end_time.between(
                        filters["end_time_from"], filters["end_time_to"]
                    )
                )
            if filters.get("payment_type"):
                trip_ids_query = trip_ids_query.filter(
                    CURBTrip.payment_type.in_(self.parse_comma_values(filters["payment_type"]))
                )
            if filters.get("gps_start_lat"):
                trip_ids_query = trip_ids_query.filter(
                    CURBTrip.gps_start_lat.cast(String).like(f"%{filters['gps_start_lat']}%")
                )
            if filters.get("gps_end_lat"):
                trip_ids_query = trip_ids_query.filter(
                    CURBTrip.gps_end_lat.cast(String).like(f"%{filters['gps_end_lat']}%")
                )
            if filters.get("distance"):
                trip_ids_query = trip_ids_query.filter(
                    CURBTrip.distance_service.cast(String).like(f"%{filters['distance']}%")
                )
            if filters.get("status"):
                status = filters["status"]
                if status == "reconciled":
                    trip_ids_query = trip_ids_query.filter(CURBTrip.is_reconciled.is_(True))
                elif status == "unreconciled":
                    trip_ids_query = trip_ids_query.filter(CURBTrip.is_reconciled.is_(False))
                elif status == "posted":
                    trip_ids_query = trip_ids_query.filter(CURBTrip.is_posted.is_(True))
                elif status == "unposted":
                    trip_ids_query = trip_ids_query.filter(CURBTrip.is_posted.is_(False))

            # Additional filters that require JOINs - apply to trip_ids_query with JOINs
            if filters.get("medallion_number") or filters.get("tlc_license_number"):
                if filters.get("medallion_number"):
                    trip_ids_query = trip_ids_query.join(Driver, Driver.driver_id == CURBTrip.driver_id)\
                        .join(LeaseDriver, LeaseDriver.driver_id == Driver.driver_id)\
                        .join(Lease, Lease.id == LeaseDriver.lease_id)\
                        .join(Medallion, Medallion.id == Lease.medallion_id)\
                        .filter(Medallion.medallion_number.in_(self.parse_comma_values(filters["medallion_number"])))
                
                if filters.get("tlc_license_number"):
                    if not filters.get("medallion_number"):  # Avoid double join
                        trip_ids_query = trip_ids_query.join(Driver, Driver.driver_id == CURBTrip.driver_id)
                    trip_ids_query = trip_ids_query.join(TLCLicense, TLCLicense.id == Driver.tlc_license_number_id)\
                        .filter(TLCLicense.tlc_license_number.in_(self.parse_comma_values(filters["tlc_license_number"])))

            # Get total count
            total = trip_ids_query.count()
            total_revenue = (
                    db.query(func.sum(CURBTrip.total_amount))
                    .filter(CURBTrip.id.in_(trip_ids_query.with_entities(CURBTrip.id)))
                    .scalar()
                ) or 0.0
            logger.debug("[Task ID: Fetch CURB Trips] Total trips found: %d", total)

            # Apply sorting and pagination to trip_ids_query
            allowed_sort_fields = ["start_date", "cab_number", "driver_id", "distance_service", "payment_type", "start_time", "end_time"]
            sort_by = sort_by if sort_by in allowed_sort_fields else "start_date"
            sort_column = getattr(CURBTrip, sort_by)
            order_fn = desc if sort_order == "desc" else asc
            
            offset = (page - 1) * per_page
            logger.debug("[Task ID: Fetch CURB Trips] Applying pagination: offset=%d, limit=%d", offset, per_page)
            
            paginated_trip_ids = trip_ids_query.order_by(order_fn(sort_column)).offset(offset).limit(per_page).all()
            trip_ids_list = [trip_id[0] for trip_id in paginated_trip_ids]
            
            logger.debug("[Task ID: Fetch CURB Trips] Got %d trip IDs for page %d", len(trip_ids_list), page)

            # Now get the full trip data with JOINs for only the paginated trips
            query = (
                db.query(
                    CURBTrip,
                    TLCLicense.tlc_license_number.label('tlc_license_number'),
                    Medallion.medallion_number.label('medallion_number')
                )
                .filter(CURBTrip.id.in_(trip_ids_list))
                .outerjoin(Driver, Driver.driver_id == CURBTrip.driver_id)
                .outerjoin(LeaseDriver, LeaseDriver.driver_id == Driver.driver_id)
                .outerjoin(Lease, Lease.lease_id == LeaseDriver.lease_id)
                .outerjoin(Medallion, Medallion.id == Lease.medallion_id)
                .outerjoin(TLCLicense, TLCLicense.id == Driver.tlc_license_number_id)
                .order_by(order_fn(sort_column))
            )

            results = query.all()
            logger.debug("[Task ID: Fetch CURB Trips] Fetched %d trips for page %d with per_page %d", len(results), page, per_page)
            
            # Define payment type mapping
            pay_type = {
                "$": "Cash",
                "P": "Private",
                "C": "Card"
            }
            
            # Serialize results
            items = [
                {
                    "trip_id": trip.id,
                    "driver_id": trip.driver_id,
                    "cab_number": trip.cab_number,
                    "trip_start_date": trip.start_date,
                    "trip_end_date": trip.end_date,
                    "start_time": trip.start_time,
                    "end_time": trip.end_time,
                    "distance": trip.distance_service,
                    "gps_start_lat": trip.gps_start_lat,
                    "gps_start_lon": trip.gps_start_lon,
                    "gps_end_lat": trip.gps_end_lat,
                    "gps_end_lon": trip.gps_end_lon,
                    "from_address": trip.from_address,
                    "to_address": trip.to_address,
                    "tips": trip.tips,
                    "extras": trip.extras,
                    "tolls": trip.tolls,
                    "tax": trip.tax,
                    "imp_tax": trip.imp_tax,
                    "ehail_fee": trip.ehail_fee,
                    "health_fee": trip.health_fee,
                    "total_amount": trip.total_amount,
                    "payment_type": pay_type[trip.payment_type] if trip.payment_type in pay_type else trip.payment_type,
                    "is_reconciled": trip.is_reconciled,
                    "is_posted": trip.is_posted,
                    "tlc_license_number": tlc_num,
                    "medallion_number": med_num,
                }
                for trip, tlc_num, med_num in results
            ]

            result = {
                "items": items,
                "total_items": total,
                "total_revenue": total_revenue,
                "filters": {
                    "status": {
                        "type": "select",
                        "label": "Status",
                        "placeholder": "Select Status",
                        "options": [
                            {"label": "Reconciled", "value": "reconciled"},
                            {"label": "Unreconciled", "value": "unreconciled"},
                            {"label": "Posted", "value": "posted"},
                            {"label": "Unposted", "value": "unposted"},
                        ]
                    },
                    "payment_type": {
                        "type": "select",
                        "label": "Payment Type",
                        "placeholder": "Select Payment Type",
                        "options": [
                            {"label": "Cash", "value": "T"},
                            {"label": "Private Card", "value": "P"},
                            {"label": "Credit Card", "value": "C"},
                        ]
                    }
                },
                "status_list": ["reconciled", "unreconciled", "posted", "unposted"],
                "payment_type_list": ["T", "P", "C"],
                "page": page,
                "per_page": per_page,
                "total_pages": ceil(total / per_page),
                "sort_fields": allowed_sort_fields
            }
            
            logger.debug("[Task ID: Fetch CURB Trips] Returning %d items, total_items=%d, page=%d, per_page=%d, total_pages=%d", 
                        len(items), total, page, per_page, ceil(total / per_page))
            
            return result

        except Exception as e:
            logger.exception("Error listing CURB trips")
            raise e

    def get_curb_trip(
        self, db: Session,
        trip_id: Optional[int] = None,
        record_id: Optional[str] = None,
        period: Optional[str] = None,
        driver_id: Optional[str] = None,
        cab_number: Optional[str] = None,
        start_date_from: Optional[datetime] = None,
        start_date_to: Optional[datetime] = None,
        end_date_from: Optional[datetime] = None,
        end_date_to: Optional[datetime] = None,
        payment_type: Optional[str] = None,
        is_reconciled: Optional[bool] = None,
        is_posted: Optional[bool] = None,
        multiple: Optional[bool] = False,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None
    ) -> Union[CURBTrip, List[CURBTrip]]:
        """Get CURB trip by ID, record ID, or multiple filters"""
        try:
            query = db.query(CURBTrip)

            if trip_id:
                query = query.filter(CURBTrip.id == trip_id)
            if record_id:
                query = query.filter(CURBTrip.record_id == record_id)
            if period:
                query = query.filter(CURBTrip.period == period)
            if driver_id:
                query = query.filter(CURBTrip.driver_id == driver_id)
            if cab_number:
                query = query.filter(CURBTrip.cab_number == cab_number)
            if start_date_from:
                query = query.filter(CURBTrip.start_date >= start_date_from)
            if start_date_to:
                query = query.filter(CURBTrip.start_date <= start_date_to)
            if end_date_from:
                query = query.filter(CURBTrip.end_date >= end_date_from)
            if end_date_to:
                query = query.filter(CURBTrip.end_date <= end_date_to)
            if payment_type:
                query = query.filter(CURBTrip.payment_type == payment_type)
            if is_reconciled is not None:
                query = query.filter(CURBTrip.is_reconciled == is_reconciled)
            if is_posted is not None:
                query = query.filter(CURBTrip.is_posted == is_posted)

            if sort_by and sort_order:
                query = query.order_by(
                    desc(getattr(CURBTrip, sort_by)) if sort_order == "desc" else asc(getattr(CURBTrip, sort_by))
                )
            
            if multiple:
                return query.all()
            else:
                return query.first()
        except Exception as e:
            logger.error("Error getting CURB trip: %s", str(e), exc_info=True)
            raise e

    def get_curb_revenue(
        self, db: Session, start_date, end_date, driver_id
    ):
        """Get CURB revenue for the trip"""
        try:
            return db.query(func.sum(CURBTrip.total_amount)).filter(
                CURBTrip.driver_id == str(driver_id),
                CURBTrip.start_date >= start_date,
                CURBTrip.end_date <= end_date
            ).scalar() or 0.0
        except Exception as e:
            logger.error("Error getting CURB revenue: %s", str(e), exc_info=True)
            raise e

    def finalize_driver_payments(
        self, db: Session, start_date, end_date
    ):
        """Finalize Driver Payments"""
        try:
            dtrs = db.query(DailyReceipt).filter(
                DailyReceipt.period_start >= start_date,
                DailyReceipt.period_end <= end_date
            ).all()

            results = []
            for dtr in dtrs:
                driver = driver_service.get_drivers(db, id=dtr.driver_id)
                lease = lease_service.get_lease(db, lookup_id=dtr.lease_id)
                medallion = medallion_service.get_medallion(db, medallion_id=dtr.medallion_id)
                curb_revenue = curb_service.get_curb_revenue(db, start_date, end_date, driver.driver_id)

                # Total payments made via ledger (e.g., cash or DTR adjustments)
                ledger_payments = db.query(func.sum(LedgerEntry.amount)).filter(
                    LedgerEntry.driver_id == dtr.driver_id,
                    LedgerEntry.created_on >= dtr.period_start,
                    LedgerEntry.created_on <= dtr.period_end,
                    LedgerEntry.debit == False
                ).scalar() or 0.0

                # Shift
                shift = lease.lease_type if lease else "N/A"

                results.append({
                    "receipt_id": dtr.receipt_number,
                    "receipt_date": dtr.period_start.date().isoformat(),
                    "medallion_number": medallion.medallion_number if medallion else "N/A",
                    "shift": shift,
                    "ach": "Yes" if getattr(dtr, "is_ach_ready", False) else "No",
                    "dtr_revenue": round(curb_revenue, 2),
                    "cash_paid": round(dtr.cash_paid or 0.0, 2),
                    "dtr_paid": round(ledger_payments, 2),
                    "payment": round(dtr.balance or 0.0, 2),
                    "receipt_urls": {
                        "html": dtr.receipt_html_url,
                        "pdf": dtr.receipt_pdf_url,
                        "excel": dtr.receipt_excel_url
                    }
                })
                
            return results
        except Exception as e:
            logger.error("Error finalizing driver payments: %s", e, exc_info=True)
            raise e

    def bulk_reconcile_trips_locally(
        self, db: Session, recon_by: str = "SYSTEM"  
    ) -> dict:
        """Bulk reconcile all unreconciled CURB trips locally without calling remote API."""
        try:
            # Get all unreconciled trips
            unreconciled_trips = db.query(CURBTrip).filter(
                CURBTrip.is_reconciled == False
            ).all()
            
            if not unreconciled_trips:
                logger.info("No unreconciled trips found for bulk reconciliation")
                return {
                    "success": True,
                    "reconciled_count": 0,
                    "message": "No trips to reconcile"
                }
            
            # Generate a timestamp-based receipt number
            recon_stat = int(datetime.now().timestamp())
            
            # Convert to string IDs as expected by reconcile_curb_trips
            trip_ids = [str(trip.id) for trip in unreconciled_trips]
            
            logger.info("Starting bulk local reconciliation for %s trips", len(trip_ids))
            
            # Use existing reconciliation method (now local-only)
            result = self.reconcile_curb_trips(
                db=db, 
                trip_ids=trip_ids, 
                recon_stat=recon_stat, 
                recon_by=recon_by
            )
            
            return result
            
        except Exception as e:
            logger.error("Error in bulk local reconciliation: %s", str(e), exc_info=True)
            raise e
        
    def process_trips_for_date_range(
        self, db: Session, from_date: date, to_date: date, import_by: str, driver_id: Optional[str] = None
    ) -> dict:
        """
        A complete workflow to fetch, import, reconcile, and post trips for a specific date range.
        Designed to be run in the background.
        """
        logger.info(f"Starting full trip processing for {from_date} to {to_date}")
        try:
            # Step 1: Fetch trips from the CURB SOAP API
            # The SOAP client expects MM/DD/YYYY format
            from_date_str = from_date.strftime("%m/%d/%Y")
            to_date_str = to_date.strftime("%m/%d/%Y")

            logger.info(f"Fetching trips from CURB API for dates: {from_date_str} to {to_date_str}")
            if driver_id:
                trip_xml_data = fetch_trips_log10(from_date=from_date_str, to_date=to_date_str, driver_id=driver_id)
            else:
                trip_xml_data = fetch_trips_log10(from_date=from_date_str, to_date=to_date_str)

            if not trip_xml_data:
                logger.warning(f"No trip data returned from CURB API for the specified date range.")
                return
            
            # Step 2: Import the fetched trips into the database
            import_result = self.import_curb_trips(
                db=db, xml_data=trip_xml_data, import_source="Manual Import", import_by=import_by
            )
            inserted_count = import_result.get("inserted", 0)
            logger.info(f"Imported {inserted_count} new trips from the manual fetch.")

            # Step 3 & 4 only need to run if new trips were actually added
            if inserted_count > 0:
                # Step 3: Reconcile all newly imported and other unreconciled trips
                logger.info("Proceeding with local bulk reconcilation")
                self.bulk_reconcile_trips_locally(db=db, recon_by=import_by)

                # Step 4: Post all newly reconciled and other unposted trips
                logger.info("Proceeding with bulk posting of ledger.")
                self.bulk_associate_and_post_trips(db=db, posted_by=import_by)

            logger.info(f"Successfully completed manual trip processing for {from_date} to {to_date}")

        except Exception as e:
            logger.error(f"An error occurred during manual trip processing: {str(e)}", exc_info=True)
        

curb_service = CURBService()
