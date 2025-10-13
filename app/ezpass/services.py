# app/ezpass/services.py

"""
Enhanced business logic layer for EZPass operations with complete association and posting logic.
"""

from datetime import datetime, timezone, date
from typing import List, Tuple, Optional, Dict, Any

from fastapi import Depends
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.db import get_async_db
from app.ezpass.repository import EZPassRepository
from app.ezpass.schemas import (
    EZPassTransactionCreate, EZPassTransactionUpdate, EZPassTransactionFilters,
    EZPassLogCreate, EZPassLogFilters, EZPassImportResult,
    EZPassAssociationResult, EZPassPostingResult,
)
from app.ezpass.models import EZPassTransaction, EZPassLog
from app.ezpass.exceptions import (
    EZPassTransactionNotFoundException, EZPassLogNotFoundException,
    EZPassImportException, EZPassAssociationException, EZPassPostingException,
    EZPassUpdateException,
)
from app.ezpass.utils import clean_plate_number

from app.leases.models import Lease
from app.vehicles.models import Vehicle, VehicleRegistration
from app.medallions.models import Medallion
from app.ledger.models import LedgerEntry, LedgerSourceType

from app.utils.logger import get_logger

logger = get_logger(__name__)


def get_ezpass_repository(db: AsyncSession = Depends(get_async_db)) -> EZPassRepository:
    """Dependency to get EZPassRepository instance."""
    return EZPassRepository(db)


class EZPassService:
    """
    Enhanced business logic layer for EZPass operations.
    Implements complete association and posting logic.
    """

    def __init__(self, repo: EZPassRepository = Depends(get_ezpass_repository)):
        self.repo = repo
        logger.debug("EZPassService initialized")

    async def get_transaction_by_id(self, transaction_id: int) -> EZPassTransaction:
        """Get a single transaction by ID."""
        logger.info("Getting transaction by ID", transaction_id=transaction_id)

        transaction = await self.repo.get_transaction_by_id(transaction_id)
        if not transaction:
            logger.error("Transaction not found", transaction_id=transaction_id)
            raise EZPassTransactionNotFoundException(transaction_id)
        
        return transaction
    
    async def get_transactions(
        self,
        filters: EZPassTransactionFilters,
    ) -> Tuple[List[EZPassTransaction], int]:
        """Get transactions with filters and pagination."""
        logger.info("Getting transactions with filters", filters=filters.model_dump())

        try:
            transactions, total_count = await self.repo.get_transactions(filters)
            logger.info(
                "Transactions retrieved successfully",
                count=len(transactions),
                total_count=total_count,
            )
            return transactions, total_count
        except Exception as e:
            logger.error("Error getting transactions", error=str(e), exc_info=True)
            raise

    async def create_transaction(
        self,
        transaction_data: EZPassTransactionCreate,
    ) -> EZPassTransaction:
        """Create a new transaction."""
        logger.info("Creating new transaction", data=transaction_data.model_dump())

        try:
            transaction = await self.repo.create_transaction(transaction_data)
            logger.info("Transaction created successfully", transaction_id=transaction.id)
            return transaction
        except Exception as e:
            logger.error("Error creating transaction", error=str(e), exc_info=True)
            raise EZPassImportException(str(e)) from e

    async def update_transaction(
        self,
        transaction_id: int,
        update_data: EZPassTransactionUpdate,
    ) -> EZPassTransaction:
        """Update an existing transaction."""
        logger.info(
            "Updating transaction",
            transaction_id=transaction_id,
            data=update_data.model_dump(exclude_unset=True)
        )

        try:
            transaction = await self.get_transaction_by_id(transaction_id)
            updated_transaction = await self.repo.update_transaction(transaction, update_data)
            logger.info("Transaction updated successfully", transaction_id=transaction_id)
            return updated_transaction
        except EZPassTransactionNotFoundException:
            raise
        except Exception as e:
            logger.error(
                "Error updating transaction",
                transaction_id=transaction_id,
                error=str(e),
                exc_info=True
            )
            raise EZPassUpdateException(transaction_id, str(e)) from e
        
    async def process_ezpass_data(
        self,
        rows: List[dict],
        log_type: str = "Import"
    ) -> EZPassImportResult:
        """
        Process and Import EZPass data from file.
        """
        logger.info("Processing EZPass data", rows_count=len(rows), log_type=log_type)

        try:
            # Create log entry
            log_data = EZPassLogCreate(
                log_date=datetime.now(timezone.utc),
                log_type=log_type,
                records_impacted=len(rows),
                success_count=0,
                unidentified_count=0,
                status="Processing",
            )
            log = await self.repo.create_log(log_data)
            logger.info("Import log created", log_id=log.id)

            # === Process transactions ===
            transactions_data = []
            success_count = 0
            unidentified_count = 0

            for row in rows:
                try:
                    # === Clean and prepare data ===
                    transaction_data = EZPassTransactionCreate(
                        transaction_id=str(row.get("transaction_id", "")),
                        transaction_date=row.get("transaction_date"),
                        transaction_time=row.get("transaction_time"),
                        plate_no=row.get("plate_no"),
                        tag_or_plate=row.get("tag_or_plate") or row.get("plate_no", ""),
                        agency=row.get("agency"),
                        entry_plaza=row.get("entry_plaza"),
                        exit_plaza=row.get("exit_plaza"),
                        amount=float(row.get("amount", 0)),
                        status="Imported",
                        log_id=log.id,
                    )
                    transactions_data.append(transaction_data)
                    success_count += 1
                except Exception as e:
                    logger.warning("Failed to process row", row=row, error=str(e))
                    unidentified_count += 1

            # === Bulk create transactions ===
            if transactions_data:
                await self.repo.bulk_create_transactions(transactions_data)
                logger.info("Transactions imported successfully", count=len(transactions_data))

            # === Update log ===
            await self.repo.update_log(
                log,
                success_count=success_count,
                unidentified_count=unidentified_count,
                status="Success" if unidentified_count == 0 else "Partial"
            )

            result = EZPassImportResult(
                success=True,
                log_id=log.id,
                records_impacted=len(rows),
                success_count=success_count,
                unidentified_count=unidentified_count,
                message=f"Successfully imported {success_count} records, {unidentified_count} failed"
            )

            logger.info("EZPass data processing completed", result=result.model_dump())
            return result

        except Exception as e:
            logger.error("Error processing EZPass data", error=str(e), exc_info=True)
            raise EZPassImportException(str(e)) from e
        
    async def associate_transactions(self) -> EZPassAssociationResult:
        """
        Associate imported transactions with vehicles, drivers, and medallions.

        Logic:
        1. Get all unassociated transactions (status='Imported')
        2. For each transaction, find active lease by plate number
        3. Get vehicle, driver, and medallion from the lease
        4. Update transaction with associations
        5. Mark as 'Associated' or 'Failed'
        """
        logger.info("Starting transaction association process")

        try:
            # === Get unassociated transactions ===
            transactions = await self.repo.get_unassociated_transactions()
            logger.info("Found unassociated transactions", count=len(transactions))

            if not transactions:
                return EZPassAssociationResult(
                    success=True,
                    total_transactions=0,
                    associated_count=0,
                    failed_count=0,
                    message="No unassociated transactions found"
                )
            
            associated_count = 0
            failed_count = 0
            db = self.repo.db

            for transaction in transactions:
                try:
                    logger.debug(
                        "Processing transaction for association",
                        transaction_id=transaction.id,
                        plate_no=transaction.plate_no
                    )

                    # === Find active lease by plate number ===
                    lease_data = await self._find_active_lease_by_plate(
                        db, transaction.plate_no, transaction.transaction_date
                    )

                    if not lease_data:
                        logger.warning(
                            "No active lease found for transaction",
                            transaction_id=transaction.id,
                            plate_no=transaction.plate_no
                        )

                        update_data = EZPassTransactionUpdate(
                            status="Failed",
                            associate_failed_reason=f"No active lease found for plate: {transaction.plate_no}"
                        )
                        await self.repo.update_transaction(transaction, update_data)
                        failed_count += 1
                        continue

                    # === Update transaction with associations ===
                    update_data = EZPassTransactionUpdate(
                        status="Associated",
                        driver_id=lease_data.get("driver_id"),
                        vehicle_id=lease_data.get("vehicle_id"),
                        medallion_no=lease_data.get("medallion_no"),
                        associate_failed_reason=None
                    ),

                    await self.repo.update_transaction(transaction, update_data)
                    associated_count += 1

                    logger.info(
                        "Transaction associated successfully",
                        transaction_id=transaction.id,
                        lease_id=lease_data.get("lease_id"),
                        driver_id=lease_data.get("driver_id"),
                        vehicle_id=lease_data.get("vehicle_id")
                    )
                except Exception as e:
                    logger.error(
                        "Failed to associate transaction",
                        transaction_id=transaction.id,
                        error=str(e),
                        exc_info=True
                    )
                    update_data = EZPassTransactionUpdate(
                        status="Failed",
                        associate_failed_reason=f"Association error: {str(e)}"
                    )
                    await self.repo.update_transaction(transaction, update_data)
                    failed_count += 1

            # === Create association log ===
            log_data = EZPassLogCreate(
                log_date=datetime.now(timezone.utc),
                log_type="Associate",
                records_impacted=len(transactions),
                success_count=associated_count,
                unidentified_count=failed_count,
                status="Success" if failed_count == 0 else "Partial"
            )
            await self.repo.create_log(log_data)

            result = EZPassAssociationResult(
                success=True,
                total_processed=len(transactions),
                associated_count=associated_count,
                failed_count=failed_count,
                message=f"Associated {associated_count} transactions, {failed_count} failed"
            )

            logger.info("Transaction association completed", result=result.model_dump())
            return result

        except Exception as e:
            logger.error("Error associating transactions", error=str(e), exc_info=True)
            raise EZPassAssociationException(str(e)) from e
        
    async def post_transactions_to_ledger(self) -> EZPassPostingResult:
        """
        Post associated transactions to the central ledger.
        
        Logic:
        1. Get all unposted transactions (status='Associated')
        2. For each transaction, create ledger entry
        3. Mark transaction as 'Posted' with posting_date
        4. Handle errors and mark as 'Failed' if posting fails
        """
        logger.info("Starting transaction posting to ledger")

        try:
            # === Get unposted transactions ===
            transactions = await self.repo.get_unposted_transactions()
            logger.info("Found unposted transactions", count=len(transactions))

            if not transactions:
                return EZPassPostingResult(
                    success=True,
                    total_processed=0,
                    posted_count=0,
                    failed_count=0,
                    message="No transactions to post"
                )
            
            posted_count = 0
            failed_count = 0
            db = self.repo.db

            for transaction in transactions:
                try:
                    logger.debug(
                        "Processing transaction for posting",
                        transaction_id=transaction.id,
                        driver_id=transaction.driver_id,
                        vehicle_id=transaction.vehicle_id
                    )

                    # === Get full lease details for posting ===
                    lease_data = await self._get_lease_for_transaction(db, transaction)

                    if not lease_data:
                        logger.warning(
                            "No lease data found for posting",
                            transaction_id=transaction.id
                        )
                        update_data = EZPassTransactionUpdate(
                            status="Failed",
                            post_failed_reason="No lease data found for posting"
                        )
                        await self.repo.update_transaction(transaction, update_data)
                        failed_count += 1
                        continue

                    # === Create ledger entry ===
                    ledger_entry = await self._create_ledger_entry(
                        db, transaction, lease_data
                    )

                    if ledger_entry:
                        # === Update transaction as posted ===
                        update_data = EZPassTransactionUpdate(
                            status="Posted",
                            posting_date=datetime.now(timezone.utc).date(),
                            post_failed_reason=None
                        )
                        await self.repo.update_transaction(transaction, update_data)
                        posted_count += 1

                        logger.info(
                            "Transaction posted successfully",
                            transaction_id=transaction.id,
                            ledger_id=ledger_entry.id
                        )
                    else:
                        update_data = EZPassTransactionUpdate(
                            status="Failed",
                            post_failed_reason="Failed to create ledger entry"
                        )
                        await self.repo.update_transaction(transaction, update_data)
                        failed_count += 1

                except Exception as e:
                    logger.error(
                        "Failed to post transaction",
                        transaction_id=transaction.id,
                        error=str(e),
                        exc_info=True
                    )
                    update_data = EZPassTransactionUpdate(
                        status="Failed",
                        post_failed_reason=f"Posting error: {str(e)}"
                    )
                    await self.repo.update_transaction(transaction, update_data)
                    failed_count += 1

            # === Create posting log ===
            log_data = EZPassLogCreate(
                log_date=datetime.now(timezone.utc),
                log_type="Post",
                records_impacted=len(transactions),
                success_count=posted_count,
                unidentified_count=failed_count,
                status="Success" if failed_count == 0 else "Partial"
            )
            await self.repo.create_log(log_data)

            result = EZPassPostingResult(
                success=True,
                total_processed=len(transactions),
                posted_count=posted_count,
                failed_count=failed_count,
                message=f"Posted {posted_count} transactions, {failed_count} failed"
            )

            logger.info("Transaction posting completed", result=result.model_dump())
            return result

        except Exception as e:
            logger.error("Error posting transactions to ledger", error=str(e), exc_info=True)
            raise EZPassPostingException(str(e)) from e
        
    # === Helper Methods ===

    async def _find_active_lease_by_plate(
        self,
        db: AsyncSession,
        plate_no: str,
        transaction_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        Find active lease for a vehicle by plate number on the transaction date.

        Returns dictionary with lease_id, driver_id, vehicle_id, medallion_no
        """
        if not plate_no:
            return None
        
        # === Clean plate number for matching ===
        cleaned_plate = clean_plate_number(plate_no)

        logger.debug(
            "Searching for active lease",
            plate_no=plate_no,
            cleaned_plate=cleaned_plate,
            transaction_date=transaction_date
        )

        try:
            # === Query to find vehicle by plate number (current or historical registration) ===
            vehicle_stmt = select(Vehicle).join(
                VehicleRegistration,
                Vehicle.id == VehicleRegistration.vehicle_id
            ).where(
                or_(
                    VehicleRegistration.plate_number.like(f"{plate_no}%"),
                    VehicleRegistration.plate_number.like(f"{cleaned_plate}%")
                )
            )

            vehicle_result = await db.execute(vehicle_stmt)
            vehicle = vehicle_result.scalar_one_or_none()
            

            if not vehicle:
                logger.debug("No vehicle found for plate number", plate_no=plate_no)
                return None
            
            logger.debug("Vehicle found", vehicle_id=vehicle.id, plate_no=plate_no)

            # === Find active lease for this vehicle on the transaction date ===
            lease_stmt = select(Lease).options(
                selectinload(Lease.lease_driver)
            ).where(
                and_(
                    Lease.vehicle_id == vehicle.id,
                    Lease.lease_start_date <= transaction_date,
                    or_(
                        Lease.lease_end_date >= transaction_date,
                        Lease.lease_end_date.is_(None)
                    ),
                    Lease.lease_status == "Active"
                )
            ).order_by(Lease.lease_start_date.desc())

            lease_result = await db.execute(lease_stmt)
            lease = lease_result.scalar_one_or_none()

            if not lease:
                logger.debug(
                    "No active lease found for vehicle",
                    vehicle_id=vehicle.id,
                    transaction_date=transaction_date,
                )
                return None

            # === Get primary driver from lease ===
            driver_id = None
            if lease.lease_driver:
                # === Get the primary driver or the first driver ===
                primary_driver = next(
                    (ld for ld in lease.lease_driver if ld.col_lease_seq == 1),
                    lease.lease_driver[0] if lease.lease_driver else None
                )
                if primary_driver:
                    driver_id = primary_driver.driver_id

            # === Get medallion number ===
            medallion_no = None
            if lease.medallion_id:
                medallion_stmt = select(Medallion.medallion_number).where(
                    Medallion.id == lease.medallion_id
                )
                medallion_result = await db.execute(medallion_stmt)
                medallion_no = medallion_result.scalar_one_or_none()

            result = {
                "lease_id": lease.id,
                "driver_id": driver_id,
                "vehicle_id": vehicle.id,
                "medallion_no": medallion_no,
                "medallion_id": lease.medallion_id,
            }

            logger.info(
                "Active lease found",
                lease_id=lease.id,
                vehicle_id=vehicle.id,
                driver_id=driver_id,
                medallion_no=medallion_no
            )
            return result

        except Exception as e:
            logger.error(
                "Error finding active lease",
                plate_no=plate_no,
                error=str(e),
                exc_info=True
            )
            return None
        
    async def _get_lease_for_transaction(
        self,
        db: AsyncSession,
        transaction: EZPassTransaction
    ) -> Optional[Dict[str, Any]]:
        """Get full lease details for a transaction."""
        if not transaction.vehicle_id:
            return None

        try:
            # === Get lease with all related data ===
            lease_stmt = select(Lease).options(
                selectinload(Lease.lease_driver),
                selectinload(Lease.vehicle),
                selectinload(Lease.medallion)
            ).where(
                and_(
                    Lease.vehicle_id == transaction.vehicle_id,
                    Lease.lease_start_date <= transaction.transaction_date,
                    or_(
                        Lease.lease_end_date >= transaction.transaction_date,
                        Lease.lease_end_date.is_(None)
                    ),
                    Lease.lease_status == "Active"
                )
            ).order_by(Lease.lease_start_date.desc())

            lease_result = await db.execute(lease_stmt)
            lease = lease_result.scalar_one_or_none()

            if not lease:
                return None
            
            return {
                "lease_id": lease.id,
                "driver_id": transaction.driver_id,
                "vehicle_id": lease.vehicle_id,
                "medallion_id": lease.medallion_id,
                "medallion_no": transaction.medallion_no,
                "lease": lease,
            }
        
        except Exception as e:
            logger.error(
                "Error getting lease for transaction",
                transaction_id=transaction.id,
                error=str(e)
            )
            return None
        
    async def _create_ledger_entry(
        self,
        db: AsyncSession,
        transaction: EZPassTransaction,
        lease_data: Dict[str, Any],
    ) -> Optional[LedgerEntry]:
        """
        Create ledger entry for EZPass transaction

        This creates a debit entry for the driver/lease.
        """
        try:
            # === Create ledger entry ===
            ledger_entry = LedgerEntry(
                transaction_date=transaction.transaction_date,
                posting_date=datetime.now(timezone.utc).date(),
                amount=transaction.amount,
                transaction_type="Debit",
                description=f"EZPass - {transaction.agency or 'Toll'} - {transaction.plate_no}",
                reference_number=transaction.transaction_id,
                source_type=LedgerSourceType.EZPASS,
                source_id=transaction.id,
                driver_id=transaction.driver_id,
                vehicle_id=transaction.vehicle_id,
                lease_id=lease_data.get("lease_id"),
                medallion_id=lease_data.get("medallion_id"),
                status="Posted",
                notes=f"Entry: {transaction.entry_plaza}, Exit: {transaction.exit_plaza}",
            )

            db.add(ledger_entry)
            await db.flush()
            await db.refresh(ledger_entry)

            logger.info(
                "Ledger entry created",
                ledger_id=ledger_entry.id,
                transaction_id=transaction.id,
                amount=transaction.amount
            )

            return ledger_entry

        except Exception as e:
            logger.error(
                "Error creating ledger entry",
                transaction_id=transaction.id,
                error=str(e),
                exc_info=True
            )
            return None
        
    # === Log operations ===

    async def get_log_by_id(self, log_id: int) -> EZPassLog:
        """Get a single log by ID."""
        logger.info("Getting log by ID", log_id=log_id)

        log = await self.repo.get_log_by_id(log_id)
        if not log:
            logger.error("Log not found", log_id=log_id)
            raise EZPassLogNotFoundException(log_id)
        
        return log

    async def get_logs(
        self,
        filters: EZPassLogFilters
    ) -> Tuple[List[EZPassLog], int]:
        """Get logs with filters and pagination."""
        logger.info("Getting logs with filters", filters=filters.model_dump())

        try:
            logs, total_count = await self.repo.get_logs(filters)
            logger.info(
                "Logs retrieved successfully",
                count=len(logs),
                total_count=total_count,
            )
            return logs, total_count
        except Exception as e:
            logger.error("Error getting logs", error=str(e), exc_info=True)
            raise


    

                

    

