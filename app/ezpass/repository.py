# app/ezpass/repository.py

"""
Data Access Layer for EZPass module using async SQLAlchemy 2.x
"""

from typing import List, Optional, Tuple

from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession

from app.ezpass.models import EZPassTransaction, EZPassLog
from app.ezpass.schemas import (
    EZPassTransactionCreate, EZPassTransactionUpdate,
    EZPassLogCreate, EZPassTransactionFilters, EZPassLogFilters,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class EZPassRepository:
    """
    Data Access Layer for EZPass operations.
    Handles all database interactions using async SQLAchemy 2.x.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        logger.debug("EZPassRepository initialized", session_id=id(db))

    async def get_transaction_by_id(self, transaction_id: int) -> Optional[EZPassTransaction]:
        """Fetch a transaction by ID"""
        logger.debug("Fetching transaction by ID", transaction_id=transaction_id)

        stmt = select(EZPassTransaction).where(EZPassTransaction.id == transaction_id)
        result = await self.db.execute(stmt)
        transaction = result.scalar_one_or_none()

        if transaction:
            logger.info("Transaction found", transaction_id=transaction_id)
        else:
            logger.warning("Transaction not found", transaction_id=transaction_id)

        return transaction
    
    async def get_transactions(
        self,
        filters: EZPassTransactionFilters,
    ) -> Tuple[List[EZPassTransaction], int]:
        """
        Fetch transactions with filters, pagination, and sorting.
        Returns tuple of (transactions, total_count)
        """
        logger.debug("Fetching transactions with filters", filters=filters.model_dump())

        # === Base query ===
        query = select(EZPassTransaction)

        # === Apply filters ===
        conditions = []

        if filters.transaction_id:
            conditions.append(EZPassTransaction.id == filters.transaction_id)

        if filters.transaction_from_date:
            conditions.append(EZPassTransaction.transaction_date >= filters.transaction_from_date.date())

        if filters.transaction_to_date:
            conditions.append(EZPassTransaction.transaction_date <= filters.transaction_to_date.date())

        if filters.medallion_no:
            medallion_nos = [m.strip() for m in filters.medallion_no.split(",")]
            conditions.append(EZPassTransaction.medallion_no.in_(medallion_nos))

        if filters.driver_id:
            driver_ids = [int(d.strip()) for d in filters.driver_id.split(",")]
            conditions.append(EZPassTransaction.driver_id.in_(driver_ids))

        if filters.plate_no:
            plate_nos = [p.strip() for p in filters.plate_no.split(",")]
            conditions.append(EZPassTransaction.plate_no.in_(plate_nos))

        if filters.posting_from_date:
            conditions.append(EZPassTransaction.posting_date >= filters.posting_from_date.date())

        if filters.posting_to_date:
            conditions.append(EZPassTransaction.posting_date <= filters.posting_to_date.date())

        if filters.transaction_status:
            statuses = [s.strip() for s in filters.transaction_status.split(",")]
            conditions.append(EZPassTransaction.status.in_(statuses))

        if conditions:
            query = query.where(and_(*conditions))

        # === Get total count ===
        count_stmt = select(func.count()).select_from(EZPassTransaction)
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total_count_result = await self.db.execute(count_stmt)
        total_count = total_count_result.scalar()

        # === Apply sorting ===
        sort_column = getattr(EZPassTransaction, filters.sort_by, EZPassTransaction.updated_on)
        if filters.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # === Apply pagination ===
        offset = (filters.page - 1) * filters.per_page
        query = query.offset(offset).limit(filters.per_page)

        # === Execute query ===
        result = await self.db.execute(query)
        transactions = result.scalars().all()

        logger.info(
            "Transactions fetched successfully",
            count=len(transactions),
            total_count=total_count,
            page=filters.page,
        )

        return list(transactions), total_count
    
    async def create_transaction(
        self,
        transaction_data: EZPassTransactionCreate,
    ) -> EZPassTransaction:
        """Create a new transaction"""
        logger.debug("Creating new transaction", data=transaction_data.model_dump())

        transaction = EZPassTransaction(**transaction_data.model_dump())
        self.db.add(transaction)
        await self.db.flush()
        await self.db.refresh(transaction)

        logger.info("Trnasaction created successfully", transaction_id=transaction.id)
        return transaction
    
    async def update_transaction(
        self,
        transaction: EZPassTransaction,
        update_data: EZPassTransactionUpdate,
    ) -> EZPassTransaction:
        """Update an existing transaction"""
        logger.debug(
            "Updating transaction",
            transaction_id=transaction.id,
            data=update_data.model_dump(exclude_unset=True),
        )

        for key, value in update_data.model_dump(exclude_unset=True).items():
            setattr(transaction, key, value)

        await self.db.flush()
        await self.db.refresh(transaction)

        logger.info("Transaction udpated successfully", transaction_id=transaction.id)
        return transaction
    
    async def bulk_create_transactions(
        self,
        transactions_data: List[EZPassTransactionCreate],
    ) -> List[EZPassTransaction]:
        """Bulk create transactions"""
        logger.debug("Bulk creating transactions", count=len(transactions_data))

        transactions = [
            EZPassTransaction(**data.model_dump())
            for data in transactions_data
        ]

        self.db.add_all(transactions)
        await self.db.flush()

        logger.info("Bulk transactions created successfully", count=len(transactions))
        return transactions
    
    async def get_unassociated_transactions(self) -> List[EZPassTransaction]:
        """Get all transactions with status 'Imported'"""
        logger.debug("Fetching unassociated transactions")

        stmt = select(EZPassTransaction).where(
            EZPassTransaction.status == "Imported"
        )
        result = await self.db.execute(stmt)
        transactions = result.scalars().all()

        logger.info("Unassociated transactions fetched", count=len(transactions))
        return list(transactions)
    
    async def get_unposted_transactions(self) -> List[EZPassTransaction]:
        """Get all transactions with status 'Associated'"""
        logger.debug("Fetching unposted transactions")

        stmt = select(EZPassTransaction).where(
            EZPassTransaction.status == "Associated"
        )
        result = await self.db.execute(stmt)
        transactions = result.scalars().all()

        logger.info("Unposted transactions fetched", count=len(transactions))
        return list(transactions)
    
    # ======== Log Operations ========

    async def get_log_by_id(self, log_id: int) -> Optional[EZPassLog]:
        """Fetch log by ID"""
        logger.debug("Fetching log by ID", log_id=log_id)

        stmt = select(EZPassLog).where(EZPassLog.id == log_id)
        result = await self.db.execute(stmt)
        log = result.scalar_one_or_none()

        if log:
            logger.info("Log found", log_id=log_id)
        else:
            logger.warning("Log not found", log_id=log_id)

        return log
    
    async def get_logs(
        self,
        filters: EZPassLogFilters,
    ) -> Tuple[List[EZPassLog], int]:
        """
        Fetch logs with filters, pagination, and sorting.
        Returns tuple of (logs, total_count)
        """
        logger.debug("Fetching logs with filters", filters=filters.model_dump())

        # === Base query ===
        query = select(EZPassLog)

        # === Apply filters ===
        conditions = []

        if filters.log_id:
            conditions.append(EZPassLog.id == filters.log_id)

        if filters.log_from_date:
            conditions.append(EZPassLog.log_date >= filters.log_from_date)

        if filters.log_to_date:
            conditions.append(EZPassLog.log_date <= filters.log_to_date)

        if filters.log_status:
            statuses = [s.strip() for s in filters.log_status.split(",")]
            conditions.append(EZPassLog.status.in_(statuses))

        if filters.log_type:
            types = [t.strip() for t in filters.log_type.split(",")]
            conditions.append(EZPassLog.log_type.in_(types))

        if filters.records_impacted is not None:
            conditions.append(EZPassLog.records_impacted == filters.records_impacted)

        if filters.success_count is not None:
            conditions.append(EZPassLog.success_count == filters.success_count)

        if filters.unidentified_count is not None:
            conditions.append(EZPassLog.unidentified_count == filters.unidentified_count)

        if conditions:
            query = query.where(and_(*conditions))

        # === Get total count ===
        count_stmt = select(func.count()).select_from(EZPassLog)
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total_count_result = await self.db.execute(count_stmt)
        total_count = total_count_result.scalar()

        # === Apply sorting ===
        sort_column = getattr(EZPassLog, filters.sort_by, EZPassLog.log_date)
        if filters.sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(asc(sort_column))

        # === Apply pagination ===
        offset = (filters.page - 1) * filters.per_page
        query = query.offset(offset).limit(filters.per_page)

        # === Execute query ===
        result = await self.db.execute(query)
        logs = result.scalars().all()

        logger.info(
            "Logs fetched successfully",
            count=len(logs),
            total_count=total_count,
            page=filters.page
        )

        return list(logs), total_count
    
    async def create_log(self, log_data: EZPassLogCreate) -> EZPassLog:
        """Create a new log"""
        logger.debug("Creating new log", data=log_data.model_dump())

        log = EZPassLog(**log_data.model_dump())
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)

        logger.info("Log created successfully", log_id=log.id)
        return log
    
    async def update_log(self, log: EZPassLog, **kwargs) -> EZPassLog:
        """Update an existing log"""
        logger.debug("Updating log", log_id=log.id, updates=kwargs)

        for key, value in kwargs.items():
            if hasattr(log, key):
                setattr(log, key, value)

        await self.db.flush()
        await self.db.refresh(log)

        logger.info("Log updated successfully", log_id=log.id)
        return log
    
