### app/pvb/services.py

# Standard library imports
from datetime import datetime, timezone , date , time
from typing import Union, List, Optional

# Third party imports
from sqlalchemy.orm import Session
from sqlalchemy import select, or_ , func


# Local imports
from app.utils.logger import get_logger
from app.pvb.models import PVBLog, PVBViolation
from app.medallions.models import Medallion, MedallionOwner
from app.entities.models import Individual, Corporation
from app.vehicles.models import Vehicle, VehicleRegistration
from app.drivers.models import Driver, TLCLicense
from app.drivers.services import driver_service
from app.leases.models import Lease, LeaseDriver
from app.medallions.services import medallion_service
from app.ledger.services import ledger_service
from app.leases.services import lease_service
from app.ledger.models import LedgerSourceType
from app.vehicles.services import vehicle_service
from app.services.common import common_service
from app.utils.general import parse_custom_time

logger = get_logger(__name__)


class PVBService:
    """PVB service for operations"""
    def get_pvb_log(
        self, db: Session,
        log_id: Optional[int] = None,
        log_from_date: Optional[datetime] = None,
        log_to_date: Optional[datetime] = None,
        log_status: Optional[str] = None,
        log_type: Optional[str] = None,
        records_impacted: Optional[int] = None,
        success_count: Optional[int] = None,
        unidentified_count: Optional[int] = None,
        page: Optional[int] = 1,
        per_page: Optional[int] = 10,
        sort_order: Optional[str] = "desc",
        sort_by: Optional[str] = "log_date",
        multiple: Optional[bool] = None
    ) -> Union[PVBLog, List[PVBLog]]:
        """Get PVB log by id or multiple"""
        try:
            query = db.query(PVBLog)

            if log_id:
                query = query.filter(PVBLog.id == log_id)
            if log_from_date:
                query = query.filter(PVBLog.log_date >= log_from_date)
            if log_to_date:
                query = query.filter(PVBLog.log_date <= log_to_date)
            if log_status:
                query = query.filter(PVBLog.status == log_status)
            if log_type:
                query = query.filter(PVBLog.log_type == log_type)
            if records_impacted:
                query = query.filter(PVBLog.records_impacted == records_impacted)
            if success_count:
                query = query.filter(PVBLog.success_count == success_count)
            if unidentified_count:
                query = query.filter(PVBLog.unidentified_count == unidentified_count)

            if multiple:
                total_count = query.count()
                
                if sort_order == "asc":
                    query = query.order_by(getattr(PVBLog, sort_by).asc())
                else:
                    query = query.order_by(getattr(PVBLog, sort_by).desc())
                
                if page and per_page :
                    query = query.offset((page - 1) * per_page).limit(per_page)

                return query.all() , total_count
            
            return query.first()
        except Exception as e:
            logger.error("Error getting PVB log: %s", str(e))
            raise e
        
    def get_pvb(
        self, db: Session,
        violation_id: Optional[int] = None,
        plate_number: Optional[str] = None,
        record_status: Optional[str] = None,
        vehicle_id : Optional[str] = None,
        driver_id : Optional[str] = None,
        medallion_id : Optional[str] = None,
        type: Optional[str] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        summons_number: Optional[str] = None,
        state : Optional[str] = None,
        issue_from_date: Optional[datetime] = None,
        issue_to_date: Optional[datetime] = None,
        issue_time_from: Optional[time] = None,
        issue_time_to: Optional[time] = None,
        sort_by: Optional[str] = "updated_on",
        sort_order: Optional[str]= "desc",
        multiple: Optional[bool] = None
    ) -> Union[PVBViolation, List[PVBViolation]]:
        """Get PVB violation by id or multiple"""
        try:
            query = db.query(PVBViolation)

            if violation_id:
                query = query.filter(PVBViolation.id == violation_id)
                
            if plate_number:
                numbers = [plates.strip() for plates in plate_number.split(",") if plates.strip()]
                query = query.filter(or_(*[PVBViolation.plate_number.ilike(f"%{number}%") for number in numbers]))
                
            if record_status:
                statuses = record_status.split(",")
                query = query.filter(PVBViolation.status.in_(statuses))
            
            if vehicle_id:
                vehicle_ids = vehicle_id.split(",")
                query = query.filter(PVBViolation.vehicle_id.in_(vehicle_ids))
            
            if driver_id:
                driver_ids = driver_id.split(",")
                query = query.filter(PVBViolation.driver_id.in_(driver_ids))

            if medallion_id:
                medallion_ids = medallion_id.split(",")
                query = query.filter(PVBViolation.medallion_id.in_(medallion_ids))

            if type:
                types = type.split(",")
                query = query.filter(PVBViolation.vehicle_type.in_(types))
            
            if summons_number :
                numbers = [num.strip() for num in summons_number.split(",") if num.strip()]
                query = query.filter(or_(*[PVBViolation.summons_number.ilike(f"%{number}%") for number in numbers]))
            
            if state :
                states = state.split(",")
                query = query.filter(PVBViolation.state.in_(states))
            
            if issue_from_date:
                query = query.filter(PVBViolation.issue_date >= issue_from_date)
            
            if issue_to_date:
                query = query.filter(PVBViolation.issue_date <= issue_to_date)  

            if issue_time_from:
                query = query.filter(
                   PVBViolation.issue_time >= issue_time_from
                )

            if issue_time_to:
                query = query.filter(
                   PVBViolation.issue_time <= issue_time_to
                )

            if sort_by and sort_order:
                sort_attr ={
                    "id": PVBViolation.id,
                    "plate_number": PVBViolation.plate_number,
                    "state": PVBViolation.state,
                    "type": PVBViolation.vehicle_type,
                    "summons_number": PVBViolation.summons_number,
                    "issue_date": PVBViolation.issue_date,
                    "issue_time": PVBViolation.issue_time,
                    "amount_due": PVBViolation.amount_due,
                    "amount_paid": PVBViolation.amount_paid,
                    "status": PVBViolation.status,
                    "created_on": PVBViolation.created_on,
                    "updated_on": PVBViolation.updated_on
                }

                if sort_by in sort_attr:
                    if sort_order == "asc":
                        query = query.order_by(sort_attr[sort_by].asc())
                    else:
                        query = query.order_by(sort_attr[sort_by].desc())
                
            if multiple:
                total_count = query.count()
                if page and per_page :
                    query = query.offset((page - 1) * per_page).limit(per_page)

                return query.all(), total_count
            
            return query.first()
        except Exception as e:
            logger.error("Error getting PVB violation: %s", str(e))
            raise e
        
    def upsert_pvb_log(self, db: Session, log_data: dict) -> PVBLog:
        """Upsert PVB log"""
        try:
            if log_data.get("id"):
                log = self.get_pvb_log(db, log_data["id"])
                if not log:
                    raise ValueError("Log not found")
                
                for key, value in log_data.items():
                    setattr(log, key, value)
            else:
                log = PVBLog(**log_data)
            
            db.add(log)
            db.commit()
            db.refresh(log)
            return log
        except Exception as e:
            logger.error("Error upserting PVB log: %s", str(e))
            raise e
        
    def upsert_pvb_violation(self, db: Session, violation_data: dict) -> PVBViolation:
        """Upsert PVB violation"""
        try:
            if violation_data.get("id"):
                violation = self.get_pvb(db, violation_data["id"])
                if not violation:
                    raise ValueError("Violation not found")
                
                for key, value in violation_data.items():
                    setattr(violation, key, value)
            else:
                violation = PVBViolation(**violation_data)
            
            db.add(violation)
            db.commit()
            db.refresh(violation)
            return violation
        except Exception as e:
            logger.error("Error upserting PVB violation: %s", str(e))
            raise e

    def parse_date_flexibly(self , date_str: str) -> date:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        raise ValueError(f"Unrecognized date format: {date_str}")
        
    def import_pvb(
        self, db: Session, rows: list[dict]
    ):
        """Import PVB violations from CSV"""
        try:
            imported, failed = 0, 0
            failed_rows = {}

            log_data = {
                "log_date": datetime.now(timezone.utc),
                "log_type": "Import",
                "records_impacted": len(rows),
                "status": "Pending"
            }

            log = self.upsert_pvb_log(db, log_data)

            for row in rows:
                violation_data = {}
                try:
                    violation_data = {
                        "summons_number": row["SUMMONS"],
                        "plate_number": row["PLATE"],
                        "state": row["STATE"],
                        "vehicle_type": row.get("TYPE"),
                        "issue_date": self.parse_date_flexibly(row["ISSUE DATE"]),
                        "issue_time": parse_custom_time(row.get("ISSUE TIME")) if row.get("ISSUE TIME") else "",
                        "amount_due": int(float(row["AMOUNT DUE"])),
                        "status": "Imported",
                        "log_id": log.id
                    }
                    self.upsert_pvb_violation(db, violation_data)  # <- only insert if valid
                    imported += 1

                except Exception as e:
                    failed += 1
                    failed_rows[row.get("SUMMONS", f"row_{failed}")] = str(e)
                    logger.warning("Skipping invalid PVB row due to error: %s", str(e))
                    continue  # <- prevent inserting empty data

            log_data["success_count"] = imported
            log_data["unidentified_count"] = failed
            log_data["status"] = "Partial" if failed else "Success"
            log_data["id"] = log.id

            self.upsert_pvb_log(db, log_data)
            logger.info("PVB import completed: %s records imported, %s failed", imported, failed)
            self.associate_pvb(db)
            self.post_pvb(db)

            return {
                "message": "PVB import completed",
                "success": imported,
                "failed": failed,
                "log_id": log.id,
                "transaction_failed": failed_rows
            }
        except Exception as e:
            logger.error("Error importing PVB: %s", str(e), exc_info=True)
            raise e
    
    def associate_pvb(
        self, db: Session
    ) -> dict:
        """Associate PVB"""
        try:
            records, count = self.get_pvb(db, record_status="Imported", multiple=True)
            logger.info("Associating number of pvb : %s" , len(records))
            associated, failed = 0, 0


            log_data = {
                "log_date": datetime.now(timezone.utc),
                "log_type": "Associate",
                "records_impacted": len(records),
                "status": "Pending"
            }

            log = self.upsert_pvb_log(db, log_data)

            for record in records:
                record_data = {}
                try:
                    driver_id, _ = common_service.resolve_driver_from_curb(db, record.plate_number, record.issue_date)
                    driver = driver_service.get_drivers(db=db , driver_id=driver_id)
                    if not driver_id:
                        record_data["status"] = "Associate Failed"
                        record_data["associated_failed_reason"] = "No driver found"
                        failed += 1
                        logger.info("Driver found for plate number %s: %s", record.plate_number, driver_id)
                        continue
                    
                    vehicle = vehicle_service.get_vehicles(
                        db, plate_number=record.plate_number
                    )

                    if not vehicle:
                        record_data["status"] = "Associate Failed"
                        record_data["associated_failed_reason"] = "No vehicle found"
                        failed += 1
                        logger.info("Vehicle found for plate number %s: %s", record.plate_number, vehicle)
                        continue
                    
                    lease = lease_service.get_lease(
                        db, vehicle_id=vehicle.id,plate_number=record.plate_number, driver_id=driver_id
                    )

                    if not lease:
                        record_data["status"] = "Associate Failed"
                        record_data["associated_failed_reason"] = "No active lease found"
                        failed += 1
                        continue

                    lease_driver = lease_service.get_lease_drivers(db, lease_id=lease.id)
                    record_data["status"] = "Associated"
                    record_data["vehicle_id"] = vehicle.id
                    record_data["driver_id"] = driver.id
                    record_data["medallion_id"] = lease.medallion_id
                    associated += 1

                except Exception as e:
                    record_data["status"] = "Associate Failed"
                    record_data["associated_failed_reason"] = str(e)
                    failed += 1

                self.upsert_pvb_violation(db, {"id": record.id, **record_data})
            
            log_data["success_count"] = associated
            log_data["unidentified_count"] = failed
            log_data["status"] = "Partial" if failed else "Success"
            log_data["id"] = log.id

            self.upsert_pvb_log(db, log_data)

            return {
                "message": "PVB Association Completed",
                "associated": associated,
                "failed": failed,
                "log_id": log.id
            }
        except Exception as e:
            logger.error("Error associating PVB: %s", str(e))
            raise e
        
    def fetch_driver_id_pvb(self, db: Session, step_data: dict) -> Optional[dict]:
        """
        Fetch the driver ID for the PVB based on plate number, TLC license number, or medallion number.
        
        Args:
            db: Database session
            step_data: Dictionary containing search criteria (plate_number, tlc_license_number, or medallion_number)
            
        Returns:
            Optional[dict]: Dictionary containing driver and related information, or None if no match found
        """
        try:
            filters = []
            if step_data.get("plate_number"):
                filters.append(VehicleRegistration.plate_number == step_data["plate_number"])
            if step_data.get("tlc_license_number"):  # Fixed spelling
                filters.append(TLCLicense.tlc_license_number == step_data["tlc_license_number"])
            if step_data.get("medallion_number"):
                filters.append(Medallion.medallion_number == step_data["medallion_number"])

            if not filters:
                logger.warning("No valid search criteria provided")
                return None

            stmt = (
                select(Driver, Medallion, VehicleRegistration, TLCLicense,Individual, Corporation)
                .select_from(Medallion)
                .outerjoin(Vehicle, Vehicle.medallion_id == Medallion.id)
                .outerjoin(VehicleRegistration, VehicleRegistration.vehicle_id == Vehicle.id)
                .outerjoin(Lease, Vehicle.id == Lease.vehicle_id)
                .outerjoin(LeaseDriver, Lease.id == LeaseDriver.lease_id)
                .outerjoin(Driver, LeaseDriver.driver_id == Driver.driver_id)
                .outerjoin(TLCLicense, Driver.tlc_license_number_id == TLCLicense.id)
                .outerjoin(MedallionOwner, Medallion.owner_id == MedallionOwner.id)
                .outerjoin(Individual, MedallionOwner.individual_id == Individual.id)
                .outerjoin(Corporation, MedallionOwner.corporation_id == Corporation.id)
                .where(or_(*filters))
            )

            result = db.execute(stmt)
            row = result.first()

            if not row:
                return None
            
            driver = row.Driver
            medallion = row.Medallion
            vehicle_registration = row.VehicleRegistration
            tlc_license = row.TLCLicense



            return {
                "id": driver.id if driver else None,
                "driver_id": driver.driver_id if driver else None,
                "driver_name": f"{driver.first_name} {driver.last_name}" if driver else None,
                "medallion_number": medallion.medallion_number if medallion else None,
                "medallion_owner": (
                    f"{row.Individual.first_name} {row.Individual.last_name}" if row.Individual else
                    row.Corporation.name if row.Corporation else None
                ),
                "plate_number": vehicle_registration.plate_number if vehicle_registration else None,
                "tlc_license_number": tlc_license.tlc_license_number if tlc_license else None,
            }
        except Exception as e:
            logger.error("Error fetching driver ID: %s", str(e))
            raise

    def post_pvb(self, db: Session) -> Optional[dict]:
        """
        Post PVB violations to the external system.

        Args:
            db: Database session

        Returns:
            Optional[dict]: Dictionary containing the result of the post operation
        """

        transactions , count = self.get_pvb(db, record_status="Associated", multiple=True)
        logger.info("Posting number of pvb : %s" , len(transactions))
        posted, failed = 0, 0

        log_data = {
            "log_date": datetime.now(timezone.utc),
            "log_type": "Post",
            "records_impacted": len(transactions),
            "status": "Pending"
        }

        log = self.upsert_pvb_log(db, log_data)

        for transaction in transactions:
            transaction_data = {}
            try:
                if not all([
                    transaction.driver_id,
                    transaction.medallion_id,
                    transaction.vehicle_id,
                ]) and transaction.amount_paid is None:
                    transaction_data["status"] = "Posting Failed"
                    transaction_data["post_failed_reason"] = "Missing required fields"
                    logger.warning("Missing required fields for posting PVB")
                    failed += 1
                    continue

                ledger_service.upsert_ledgers(db, {
                    "driver_id": transaction.driver_id,
                    "medallion_id": transaction.medallion_id,
                    "vehicle_id": transaction.vehicle_id,
                    "amount": transaction.amount_paid,
                    "debit": True,
                    "description": f"PVB toll posted on {transaction.issue_date} for plate {transaction.plate_number}",
                    "source_type": LedgerSourceType.PVB,
                    "source_id": transaction.id
                })

                transaction_data["status"] = "Posted"
                posted += 1

            except Exception as e:
                transaction_data["status"] = "Posting Failed"
                transaction_data["post_failed_reason"] = str(e)
                logger.error("Error posting PVB: %s", str(e))
                failed += 1

            # Update individual transaction if needed
            self.upsert_pvb_violation(db=db, violation_data={"id": transaction.id, **transaction_data})

        # Final log update
        log_data["id"] = log.id
        log_data["success_count"] = posted
        log_data["unidentified_count"] = failed
        log_data["status"] = "Partial" if failed else "Success"
        
        self.upsert_pvb_log(db, log_data)

        return {
            "message": "Posting to central ledger completed",
            "posted": posted,
            "failed": failed,
            "log_id": log.id
        }
                
pvb_service = PVBService()
