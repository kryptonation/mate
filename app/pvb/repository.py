# app/pvb/repository.py

"""
Data Access Layer for PVB module using async SQLAlchemy 2.x
"""

from typing import List, Optional, Tuple

from sqlalchemy import select, func, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.pvb.models import PVBViolation, PVBLog
from app.pvb.schemas import (
    PVBViolationCreate, PVBViolationUpdate, PVBViolationFilters,
    PVBLogCreate, PVBLogUpdate, PVBLogFilters,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PVBRepository:
    """
    Data Access Layer for PVB operations.
    Handles all database interactions using async SQLAlchemy 2.x
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        logger.debug("PVBRepository initialized", session_id=id(db))

    # === Violation Operations ===

    async def get_violation_by_id(self, violation_id: int) -> Optional[PVBViolation]:
        """Fetch a violation by ID"""
        logger.debug("Fetching violation by ID", violation_id=violation_id)

        stmt = select(PVBViolation).where(PVBViolation.id == violation_id)
        result = await self.db.execute(stmt)
        violation = result.scalar_one_or_none()

        if violation:
            logger.info("Violation found", violation_id=violation_id)
        else:
            logger.warning("Violation not found", violation_id=violation_id)

        return violation
    
    async def get_violation_by_summons(self, summons_number: str) -> Optional[PVBViolation]:
        """Fetch a violation by summons number"""
        logger.debug("Fetching violation by summons", summons_number=summons_number)

        stmt = select(PVBViolation).where(PVBViolation.summons_number == summons_number)
        result = await self.db.execute(stmt)
        violation = result.scalar_one_or_none()

        if violation:
            logger.info("Violation found by summons", summons_number=summons_number)
        else:
            logger.debug("Violation not found by summons", summons_number=summons_number)

        return violation
    
    async def get_violations(
        self,
        filters: PVBViolationFilters,
    ) -> Tuple[List[PVBViolation], int]:
        """
        Fetch violations with filters, pagination, and sorting.
        Returns tuple of (violations list, total count).
        """
        logger.debug("Fetching violations with filters", filters=filters.model_dump())

        # === Base query ===
        stmt = select(PVBViolation).where(PVBViolation.is_archived == False)
        count_stmt = select(func.count(PVBViolation.id)).where(PVBViolation.is_archived == False)

        # === Apply Filters ===
        if filters.violation_id:
            stmt = stmt.where(PVBViolation.id == filters.violation_id)
            count_stmt = count_stmt.where(PVBViolation.id == filters.violation_id)

        if filters.plate_number:
            plate_numbers = [p.strip() for p in filters.plate_number.split(",") if p.strip()]
            stmt = stmt.where(
                or_(*[PVBViolation.plate_number.ilike(f"%{plate}%") for plate in plate_numbers])
            )
            count_stmt = count_stmt.where(
                or_(*[PVBViolation.plate_number.ilike(f"%{plate}%") for plate in plate_numbers])
            )

        if filters.summons_number:
            summons_numbers = [s.strip() for s in filters.summons_number.split(",") if s.strip()]
            stmt = stmt.where(
                or_(*[PVBViolation.summons_number.ilike(f"%{summons}%") for summons in summons_numbers])
            )
            count_stmt = count_stmt.where(
                or_(*[PVBViolation.summons_number.ilike(f"%{summons}%") for summons in summons_numbers])
            )

        if filters.state:
            states = [s.strip() for s in filters.state.split(",") if s.strip()]
            stmt = stmt.where(PVBViolation.state.in_(states))
            count_stmt = count_stmt.where(PVBViolation.state.in_(states))

        if filters.vehicle_type:
            types = [t.strip() for t in filters.vehicle_type.split(",") if t.strip()]
            stmt = stmt.where(PVBViolation.vehicle_type.in_(types))
            count_stmt = count_stmt.where(PVBViolation.vehicle_type.in_(types))

        if filters.record_status:
            statuses = [s.strip() for s in filters.record_status.split(",") if s.strip()]
            stmt = stmt.where(PVBViolation.status.in_(statuses))
            count_stmt = count_stmt.where(PVBViolation.status.in_(statuses))

        if filters.vehicle_id:
            vehicle_ids = [int(v) for v in filters.vehicle_id.split(",") if v.strip().isdigit()]
            stmt = stmt.where(PVBViolation.vehicle_id.in_(vehicle_ids))
            count_stmt = count_stmt.where(PVBViolation.vehicle_id.in_(vehicle_ids))

        if filters.driver_id:
            driver_ids = [int(d) for d in filters.driver_id.split(",") if d.strip().isdigit()]
            stmt = stmt.where(PVBViolation.driver_id.in_(driver_ids))
            count_stmt = count_stmt.where(PVBViolation.driver_id.in_(driver_ids))

        if filters.medallion_id:
            medallion_ids = [int(m) for m in filters.medallion_id.split(",") if m.strip().isdigit()]
            stmt = stmt.where(PVBViolation.medallion_id.in_(medallion_ids))
            count_stmt = count_stmt.where(PVBViolation.medallion_id.in_(medallion_ids))

        if filters.issue_from_date:
            stmt = stmt.where(PVBViolation.issue_date >= filters.issue_from_date)
            count_stmt = count_stmt.where(PVBViolation.issue_date >= filters.issue_from_date)

        if filters.issue_to_date:
            stmt = stmt.where(PVBViolation.issue_date <= filters.issue_to_date)
            count_stmt = count_stmt.where(PVBViolation.issue_date <= filters.issue_to_date)

        if filters.issue_time_from:
            stmt = stmt.where(PVBViolation.issue_time >= filters.issue_time_from)
            count_stmt = count_stmt.where(PVBViolation.issue_time >= filters.issue_time_from)

        if filters.issue_time_to:
            stmt = stmt.where(PVBViolation.issue_time <= filters.issue_time_to)
            count_stmt = count_stmt.where(PVBViolation.issue_time <= filters.issue_time_to)

        # === Get total count ===
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar()

        # === Apply sorting ===
        sort_column = getattr(PVBViolation, filters.sort_by, PVBViolation.updated_on)
        if filters.sort_order.lower() == "asc":
            stmt = stmt.order_by(asc(sort_column))
        else:
            stmt = stmt.order_by(desc(sort_column))

        # === Apply pagination ===
        offset = (filters.page - 1) * filters.per_page
        stmt = stmt.offset(offset).limit(filters.per_page)

        # === Execute query ===
        result = await self.db.execute(stmt)
        violations = result.scalars().all()

        logger.info("Violations fetched", count=len(violations), total=total_count)
        return list(violations), total_count
    
    async def create_violation(self, violation_data: PVBViolationCreate) -> PVBViolation:
        """Create a new violation"""
        logger.debug("Creating new violation", data=violation_data.model_dump())

        violation = PVBViolation(**violation_data.model_dump())
        self.db.add(violation)
        await self.db.flush()
        await self.db.refresh(violation)

        logger.info("Violation created", violation_id=violation.id)
        return violation
    
    async def update_violation(
        self,
        violation: PVBViolation,
        update_data: PVBViolationUpdate,
    ) -> PVBViolation:
        """Update an existing violation"""
        logger.debug("Updating violation", violation_id=violation.id)

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(violation, key, value)

        await self.db.flush()
        await self.db.refresh(violation)

        logger.info("Violation updated", violation_id=violation.id)
        return violation
    
    async def delete_violation(self, violation: PVBViolation) -> None:
        """Soft delete a violation (mark as archived)"""
        logger.debug("Deleting violation", violation_id=violation.id)

        violation.is_archived = True
        violation.is_active = False
        await self.db.flush()

        logger.info("Violation deleted (archived)", violation_id=violation.id)


    # === Log Operations ===

    async def get_log_by_id(self, log_id: int) -> Optional[PVBLog]:
        """Fetch a log by ID"""
        logger.debug("Fetching log by ID", log_id=log_id)

        stmt = select(PVBLog).where(PVBLog.id == log_id)
        result = await self.db.execute(stmt)
        log = result.scalar_one_or_none()

        if log:
            logger.info("Log found", log_id=log_id)
        else:
            logger.warning("Log not found", log_id=log_id)

        return log
    
    async def get_logs(
        self,
        filters: PVBLogFilters,
    ) -> Tuple[List[PVBLog], int]:
        """
        Fetch logs with filters, pagination, and sorting.
        Returns tuple of (logs list, total count).
        """
        logger.debug("Fetching logs with filters", filters=filters.model_dump())

        # === Base query ===
        stmt = select(PVBLog).where(PVBLog.is_archived == False)
        count_stmt = select(func.count(PVBLog.id)).where(PVBLog.is_archived == False)

        # === Apply filters ===
        if filters.log_id:
            stmt = stmt.where(PVBLog.id == filters.log_id)
            count_stmt = count_stmt.where(PVBLog.id == filters.log_id)

        if filters.log_from_date:
            stmt = stmt.where(PVBLog.log_date >= filters.log_from_date)
            count_stmt = count_stmt.where(PVBLog.log_date >= filters.log_from_date)

        if filters.log_to_date:
            stmt = stmt.where(PVBLog.log_date <= filters.log_to_date)
            count_stmt = count_stmt.where(PVBLog.log_date <= filters.log_to_date)

        if filters.log_type:
            types = [t.strip() for t in filters.log_type.split(",") if t.strip()]
            stmt = stmt.where(PVBLog.log_type.in_(types))
            count_stmt = count_stmt.where(PVBLog.log_type.in_(types))

        if filters.log_status:
            statuses = [s.strip() for s in filters.log_status.split(",") if s.strip()]
            stmt = stmt.where(PVBLog.status.in_(statuses))
            count_stmt = count_stmt.where(PVBLog.status.in_(statuses))

        if filters.records_impacted is not None:
            stmt = stmt.where(PVBLog.records_impacted == filters.records_impacted)
            count_stmt = count_stmt.where(PVBLog.records_impacted == filters.records_impacted)

        if filters.success_count is not None:
            stmt = stmt.where(PVBLog.success_count == filters.success_count)
            count_stmt = count_stmt.where(PVBLog.success_count == filters.success_count)

        if filters.unidentified_count is not None:
            stmt = stmt.where(PVBLog.unidentified_count == filters.unidentified_count)
            count_stmt = count_stmt.where(PVBLog.unidentified_count == filters.unidentified_count)

        # === Get total count ===
        count_result = await self.db.execute(count_stmt)
        total_count = count_result.scalar()

        # === Apply sorting ===
        sort_column = getattr(PVBLog, filters.sort_by, PVBLog.log_date)
        if filters.sort_order.lower() == "asc":
            stmt = stmt.order_by(asc(sort_column))
        else:
            stmt = stmt.order_by(desc(sort_column))

        # === Apply Pagination ===
        offset = (filters.page - 1) * filters.per_page
        stmt = stmt.offset(offset).limit(filters.per_page)

        # === Execute query ===
        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        logger.info("Logs fetched", count=len(logs), total=total_count)
        return list(logs), total_count
    
    async def create_log(self, log_data: PVBLogCreate) -> PVBLog:
        """Create a new log"""
        logger.debug("Creating new log", data=log_data.model_dump())

        log = PVBLog(**log_data.model_dump())
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)

        logger.info("Log created", log_id=log.id)
        return log
    
    async def update_log(self, log: PVBLog, update_data: PVBLogUpdate) -> PVBLog:
        """Update an existing log"""
        logger.debug("Updating log", log_id=log.id)

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(log, key, value)

        await self.db.flush()
        await self.db.refresh(log)

        logger.info("Log updated", log_id=log.id)
        return log
    
