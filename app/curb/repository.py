# app/curb/repository.py

"""
Data Access Layer for CURB module using async SQLAlchemy 2.x
"""

from typing import List, Optional, Tuple
from datetime import date

from sqlalchemy import select, func, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.curb.models import CURBTrip, CURBImportLog, CURBTripReconciliation
from app.curb.schemas import (
    CURBTripCreate, CURBTripUpdate, CURBTripFilters,
    CURBImportLogCreate, CURBImportLogUpdate, CURBImportLogFilters,
    CURBTripReconciliationCreate,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class CURBRepository:
    """
    Data Access Layer for CURB operations.
    Handles all database interactions using async SQLAlchemy 2.x
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        logger.debug("CURBRepository initialized", session_id=id(db))

    # === Trip Operations ===

    async def get_trip_by_id(self, trip_id: int) -> Optional[CURBTrip]:
        """Fetch a trip by ID"""
        logger.debug("Fetching trip by ID", trip_id=trip_id)

        stmt = select(CURBTrip).where(CURBTrip.id == trip_id)
        result = await self.db.execute(stmt)
        trip = result.scalar_one_or_none()

        if trip:
            logger.info("Trip found", trip_id=trip_id)
        else:
            logger.warning("Trip not found", trip_id=trip_id)

        return trip
    
    async def get_trip_by_record_id(self, record_id: str, period: Optional[str] = None) -> Optional[CURBTrip]:
        """Fetch a trip by record_id and optionally period"""
        logger.debug("Fetching trip by record_id", record_id=record_id, period=period)

        stmt = select(CURBTrip).where(CURBTrip.record_id == record_id)
        if period:
            stmt = stmt.where(CURBTrip.period == period)

        result = await self.db.execute(stmt)
        trip = result.scalar_one_or_none()

        if trip:
            logger.info("Trip found by record_id", record_id=record_id)
        else:
            logger.debug("Trip not found by record_id", record_id=record_id)

        return trip
    
    async def get_trips(
        self,
        filters: CURBTripFilters,
    ) -> Tuple[List[CURBTrip], int]:
        """
        Fetch trips with filters, pagination, and sorting.
        Returns tuple of (trips list, total count).
        """
        logger.debug("Fetching trips with filters", filters=filters.model_dump())

        # === Base query ===
        stmt = select(CURBTrip)
        count_stmt = select(func.count()).select_from(CURBTrip)

        # === Apply Filters ===
        conditions = []

        if filters.trip_id:
            conditions.append(CURBTrip.id == filters.trip_id)

        if filters.record_id:
            conditions.append(CURBTrip.record_id == filters.record_id)

        if filters.period:
            conditions.append(CURBTrip.period == filters.period)

        if filters.driver_id:
            driver_ids = [d.strip() for d in filters.driver_id.split(",")]
            conditions.append(CURBTrip.driver_id.in_(driver_ids))

        if filters.cab_number:
            cab_numbers = [c.strip() for c in filters.cab_number.split(",")]
            conditions.append(CURBTrip.cab_number.in_(cab_numbers))

        if filters.start_date_from:
            conditions.append(CURBTrip.start_date >= filters.start_date_from)

        if filters.start_date_to:
            conditions.append(CURBTrip.start_date <= filters.start_date_to)

        if filters.end_date_from:
            conditions.append(CURBTrip.end_date >= filters.end_date_from)

        if filters.end_date_to:
            conditions.append(CURBTrip.end_date <= filters.end_date_to)

        if filters.payment_type:
            payment_types = [p.strip() for p in filters.payment_type.split(",")]
            conditions.append(CURBTrip.payment_type.in_(payment_types))

        if filters.is_posted is not None:
            conditions.append(CURBTrip.is_posted == filters.is_posted)

        if filters.status:
            statuses = [s.strip() for s in filters.status.split(",")]
            conditions.append(CURBTrip.status.in_(statuses))

        # === Apply Conditions ===

        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))

        # === Get total count ===
        total_result = await self.db.execute(count_stmt)
        total_count = total_result.scalar() or 0

        # === Apply Sorting ===
        if filters.sort_by and hasattr(CURBTrip, filters.sort_by):
            sort_column = getattr(CURBTrip, filters.sort_by)
            if filters.sort_order == "asc":
                stmt = stmt.order_by(asc(sort_column))
            else:
                stmt = stmt.order_by(desc(sort_column))

        # === Apply pagination ===
        offset = (filters.page - 1) * filters.per_page
        stmt = stmt.offset(offset).limit(filters.per_page)

        # === Execute query ===
        result = await self.db.execute(stmt)
        trips = result.scalars().all()

        logger.inf("Retrieved trips", count=len(trips), total=total_count)
        return list(trips), total_count
    
    
