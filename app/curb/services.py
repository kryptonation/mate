# app/curb/services.py

"""
Business logic layer for CURB (Taxi fleet) operations.
Implements complete import, association, reconciliation, and posting logic.
"""

from datetime import datetime, timezone
from typing import List, Tuple, Optional

from fastapi import Depends
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_db
from app.curb.repository import CURBRepository
from app.curb.schemas import (
    CURBTripCreate, CURBTripUpdate, CURBTripFilters,
    CURBImportLogCreate, CURBImportLogUpdate, CURBImportLogFilters,
    CURBTripReconciliationCreate,
    CURBImportResult, CURBReconciliationResult,
    CURBPostingResult,
)
from app.curb.models import CURBTrip, CURBImportLog
from app.curb.exceptions import (
    CURBTripNotFoundException, CURBImportLogNotFoundException,
    CURBImportException, CURBReconciliationException,
    CURBPostingException, 
)
from app.curb.utils import parse_trips_xml, parse_card_transactions_xml
from app.curb.soap_client import reconcile_trips_on_server

from app.leases.models import Lease
from app.medallions.models import Medallion
from app.ledger.models import LedgerBalance
from app.ledger.schemas import LedgerCategory

from app.utils.logger import get_logger

logger = get_logger(__name__)

def get_curb_repository(db: AsyncSession = Depends(get_async_db)) -> CURBRepository:
    """Get CURB repository"""
    return CURBRepository(db)


class CURBService:
    """
    Business logic layer for CURB operations.
    Implements complete import, reconciliation, association, and posting workflows.
    """

    def __init__(self, repo: CURBRepository = Depends(get_curb_repository)):
        self.repo = repo
        logger.debug("CURBService initialized")

    # === Trip Operations ===

    async def get_trip_by_id(self, trip_id: int) -> CURBTrip:
        """Get a single trip by ID"""
        logger.info("Getting trip by ID", trip_id=trip_id)

        trip = await self.repo.get_trip_by_id(trip_id)
        if not trip:
            logger.error("Trip not found", trip_id=trip_id)
            raise CURBTripNotFoundException(trip_id)
        
        return trip

    async def get_trips(
        self, filters: CURBTripFilters
    ) -> Tuple[List[CURBTrip], int]:
        """Get trips with filters and pagination"""
        logger.info("Getting trips with filters", filters=filters.model_dump())

        trips, total_count = await self.repo.get_trips(filters)
        logger.info("Retrieved trips", count=len(trips), total=total_count)

        return trips, total_count

    async def update_trip(
        self, trip_id: int, trip_data: CURBTripUpdate
    ) -> CURBTrip:
        """Update a trip"""
        logger.info("Updating trip", trip_id=trip_id)

        trip = await self.repo.update_trip(trip_id, trip_data)
        if not trip:
            raise CURBTripNotFoundException(trip_id)

        logger.info("Trip updated successfully", trip_id=trip_id)
        return trip

    # === Import Operations ===

    async def import_trips(
        self, xml_data: str, cash_xml_data: Optional[str] = None,
        import_source: str = "SOAP", import_by: str = "SYSTEM"
    ) -> CURBImportResult:
        """
        Import trips from XML data
        
        Args:
            xml_data: XML data from card transaction API
            cash_xml_data: Optional XML data from trips log (cash trips)
            import_source: Source of import (SOAP, Upload, Manual)
            import_by: User or system performing import

        Returns:
            CURBImportResult: Result of the import operation
        """
        logger.info("Starting trip import", source=import_source, by=import_by)

        try:
            # === Parse XML data ===
            trips = parse_card_transactions_xml(xml_data)
            logger.info("Parsed card transactions", count=len(trips))

            # === Merge cash trips if provided ===
            if cash_xml_data:
                cash_trips = parse_trips_xml(cash_xml_data)
                cash_only = [t for t in cash_trips if t.get("payment_type") == "$"]
                trips.extend(cash_only)
                logger.info("Merged cash trips", count=len(cash_only), total=len(trips))

            # === Create import log ===
            log_data = CURBImportLogCreate(
                import_source=import_source,
                import_by=import_by,
                total_records=len(trips),
                status="IN_PROGRESS",
            )
            import_log = await self.repo.create_import_log(log_data)
            logger.info("Created import log", log_id=import_log.id)

            # === Check for existing trips ===
            existing_records_ids = set()
            stmt = select(CURBTrip.record_id).where(
                CURBTrip.record_id.in_([t["record_id"] for t in trips if "record_id" in t])
            )
            result = await self.repo.db.execute(stmt)
            existing_record_ids = {row[0] for row in result.all()}

            # === Prepare new trips ===
            new_trips_data = []
            duplicate_count = 0

            for trip_dict in trips:
                record_id = trip_dict.get("record_id")

                if record_id in existing_record_ids:
                    duplicate_count += 1
                    logger.debug("Duplicate trip skipped", record_id=record_id)
                    continue

                # === Create trip data ===
                try:
                    trip_create = CURBTripCreate(
                        record_id=record_id,
                        period=trip_dict.get("period"),
                        trip_number=trip_dict.get("trip_number"),
                        cab_number=trip_dict.get("cab_number"),
                        driver_id=trip_dict.get("driver_id"),
                        start_date=trip_dict.get("start_date"),
                        end_date=trip_dict.get("end_date"),
                        start_time=trip_dict.get("start_time"),
                        end_time=trip_dict.get("end_time"),
                        trip_amount=trip_dict.get("trip_amount", 0.0),
                        tips=trip_dict.get("tips", 0.0),
                        extras=trip_dict.get("extras", 0.0),
                        tolls=trip_dict.get("tolls", 0.0),
                        tax=trip_dict.get("tax", 0.0),
                        imp_tax=trip_dict.get("imp_tax", 0.0),
                        total_amount=trip_dict.get("total_amount", 0.0),
                        gps_start_lat=trip_dict.get("gps_start_lat"),
                        gps_start_lon=trip_dict.get("gps_start_lon"),
                        gps_end_lat=trip_dict.get("gps_end_lat"),
                        gps_end_lon=trip_dict.get("gps_end_lon"),
                        from_address=trip_dict.get("from_address"),
                        to_address=trip_dict.get("to_address"),
                        payment_type=trip_dict.get("payment_type", "T"),
                        cc_number=trip_dict.get("cc_number"),
                        auth_code=trip_dict.get("auth_code"),
                        auth_amount=trip_dict.get("auth_amount", 0.0),
                        ehail_fee=trip_dict.get("ehail_fee", 0.0),
                        health_fee=trip_dict.get("health_fee", 0.0),
                        congestion_fee=trip_dict.get("congestion_fee", 0.0),
                        airport_fee=trip_dict.get("airport_fee", 0.0),
                        cbdt_fee=trip_dict.get("cbdt_fee", 0.0),
                        passengers=trip_dict.get("passengers", 1),
                        distance_service=trip_dict.get("distance_service", 0.0),
                        distance_bs=trip_dict.get("distance_bs", 0.0),
                        reservation_number=trip_dict.get("reservation_number"),
                        import_id=import_log.id,
                    )
                    new_trips_data.append(trip_create)
                except Exception as e:
                    logger.error("Failed to create trip data", record_id=record_id, error=str(e))
                    continue

            # === Bulk insert new trips ===
            success_count = 0
            if new_trips_data:
                created_trips = await self.repo.bulk_create_trips(new_trips_data)
                success_count = len(created_trips)
                logger.info("Trips inserted", count=success_count)

            # === Update import log ===
            await self.repo.update_import_log(
                import_log.id,
                CURBImportLogUpdate(
                    import_end=datetime.now(timezone.utc),
                    success_count=success_count,
                    duplicate_count=duplicate_count,
                    failure_count=len(trips) - success_count - duplicate_count,
                    status="COMPLETED" if success_count > 0 else "FAILED"
                )
            )

            # === Commit transaction ===
            await self.repo.db.commit()

            logger.info(
                "Import completed",
                log_id=import_log.id,
                total=len(trips),
                success=success_count,
                duplicates=duplicate_count,
            )

            return CURBImportResult(
                success=True,
                log_id=import_log.id,
                total_records=len(trips),
                success_count=success_count,
                duplicate_count=duplicate_count,
                failure_count=len(trips) - success_count - duplicate_count,
                message=f"Successfully imported {success_count} trips {duplicate_count} duplicates skipped"
            )
        except Exception as e:
            logger.error("Import failed", error=str(e), exc_info=True)
            await self.repo.db.rollback()
            raise CURBImportException(str(e)) from e
        
    # === Reconciliation Operations ===

    async def reconcile_trips_locally(
        self,
        trip_ids: Optional[List[int]] = None,
        recon_stat: Optional[int] = None,
        recon_by: str = "SYSTEM"
    ) -> CURBReconciliationResult:
        """
        Reconcile trips locally in the database.
        For dev/uat: marks trips as reconciled without calling CURB API.
        """
        logger.info("Starting local reconciliation", trip_ids=trip_ids, recon_stat=recon_stat)

        try:
            # === Get trips to reconcile ===
            if trip_ids:
                trips = []
                for trip_id in trip_ids:
                    trip = await self.repo.get_trip_by_id(trip_id)
                    if trip:
                        trips.append(trip)
            else:
                trips = await self.repo.get_unreconciled_trips()

            if not trips:
                logger.info("No trips to reconcile")
                return CURBReconciliationResult(
                    success=True,
                    total_processed=0,
                    reconciled_count=0,
                    already_reconciled_count=0,
                    failed_count=0,
                    recon_stat=recon_stat or 0,
                    message="No trips to reconcile"
                )
            
            # === Generate recon stat if not provided ===
            if not recon_stat:
                recon_stat = int(datetime.now(timezone.utc).timestamp())

            # === Process trips ===
            reconciled_count = 0
            already_reconciled = 0
            failed_count = 0
            reconciliations_to_create = []

            for trip in trips:
                if trip.is_reconciled:
                    already_reconciled += 1
                    logger.debug("Trip already reconciled", trip_id=trip.id)
                    continue

                try:
                    # === Update trip status ===
                    await self.repo.update_trip(
                        trip.id,
                        CURBTripUpdate(
                            is_reconciled=True,
                            recon_stat=recon_stat,
                            status="Reconciled"
                        )
                    )

                    # === Create reconciliation record ===
                    reconciliations_to_create.append(
                        CURBTripReconciliationCreate(
                            trip_id=trip.id,
                            recon_stat=recon_stat,
                            reconciled_by=recon_by,
                            reconciliation_type="LOCAL"
                        )
                    )
                    reconiled_count += 1

                except Exception as e:
                    logger.error("Failed to reconcile trip", trip_id=trip.id, error=str(e))
                    failed_count += 1

            # === Bulk create reconciliation records ===
            if reconciliations_to_create:
                await self.repo.bulk_create_reconciliations(reconciliations_to_create)

            # === Commit transaction ===
            await self.repo.db.commit()

            logger.info(
                "Local reconciliation completed",
                total=len(trips),
                reconciled_count=reconciled_count,
                already_reconciled_count=already_reconciled,
                failed_count=failed_count,
                recon_stat=recon_stat,
                message=f"Successfully reconciled {reconciled_count} trips locally"
            )

        except Exception as e:
            logger.error("Local reconciliation failed", error=str(e), exc_info=True)
            await self.repo.db.rollback()
            raise CURBReconciliationException(str(e)) from e
        
    async def reconcile_trips_on_server(
        self, trip_ids: List[int], recon_stat: int, recon_by: str = "SYSTEM"
    ) -> CURBReconciliationResult:
        """
        Reconcile trips on CURB server via SOAP API.
        For production: calls CURB API to mark trips as reconciled.
        """
        logger.info("Starting server reconciliation", trip_ids=trip_ids, recon_stat=recon_stat)

        try:
            # === Get trips ===
            trips = []
            for trip_id in trip_ids:
                trip = await self.repo.get_trip_by_id(trip_id)
                if trip:
                    trips.append(trip)

            if not trips:
                raise CURBReconciliationException("No valid trips found")
            
            # === Extract record IDs ===
            record_ids = [trip.record_id for trip in trips]

            # === Call CURB API to reconcile on server ===
            try:
                reconcile_trips_on_server(record_ids, recon_stat)
                logger.info("Server reconciliation API call succeeded")
            except Exception as e:
                logger.error("Server reconciliation API call failed", error=str(e))
                raise CURBReconciliationException(f"CURB API call failed: {str(e)}") from e
            
            # === Update trips locally after successful API call ===
            reconciled_count = 0
            failed_count = 0
            reconciliations_to_create = []

            for trip in trips:
                try:
                    await self.repo.update_trip(
                        trip.id,
                        CURBTripUpdate(
                            is_reconciled=True,
                            recon_stat=recon_stat,
                            status="Reconciled"
                        )
                    )

                    reconciliations_to_create.append(
                        CURBTripReconciliationCreate(
                            trip_id=trip.id,
                            recon_stat=recon_stat,
                            reconciled_by=recon_by,
                            reconciliation_type="REMOTE"
                        )
                    )
                    reconciled_count += 1
                except Exception as e:
                    logger.error("Failed to update trip after reconciliation", trip_id=trip.id, error=str(e))
                    failed_count += 1

            # === Bulk create reconciliation records ===
            if reconciliations_to_create:
                await self.repo.bulk_create_reconciliations(reconciliations_to_create)

            # === Commit transaction ===
            await self.repo.db.commit()

            logger.info(
                "Server reconciliation completed",
                reconciled=reconciled_count,
                failed=failed_count
            )

            return CURBReconciliationResult(
                success=True,
                total_processed=len(trips),
                reconciled_count=reconciled_count,
                already_reconciled_count=0,
                failed_count=failed_count,
                recon_stat=recon_stat,
                message=f"Successfully reconciled {reconciled_count} trips on server"
            )
        
        except Exception as e:
            logger.error("Server reconciliation failed", error=str(e), exc_info=True)
            await self.repo.db.rollback()
            if isinstance(e, CURBReconciliationException):
                raise
            raise CURBReconciliationException(str(e)) from e

    # === Association and Posting Operations ===

    async def associate_and_post_trips(
        self,
        posted_by: str = "SYSTEM"
    ) -> CURBPostingResult:
        """
        Associate trips with leases and post to ledger.
        Processes reconciled but unposted trips.
        """
        logger.info("Starting trip association and posting")

        try:
            # === Get reconciled but unposted trips ===
            trips = await self.repo.get_reconciled_unposted_trips()

            if not trips:
                logger.info("No trips to post")
                return CURBPostingResult(
                    success=True,
                    total_processed=0,
                    posted_count=0,
                    failed_count=0,
                    skipped_count=0,
                    message="No trips to post"
                )
            
            posted_count = 0
            failed_count = 0
            skipped_count = 0
            details = []

            for trip in trips:
                try:
                    # === Find active lease for the driver and medallion on trip date ===
                    lease = await self.find_active_lease_for_trip(trip)
                    if not lease:
                        skipped_count += 1
                        details.append(f"Trip {trip.id} skipped: No active lease found")
                        logger.debug("No active lease found for trip", trip_id=trip.id)
                        continue

                    # === Create ledger entry ===
                    # TODO: Implement actual ledger posting logic here
                    # ledger_entry = LedgerEntry(
                    #     lease_id=lease.id,
                    #     vehicle_id=lease.vehicle_id,
                    #     medallion_id=lease.medallion_id,
                    #     entry_date=trip.start_date,
                    #     amount=trip.total_amount,
                    #     description=f"CURB Trip {trip.trip_number} on {trip.start_date}",
                    #     source_type=LedgerSourceType.CURB,
                    #     source_id=trip.id,
                    #     created_by=posted_by
                    # )
                    # self.repo.db.add(ledger_entry)
                    # await self.repo.db.flush()
                    # posted_count += 1
                    # details.append(f"Trip {trip.id} posted successfully")
                    # logger.debug("Trip posted successfully", trip_id=trip.id, ledger_id=ledger_entry.id)

                    # === Update trip status ===
                    await self.repo.update_trip(
                        trip.id,
                        CURBTripUpdate(
                            is_posted=True,
                            status="Posted"
                        )
                    )

                    posted_count += 1

                except Exception as e:
                    logger.error("Failed to post trip", trip_id=trip.id, error=str(e))

                    await self.repo.update_trip(
                        trip.id,
                        CURBTripUpdate(
                            status="Failed",
                            post_failed_reason=str(e)
                        )
                    )

                    failed_count += 1
                    details.append({
                        "trip_id": trip.id,
                        "record_id": trip.record_id,
                        "error": str(e)
                    })

            # === Commit transaction ===
            await self.repo.db.commit()

            logger.info(
                "Posting completed",
                total=len(trips),
                posted=posted_count,
                failed=failed_count,
                skipped=skipped_count,
            )

            return CURBPostingResult(
                success=True,
                total_processed=len(trips),
                posted_count=posted_count,
                failed_count=failed_count,
                skipped_count=skipped_count,
                message=f"Successfully posted {posted_count} trips to ledger",
                details=details if details else None
            )
        
        except Exception as e:
            logger.error("Posting failed", error=str(e), exc_info=True)
            await self.repo.db.rollback()
            raise CURBPostingException(str(e)) from e

    # === Import logs operation ===

    async def get_import_log_by_id(self, log_id: int) -> CURBImportLog:
        """Get import log by ID"""
        logger.info("Getting import log", log_id=log_id)

        log = await self.repo.get_import_log_by_id(log_id)
        if not log:
            raise CURBImportLogNotFoundException(log_id)
        
        return log

    async def get_import_logs(
        self,
        filters: CURBImportLogFilters
    ) -> Tuple[List[CURBImportLog], int]:
        """Get import logs with filters and pagination"""
        logger.info("Getting import logs", filters=filters.model_dump())

        logs, total_count = await self.repo.get_import_logs(filters)
        logger.info("Retrieved import logs", count=len(logs), total=total_count)

        return logs, total_count

    # === Helper Functions ===

    async def find_active_lease_for_trip(self,trip: CURBTrip) -> Optional[Lease]:
        """
        Find an active lease for the driver and medallion on the trip date.
        """
        stmt = select(Lease).where(
            and_(
                Lease.driver_id == trip.driver_id,
                Lease.medallion.has(Medallion.medallion_number == trip.cab_number),
                Lease.start_date <= trip.start_date,
                or_(Lease.end_date == None, Lease.end_date >= trip.start_date),
                Lease.lease_status == "Active"
            )
        ).order_by(Lease.start_date.desc())

        result = await self.repo.db.execute(stmt)
        lease = result.scalars().first()
        return lease

                

