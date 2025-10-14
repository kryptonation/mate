# app/pvb/services.py

"""
Business logic layer for PVB (Parking Violations Bureau) operations.
Implements complete import, association, and posting logic.
"""

from datetime import datetime, timezone, date
from typing import List, Tuple, Optional, Dict, Any

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_db
from app.pvb.repository import PVBRepository
from app.pvb.schemas import (
    PVBViolationCreate, PVBViolationUpdate, PVBViolationFilters,
    PVBLogCreate, PVBLogUpdate, PVBLogFilters,
    PVBImportResult, PVBAssociationResult, PVBPostingResult,
)
from app.pvb.models import PVBViolation, PVBLog
from app.pvb.exceptions import (
    PVBViolationNotFoundException, PVBLogNotFoundException,
    PVBImportException, PVBAssociationException, PVBPostingException,
    PVBUpdateException, PVBDateParseException, PVBDuplicateSummonsException,
)
from app.vehicles.models import Vehicle, VehicleRegistration
from app.ledger.models import LedgerEntry, LedgerSourceType
from app.utils.logger import get_logger

logger = get_logger(__name__)

def get_pvb_repository(db: AsyncSession = Depends(get_async_db)) -> PVBRepository:
    """Dependency to get PVBRepository instance."""
    return PVBRepository(db)


class PVBService:
    """
    Business logic layer for PVB operations.
    Implements complete import, association, and posting worklfows.
    """

    def __init__(self, repo: PVBRepository = Depends(get_pvb_repository)):
        self.repo = repo
        logger.debug("PVBService initialized")

    # === Violation operations ===

    async def get_violation_by_id(self, violation_id: int) -> PVBViolation:
        """Get a single violation by ID."""
        logger.info("Getting violation by ID", violation_id=violation_id)

        violation = await self.repo.get_violation_by_id(violation_id)
        if not violation:
            logger.error("Violation not found", violation_id=violation_id)
            raise PVBViolationNotFoundException(violation_id)
        
        return violation
    
    async def get_violations(
        self,
        filters: PVBViolationFilters,
    ) -> Tuple[List[PVBViolation], int]:
        """Get violations with filters and pagination."""
        logger.info("Getting violations with filters", filters=filters.model_dump())

        violations, total_count = await self.repo.get_violations(filters)
        logger.info("Retrieved violations", count=len(violations), total=total_count)

        return violations, total_count

    async def create_violation(
        self,
        violation_data: PVBViolationCreate
    ) -> PVBViolation:
        """Create a new violation."""
        logger.info("Creating violation", data=violation_data.model_dump())

        # === Check for duplicate summons number ===
        if violation_data.summons_number:
            existing = await self.repo.get_violation_by_summons(violation_data.summons_number)
            if existing:
                logger.warning("Duplicate summons number", summons=violation_data.summons_number)
                raise PVBDuplicateSummonsException(violation_data.summons_number)
            
        try:
            violation = await self.repo.create_violation(violation_data)
            await self.repo.commit()
            logger.info("Violation created successfully", violation_id=violation.id)
            return violation
        except Exception as e:
            await self.repo.db.rollback()
            logger.error("Error creating violation", error=str(e), exc_info=True)
            raise PVBImportException(f"Failed to create violation: {str(e)}") from e

    async def update_violation(
        self,
        violation_id: int,
        update_data: PVBViolationUpdate
    ) -> PVBViolation:
        """Update an existing violation."""
        logger.info("Updating violation", violation_id=violation_id)

        violation = await self.get_violation_by_id(violation_id)

        try:
            # === Check for duplicate summons if being updated ===
            if update_data.summons_number and update_data.summons_number != violation.summons_number:
                existing = await self.repo.get_violation_by_summons(update_data.summons_number)
                if existing:
                    raise PVBDuplicateSummonsException(update_data.summons_number)
                
            updated_violation = await self.repo.update_violation(violation, update_data)
            await self.repo.db.commit()
            logger.info("Violation updated successfully", violation_id=violation_id)
            return updated_violation
        except PVBDuplicateSummonsException:
            await self.repo.db.rollback()
            raise
        except Exception as e:
            await self.repo.db.rollback()
            logger.error("Error updating violation", violation_id=violation_id, error=str(e))
            raise PVBUpdateException(violation_id, str(e)) from e
        
    async def delete_violation(self, violation_id: int) -> None:
        """Delete (archive) a violation."""
        logger.info("Deleting violation", violation_id=violation_id)

        violation = await self.get_violation_by_id(violation_id)

        try:
            await self.repo.delete_violation(violation)
            await self.repo.db.commit()
            logger.info("Violation deleted successfully", violation_id=violation_id)
        except Exception as e:
            await self.repo.db.rollback()
            logger.error("Error deleting violation", violation_id=violation_id, error=str(e))
            raise PVBUpdateException(violation_id, str(e)) from e
        
    # === Log operations ===

    async def get_log_by_id(self, log_id: int) -> PVBLog:
        """Get a single log by ID."""
        logger.info("Getting log by ID", log_id=log_id)

        log = await self.repo.get_log_by_id(log_id)
        if not log:
            logger.error("Log not found", log_id=log_id)
            raise PVBLogNotFoundException(log_id)
        
        return log

    async def get_logs(
        self,
        filters: PVBLogFilters
    ) -> Tuple[List[PVBLog], int]:
        """Get logs with filters and pagination."""
        logger.info("Getting logs with filters", filters=filters.model_dump())

        logs, total_count = await self.repo.get_logs(filters)
        logger.info("Retrieved logs", count=len(logs), total=total_count)

        return logs, total_count
    
    async def create_log(self, log_data: PVBLogCreate) -> PVBLog:
        """Create a new log."""
        logger.info("Creating log", data=log_data.model_dump())

        try:
            log = await self.repo.create_log(log_data)
            await self.repo.db.commit()
            logger.info("Log created successfully", log_id=log.id)
            return log
        except Exception as e:
            await self.repo.db.rollback()
            logger.error("Error creating log", error=str(e), exc_info=True)
            raise PVBImportException(f"Failed to create log: {str(e)}") from e

    # === Import Operations ===

    async def import_violations(
        self,
        rows: List[Dict[str, Any]]
    ) -> PVBImportResult:
        """
        Import PVB violations from CSV data.
        
        Args:
            rows: List of dictionaries containing violation data
            
        Returns:
            PVBImportResult with import statistics
        """
        logger.info("Starting PVB import", row_count=len(rows))

        imported, failed = 0, 0
        failed_rows = {}

        # === Create import log ===
        log_data = PVBLogCreate(
            log_date=datetime.now(timezone.utc),
            log_type="Import",
            records_impacted=len(rows),
            status="Pending"
        )

        try:
            log = await self.create_log(log_data)
        except Exception as e:
            logger.error("Failed to create import log", error=str(e))
            raise PVBImportException(f"Failed to create import log: {str(e)}") from e
        
        # === Process each row ===
        for idx, row in enumerate(rows):
            try:
                # === Parse and validate data ===
                violation_data = await self._parse_violation_data(row, log.id)

                # === Check for duplicates ===
                if violation_data.get("summons_number"):
                    existing = await self.repo.get_violation_by_summons(violation_data["summons_number"])
                    if existing:
                        logger.debug("Skipping duplicate summons", summons=violation_data["summons_number"])
                        failed += 1
                        failed_rows[row.get("SUMMONS", f"row_{idx}")] = "Duplicate summons number"
                        continue

                # Create violation
                violation_create = PVBViolationCreate(**violation_data)
                await self.repo.create_violation(violation_create)
                imported += 1

            except PVBDateParseException as e:
                failed += 1
                failed_rows[row.get("SUMMONS", f"row_{idx}")] = str(e.message)
                logger.warning("Date parsing error", row=idx, error=str(e))
            except Exception as e:
                failed += 1
                failed_rows[row.get("SUMMONS", f"row_{idx}")] = str(e)
                logger.warning("Error importing row", row=idx, error=str(e))

        # Update log with results
        log_update = PVBLogUpdate(
            success_count=imported,
            unidentified_count=failed,
            status="Success" if failed == 0 else ("Partial" if imported > 0 else "Failure")
        )

        try:
            await self.repo.update_log(log, log_update)
            await self.repo.db.commit()
        except Exception as e:
            await self.repo.db.rollback()
            logger.error("Failed to update log", error=str(e))

        logger.info(
            "Import completed",
            log_id=log.id,
            imported=imported,
            failed=failed
        )

        return PVBImportResult(
            success=failed < len(rows),
            log_id=log.id,
            records_impacted=len(rows),
            success_count=imported,
            unidentified_count=failed,
            message=f"Imported {imported} violations, {failed} failed",
            failed_rows=failed_rows if failed_rows else None
        )

    async def _parse_violation_data(
        self, 
        row: Dict[str, Any], 
        log_id: int
    ) -> Dict[str, Any]:
        """Parse and validate violation data from CSV row."""
        
        # Parse date
        issue_date = self._parse_date_flexibly(row.get("ISSUE DATE", ""))

        # Parse amount
        amount_due = 0
        try:
            amount_due_str = str(row.get("AMOUNT DUE", "0"))
            amount_due = int(float(amount_due_str))
        except (ValueError, TypeError):
            logger.warning("Invalid amount due", value=row.get("AMOUNT DUE"))

        return {
            "plate_number": row.get("PLATE", "UNKNOWN"),
            "state": row.get("STATE", "NY"),
            "vehicle_type": row.get("TYPE"),
            "summons_number": str(row.get("SUMMONS")) if row.get("SUMMONS") else None,
            "issue_date": issue_date,
            "issue_time": self._parse_time(row.get("ISSUE TIME")),
            "amount_due": amount_due,
            "status": "Imported",
            "log_id": log_id
        }

    def _parse_date_flexibly(self, date_str: str) -> date:
        """Parse date from multiple formats."""
        from datetime import datetime
        
        if not date_str:
            return datetime.now(timezone.utc).date()

        date_str = str(date_str).strip()
        formats = ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        logger.error("Failed to parse date", date_str=date_str)
        raise PVBDateParseException(date_str, formats)

    def _parse_time(self, time_str: Any) -> Optional[str]:
        """Parse time from various formats."""
        if not time_str:
            return None

        time_str = str(time_str).strip()
        
        # Handle common time formats
        if ":" in time_str:
            parts = time_str.split(":")
            if len(parts) >= 2:
                try:
                    hour = int(parts[0])
                    minute = int(parts[1])
                    # Convert to 24-hour format string
                    return f"{hour:02d}:{minute:02d}"
                except ValueError:
                    pass

        return time_str

    # === Association Operations ===

    async def associate_violations(self) -> PVBAssociationResult:
        """
        Associate imported violations with drivers, medallions, and vehicles.
        """
        logger.info("Starting PVB association")

        # Create association log
        log_data = PVBLogCreate(
            log_date=datetime.now(timezone.utc),
            log_type="Associate",
            status="Pending"
        )

        try:
            log = await self.create_log(log_data)
        except Exception as e:
            raise PVBAssociationException(f"Failed to create association log: {str(e)}") from e

        # Get imported violations
        filters = PVBViolationFilters(record_status="Imported", page=1, per_page=1000)
        violations, _ = await self.repo.get_violations(filters)

        associated_count = 0
        failed_count = 0
        details = []

        for violation in violations:
            try:
                # Attempt to associate with vehicle registration
                associations = await self._find_associations(violation)

                if associations:
                    update_data = PVBViolationUpdate(
                        driver_id=associations.get("driver_id"),
                        medallion_id=associations.get("medallion_id"),
                        vehicle_id=associations.get("vehicle_id"),
                        status="Associated"
                    )
                    await self.repo.update_violation(violation, update_data)
                    associated_count += 1
                else:
                    update_data = PVBViolationUpdate(
                        status="Failed",
                        associated_failed_reason="No matching vehicle registration found"
                    )
                    await self.repo.update_violation(violation, update_data)
                    failed_count += 1
                    details.append({
                        "violation_id": violation.id,
                        "plate_number": violation.plate_number,
                        "reason": "No matching vehicle registration"
                    })

            except Exception as e:
                failed_count += 1
                logger.error("Error associating violation", violation_id=violation.id, error=str(e))
                details.append({
                    "violation_id": violation.id,
                    "error": str(e)
                })

        # Update log
        log_update = PVBLogUpdate(
            records_impacted=len(violations),
            success_count=associated_count,
            unidentified_count=failed_count,
            status="Success" if failed_count == 0 else "Partial"
        )

        try:
            await self.repo.update_log(log, log_update)
            await self.repo.db.commit()
        except Exception as e:
            await self.repo.db.rollback()
            logger.error("Failed to update association log", error=str(e))

        logger.info(
            "Association completed",
            associated=associated_count,
            failed=failed_count
        )

        return PVBAssociationResult(
            success=True,
            total_processed=len(violations),
            associated_count=associated_count,
            failed_count=failed_count,
            message=f"Associated {associated_count} violations, {failed_count} failed",
            details=details if details else None
        )

    async def _find_associations(self, violation: PVBViolation) -> Optional[Dict[str, int]]:
        """Find driver, medallion, and vehicle associations for a violation."""
        
        # Find vehicle registration by plate number
        stmt = (
            select(VehicleRegistration)
            .where(VehicleRegistration.plate_number == violation.plate_number)
            .where(VehicleRegistration.is_active == True)
        )
        result = await self.repo.db.execute(stmt)
        registration = result.scalar_one_or_none()

        if not registration:
            return None

        # Get vehicle
        vehicle_stmt = select(Vehicle).where(Vehicle.id == registration.vehicle_id)
        vehicle_result = await self.repo.db.execute(vehicle_stmt)
        vehicle = vehicle_result.scalar_one_or_none()

        if not vehicle:
            return None

        # Get medallion and driver from vehicle
        associations = {
            "vehicle_id": vehicle.id,
            "medallion_id": vehicle.medallion_id,
            "driver_id": vehicle.driver_id
        }

        return associations

    # === Posting Operations ===

    async def post_violations(self) -> PVBPostingResult:
        """
        Post associated PVB violations to the ledger system.
        """
        logger.info("Starting PVB posting")

        # Create posting log
        log_data = PVBLogCreate(
            log_date=datetime.now(timezone.utc),
            log_type="Post",
            status="Pending"
        )

        try:
            log = await self.create_log(log_data)
        except Exception as e:
            raise PVBPostingException(f"Failed to create posting log: {str(e)}")

        # Get associated violations
        filters = PVBViolationFilters(record_status="Associated", page=1, per_page=1000)
        violations, _ = await self.repo.get_violations(filters)

        posted_count = 0
        failed_count = 0
        details = []

        for violation in violations:
            try:
                # Create ledger entry
                ledger_entry = LedgerEntry(
                    source_type=LedgerSourceType.PVB,
                    source_id=violation.id,
                    driver_id=violation.driver_id,
                    medallion_id=violation.medallion_id,
                    vehicle_id=violation.vehicle_id,
                    amount=violation.amount_due,
                    transaction_date=violation.issue_date,
                    description=f"PVB Violation - Summons: {violation.summons_number}",
                    status="Pending"
                )

                self.repo.db.add(ledger_entry)
                await self.repo.db.flush()

                # Update violation status
                update_data = PVBViolationUpdate(status="Posted")
                await self.repo.update_violation(violation, update_data)
                posted_count += 1

            except Exception as e:
                failed_count += 1
                logger.error("Error posting violation", violation_id=violation.id, error=str(e))
                
                # Update violation with failure reason
                update_data = PVBViolationUpdate(
                    status="Failed",
                    post_failed_reason=str(e)
                )
                await self.repo.update_violation(violation, update_data)
                
                details.append({
                    "violation_id": violation.id,
                    "error": str(e)
                })

        # Update log
        log_update = PVBLogUpdate(
            records_impacted=len(violations),
            success_count=posted_count,
            unidentified_count=failed_count,
            status="Success" if failed_count == 0 else "Partial"
        )

        try:
            await self.repo.update_log(log, log_update)
            await self.repo.db.commit()
        except Exception as e:
            await self.repo.db.rollback()
            logger.error("Failed to update posting log", error=str(e))

        logger.info(
            "Posting completed",
            posted=posted_count,
            failed=failed_count
        )

        return PVBPostingResult(
            success=True,
            total_processed=len(violations),
            posted_count=posted_count,
            failed_count=failed_count,
            message=f"Posted {posted_count} violations, {failed_count} failed",
            details=details if details else None
        )

