# app/curb/repository.py

"""
Data Access Layer for CURB module using async SQLAlchemy 2.x
"""

from typing import List, Optional, Tuple

from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

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
    
    async def create_trip(self, trip_data: CURBTripCreate) -> CURBTrip:
        """Create a new trip"""
        logger.debug("Creating new trip", record_id=trip_data.record_id)

        trip = CURBTrip(**trip_data.model_dump())
        self.db.add(trip)
        await self.db.flush()
        await self.db.refresh(trip)

        logger.info("Trip created", trip_id=trip.id, record_id=trip.record_id)
        return trip
    
    async def bulk_create_trips(self, trips_data: List[CURBTripCreate]) -> List[CURBTrip]:
        """Bulk create trips"""
        logger.debug("Bulk creating trips", count=len(trips_data))

        trips = [CURBTrip(**trip_data.model_dump()) for trip_data in trips_data]
        self.db.add_all(trips)
        await self.db.flush()

        logger.info("Trips bulk created", count=len(trips))
        return trips
    
    async def update_trip(self, trip_id: int, trip_data: CURBTripUpdate) -> Optional[CURBTrip]:
        """Update a trip"""
        logger.debug("Updating trip", trip_id=trip_id)

        trip = await self.get_trip_by_id(trip_id)
        if not trip:
            logger.warning("Trip not found for update", trip_id=trip_id)
            return None
        
        update_data = trip_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(trip, field, value)

        await self.db.flush()
        await self.db.refresh(trip)

        logger.info("Trip updated", trip_id=trip_id)
        return trip
    
    async def get_unreconciled_trips(self, limit: Optional[int] = None) -> List[CURBTrip]:
        """Get all unreconciled trips"""
        logger.debug("Fetching unreconciled trips")

        stmt = select(CURBTrip).where(CURBTrip.is_reconciled == False)

        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        trips = result.scalars().all()

        logger.info("Retrieved unreconciled trips", count=len(trips))
        return list(trips)
    
    async def get_reconciled_unposted_trips(self, limit: Optional[int] = None) -> List[CURBTrip]:
        """Get reconciled but unposted trips"""
        logger.debug("Fetching reconciled unposted trips")

        stmt = select(CURBTrip).where(
            and_(CURBTrip.is_reconciled == True, CURBTrip.is_posted == False)
        )

        if limit:
            stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        trips = result.scalars().all()

        logger.info("Retrieved reconciled unposted trips", count=len(trips))
        return list(trips)
    
    # === Import Log Operations ===

    async def get_import_log_by_id(self, log_id: int) -> Optional[CURBImportLog]:
        """Fetch import log by ID"""
        logger.debug("Fetching import log by ID", log_id=log_id)

        stmt = select(CURBImportLog).where(CURBImportLog.id == log_id)
        result = await self.db.execute(stmt)
        log = result.scalar_one_or_none()

        if log:
            logger.info("Import log found", log_id=log_id)
        else:
            logger.warning("Import log not found", log_id=log_id)

        return log
    
    async def get_import_logs(
        self,
        filters: CURBImportLogFilters,
    ) -> Tuple[List[CURBImportLog], int]:
        """Fetch import logs with filters and pagination"""
        logger.debug("Fetching import logs with filters", filters=filters.model_dump())

        stmt = select(CURBImportLog)
        count_stmt = select(func.count()).select_from(CURBImportLog)

        conditions = []

        if filters.log_id:
            conditions.append(CURBImportLog.id == filters.log_id)

        if filters.import_source:
            sources = [s.strip() for s in filters.import_source.split(",")]
            conditions.append(CURBImportLog.import_source.in_(sources))

        if filters.imported_by:
            conditions.append(CURBImportLog.imported_by.ilike(f"%{filters.imported_by}%"))

        if filters.import_start_from:
            conditions.append(CURBImportLog.import_start >= filters.import_start_from)

        if filters.import_start_to:
            conditions.append(CURBImportLog.import_start <= filters.import_start_to)

        if filters.status:
            statuses = [s.strip() for s in filters.status.split(",")]
            conditions.append(CURBImportLog.status.in_(statuses))

        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))

        total_result = await self.db.execute(count_stmt)
        total_count = total_result.scalar() or 0

        if filters.sort_by and hasattr(CURBImportLog, filters.sort_by):
            sort_column = getattr(CURBImportLog, filters.sort_by)
            if filters.sort_order == "asc":
                stmt = stmt.order_by(asc(sort_column))
            else:
                stmt = stmt.order_by(desc(sort_column))

        offset = (filters.page - 1) * filters.per_page
        stmt = stmt.offset(offset).limit(filters.per_page)

        result = await self.db.execute(stmt)
        logs = result.scalars().all()

        logger.info("Retrieved import logs", count=len(logs), total=total_count)
        return list(logs), total_count
    
    async def create_import_log(self, log_data: CURBImportLogCreate) -> CURBImportLog:
        """Create a new import log"""
        logger.debug("Creating import log", source=log_data.import_source)

        log = CURBImportLog(**log_data.model_dump())
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)

        logger.info("Import log created", log_id=log.id)
        return log
    
    async def update_import_log(
        self, log_id: int, log_data: CURBImportLogUpdate
    ) -> Optional[CURBImportLog]:
        """Update import log"""
        logger.debug("Updating import log", log_id=log_id)

        log = await self.get_import_log_by_id(log_id)
        if not log:
            logger.warning("Import log not found for update", log_id=log_id)
            return None
        
        update_data = log_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(log, field, value)

        await self.db.flush()
        await self.db.refresh(log)

        logger.info("Import log updated", log_id=log_id)
        return log
    
    # === REconciliation Operations ===

    async def create_reconciliation(
        self, recon_data: CURBTripReconciliationCreate
    ) -> CURBTripReconciliation:
        """Create a reconciliation record"""
        logger.debug("Creating reconciliation", trip_id=recon_data.trip_id)

        reconciliation = CURBTripReconciliation(**recon_data.model_dump())
        self.db.add(reconciliation)
        await self.db.flush()
        await self.db.refresh(reconciliation)

        logger.info("Reconciliation created", recon_id=reconciliation.id)
        return reconciliation
    
    async def bulk_create_reconciliations(
        self, recon_data_list: List[CURBTripReconciliationCreate]
    ) -> List[CURBTripReconciliation]:
        """Bulk create reonciliation records"""
        logger.debug("Bulk creating reconciliations", count=len(recon_data_list))

        reconciliations = [
            CURBTripReconciliation(**data.model_dump()) for data in recon_data_list
        ]
        self.db.add_all(reconciliations)
        await self.db.flush()

        logger.info("Reconciliations bulk created", count=len(reconciliations))
        return reconciliations
    

