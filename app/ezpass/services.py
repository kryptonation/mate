### app/ezpass/services.py

# Standard library imports
from typing import Union, Optional, List
from datetime import datetime, timezone

# Third party imports
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_

# Local imports
from app.utils.logger import get_logger
from app.ezpass.models import EZPassLog, EZPassTransaction
from app.ezpass.utils import validate_ezpass_file, extract_amount
from app.medallions.services import medallion_service
from app.vehicles.services import vehicle_service
from app.leases.services import lease_service
from app.ledger.services import ledger_service
from app.services.common import common_service
from app.pvb.services import pvb_service
from app.ledger.schemas import LedgerSourceType

logger = get_logger(__name__)


class EZPassService:
    """EZPass services for operations"""
    def get_ezpass_log(
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
        multiple: Optional[bool] = False
    ) -> Union[EZPassLog, List[EZPassLog]]:
        """Get EZPass log by ID, date, or status"""
        try:
            query = db.query(EZPassLog)

            if log_id:
                query = query.filter(EZPassLog.id == log_id)
            if log_status:
                log_statuses = log_status.split(",")
                query = query.filter(EZPassLog.status.in_(log_statuses))
            if log_type:
                log_types = log_type.split(",")
                query = query.filter(EZPassLog.log_type.in_(log_types))
            if log_from_date:
                log_from_date = datetime.combine(log_from_date, datetime.min.time())
                query = query.filter(
                    EZPassLog.log_date >= log_from_date
                )
            if log_to_date:
                log_to_date = datetime.combine(log_to_date, datetime.max.time())
                query = query.filter(
                    EZPassLog.log_date <= log_to_date
                )
            if records_impacted:
                query = query.filter(EZPassLog.records_impacted == records_impacted)
            if success_count:
                query = query.filter(EZPassLog.success_count == success_count)
            if unidentified_count:
                query = query.filter(EZPassLog.unidentified_count == unidentified_count)

            if multiple:
                total_count = query.count()
                if sort_order == "desc":
                    query = query.order_by(getattr(EZPassLog, sort_by).desc())
                else:
                    query = query.order_by(getattr(EZPassLog, sort_by).asc())

                if page and per_page:
                    query = query.offset((page - 1) * per_page).limit(per_page)

                return query.all(), total_count
            return query.first()
        except Exception as e:
            logger.error("Error getting EZPass log: %s", str(e))
            raise e
    
    def get_ezpass_transaction(
        self, db: Session,
        transaction_id: Optional[int] = None,
        transaction_from_date: Optional[datetime] = None,
        transaction_to_date: Optional[datetime] = None,
        transaction_status: Optional[str] = None,
        medallion_no: Optional[str] = None,
        driver_id: Optional[str] = None,
        plate_no: Optional[str] = None,
        posting_from_date: Optional[datetime] = None,
        posting_to_date: Optional[datetime] = None,
        page: Optional[int] = None,
        per_page: Optional[int] = None,
        sort_order: Optional[str] = "desc",
        sort_by: Optional[str] = "transaction_date",
        multiple: Optional[bool] = False
    ) -> Union[EZPassTransaction, List[EZPassTransaction]]:
        """Get EZPass transaction by ID, date, or status"""
        try:
            query = db.query(EZPassTransaction)

            if transaction_id:
                query = query.filter(EZPassTransaction.id == transaction_id)
            if transaction_status:
                transaction_statuses = transaction_status.split(",")
                # Case insensitive matching for each transaction status
                transaction_status_filters = [EZPassTransaction.status.ilike(f"%{status}%") for status in transaction_statuses]
                query = query.filter(or_(*transaction_status_filters))
            if transaction_from_date:
                query = query.filter(
                    EZPassTransaction.transaction_date >= transaction_from_date.date()
                )
            if transaction_to_date:
                query = query.filter(
                    EZPassTransaction.transaction_date <= transaction_to_date.date()
                )
            if posting_from_date:
                query = query.filter(
                    EZPassTransaction.posting_date >= posting_from_date
                )
            if posting_to_date:
                query = query.filter(
                    EZPassTransaction.posting_date <= posting_to_date
                )
            if medallion_no:
                medallion_nos = medallion_no.split(",")
                # Case insensitive matching for each medallion number
                medallion_filters = [EZPassTransaction.medallion_no.ilike(f"%{medallion}%") for medallion in medallion_nos]
                query = query.filter(or_(*medallion_filters))
            if driver_id:
                driver_ids = driver_id.split(",")
                # Case insensitive matching for each driver id
                driver_filters = [EZPassTransaction.driver_id.ilike(f"%{driver}%") for driver in driver_ids]
                query = query.filter(or_(*driver_filters))
            if plate_no:
                plate_nos = plate_no.split(",")
                # Case insensitive matching for each plate number
                plate_filters = [EZPassTransaction.plate_no.ilike(f"%{plate}%") for plate in plate_nos]
                query = query.filter(or_(*plate_filters))

            if multiple:
                total_count = query.count()
                if sort_order == "desc":
                    query = query.order_by(getattr(EZPassTransaction, sort_by).desc())
                else:
                    query = query.order_by(getattr(EZPassTransaction, sort_by).asc())
                if page and per_page:
                    query = query.offset((page - 1) * per_page).limit(per_page)
                return query.all(), total_count
            return query.first()
        except Exception as e:
            logger.error("Error getting EZPass transaction: %s", str(e))
            raise e
    
    def upsert_ezpass_log(
        self, db: Session,
        log_data: dict
    ):
        """Upsert EZPass log"""
        try:
            if log_data.get("id"):
                log = self.get_ezpass_log(db, log_id=log_data["id"])
                if not log:
                    raise ValueError("Log not found")
                for key, value in log_data.items():
                    setattr(log, key, value)
            else:
                log = EZPassLog(**log_data)
            db.add(log)
            db.commit()
            db.refresh(log)
            return log
        except Exception as e:
            logger.error("Error upserting EZPass log: %s", str(e))
            db.rollback()
            raise e
    
    def upsert_ezpass_transaction(
        self, db: Session,
        transaction_data: dict
    ):
        """Upsert EZPass transaction"""
        try:
            if transaction_data.get("id"):
                transaction = self.get_ezpass_transaction(db, transaction_id=transaction_data["id"])
                if not transaction:
                    raise ValueError("Transaction not found")
                for key, value in transaction_data.items():
                    setattr(transaction, key, value)
            else:
                transaction = EZPassTransaction(**transaction_data)
            db.add(transaction)
            db.commit()
            db.refresh(transaction)
            return transaction
        except Exception as e:
            logger.error("Error upserting EZPass transaction: %s", str(e))
            db.rollback()
            raise e
        
    def process_ezpass_data(
        self, db: Session, rows: List[dict]
    ) -> dict:
        """Process EZPass data"""
        try:
            log_data = {
                "log_date": datetime.now(timezone.utc),
                "log_type": "Import",
                "records_impacted": len(rows),
                "status": "In Progress"
            }
            log = self.upsert_ezpass_log(db, log_data)

            success = 0
            failed_count = 0
            failed_transactions = {}

            for row in rows:
                try:
                    # Map new headers to model fields
                    trans_date_str = row.get("Date")
                    exit_time_str = row.get("Exit Time")
                    
                    transaction_data = {
                        "transaction_id": row.get("Lane Txn ID"),
                        "transaction_date": datetime.strptime(trans_date_str, "%m/%d/%Y").date() if trans_date_str else None,
                        "transaction_time": datetime.strptime(exit_time_str, "%I:%M %p").time() if exit_time_str else None,
                        "tag_or_plate": row.get("Tag/Plate #"),
                        "agency": row.get("Agency"),
                        "entry_plaza": row.get("Entry Plaza"),
                        "exit_plaza": row.get("Exit Plaza"),
                        "amount": extract_amount(row.get("Amount")),
                        "log_id": log.id,
                        "status": "Imported"
                    }
                    self.upsert_ezpass_transaction(db, transaction_data)
                    success += 1
                except Exception as e:
                    failed_count += 1
                    failed_transactions[row.get("Lane Txn ID", f"row_{failed_count}")] = str(e)
                    logger.error(f"Error processing row: {row}. Error: {e}")

            # Finalize the log
            self.upsert_ezpass_log(db, {
                "id": log.id, "success_count": success, "unidentified_count": failed_count,
                "status": "Partial" if failed_count > 0 else "Success"
            })
            
            # Trigger the association process after a successful import
            if success > 0:
                self.associate_records(db)


            return {
                "message": "Imported completed",
                "success": success,
                "failed": failed_count,
                "log_id": log.id,
                "transaction_failed": failed_transactions
            }
        except Exception as e:
            logger.error("Error processing EZPass data: %s", str(e))
            raise e
        
    def associate_records(self, db: Session) -> dict:
        """
        Associate imported EZPass transactions with vehicles and drivers using CURB data.
        """
        from app.drivers.services import driver_service
        transactions, _ = self.get_ezpass_transaction(db, transaction_status="Imported", multiple=True)
        associated, failed = 0, 0

        log = self.upsert_ezpass_log(db, {
            "log_date": datetime.now(timezone.utc), "log_type": "Associate",
            "records_impacted": len(transactions), "status": "In Progress"
        })

        for txn in transactions:
            update_data = {"id": txn.id}
            try:
                tag_or_plate = txn.tag_or_plate
                
                # --- LOGIC TO IDENTIFY PLATE NUMBER ---
                # A simple heuristic: if it contains letters, it's a plate.
                # E-ZPass tags are typically numeric. This can be made more robust if needed.
                plate_number = None
                if any(c.isalpha() for c in tag_or_plate):
                    # It's likely a plate, may have state prefix e.g., "NY T123456C"
                    plate_number = tag_or_plate.split()[-1] # Get the last part
                else:
                    # It's a tag ID, find the vehicle associated with this tag to get the plate
                    # (This is a placeholder for a future enhancement if you track tag assignments)
                    raise ValueError(f"Tag ID '{tag_or_plate}' found. Association by tag not yet implemented.")
                
                txn.plate_no = plate_number
                
                # Use the common service to find the driver from CURB trip data
                driver_id, _ = common_service.resolve_driver_from_curb(db, plate_number, txn.transaction_date)
                
                if not driver_id:
                    raise ValueError("Driver could not be resolved from CURB data for the given plate and date.")

                vehicle = vehicle_service.get_vehicles(db, plate_number=plate_number)
                lease = lease_service.get_lease(db, vehicle_id=vehicle.id, driver_id=driver_id)
                driver = driver_service.get_drivers(db, driver_id=driver_id)
                update_data.update({
                    "vehicle_id": vehicle.id if vehicle else None,
                    "driver_id": driver.id,
                    "medallion_no": lease.medallion.medallion_number if lease and lease.medallion else None,
                    "status": "Associated"
                })
                associated += 1
            except Exception as e:
                update_data.update({"status": "Association Failed", "associate_failed_reason": str(e)})
                failed += 1
                logger.warning(f"Failed to associate EZPass Txn {txn.id}: {e}")

            self.upsert_ezpass_transaction(db, update_data)
        
        # Finalize log
        self.upsert_ezpass_log(db, {"id": log.id, "success_count": associated, "unidentified_count": failed, "status": "Partial" if failed > 0 else "Success"})
        
        # Trigger posting after association
        if associated > 0:
            self.post_ezpass(db)

        return {"associated": associated, "failed": failed, "log_id": log.id}

    def post_ezpass(
        self, db: Session
    ) -> dict:
        """Post EZPass"""
        transactions , total_count = self.get_ezpass_transaction(db, transaction_status="Associated", multiple=True)
        posted, failed = 0, 0

        log_data = {
            "log_date": datetime.now(timezone.utc),
            "log_type": "Post",
            "records_impacted": len(transactions),
            "status": "Pending"
        }
        log = self.upsert_ezpass_log(db, log_data)

        for transaction in transactions:
            transaction_data = {}
            try:
                if not all([transaction.driver_id, transaction.medallion_no, transaction.vehicle_id, transaction.amount]):
                    transaction_data["status"] = "Posting Failed"
                    transaction["post_failed_reason"] = "Missing required fields"
                    failed += 1
                    continue

                medallion = medallion_service.get_medallion(db, medallion_number=transaction.medallion_no)
                ledger_service.upsert_ledgers(db, {
                    "driver_id": transaction.driver_id,
                    "medallion_id": int(medallion.id),
                    "vehicle_id": int(transaction.vehicle_id),
                    "amount": transaction.amount,
                    "debit": True,
                    "description": f"EZPass toll posted on {transaction.transaction_date} for plate {transaction.plate_no}",
                    "source_type": LedgerSourceType.EZPASS,
                    "source_id": transaction.id
                })
                transaction_data["status"] = "Posted"
                transaction_data["posting_date"] = datetime.now(timezone.utc).date()
                posted += 1
            except Exception as e:
                transaction_data["status"] = "Posting Failed"
                transaction_data["post_failed_reason"] = str(e)
                failed += 1

            self.upsert_ezpass_transaction(db , transaction_data= {"id": transaction.id, **transaction_data})

        log_data["id"] = log.id
        log_data["success_count"] = posted
        log_data["unidentified_count"] = failed
        log_data["status"] = "Partial" if failed else "Success"
        self.upsert_ezpass_log(db, log_data)

        return {
            "message": "Posting to central ledger",
            "posted": posted,
            "failed": failed,
            "log_id": log.id
        }

ezpass_service = EZPassService()
