# app/ledger/repository.py

"""
Repository layer for centralized ledger module.
Handles all database operations for ledger_postings and ledger_balances.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List, Tuple

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logger import get_logger
from app.ledger.models import LedgerPosting, LedgerBalance
from app.ledger.schemas import (
    PostingFilterParams, BalanceFilterParams
)

logger = get_logger(__name__)


class LedgerRepository:
    """
    Repository for Ledger database operations.
    Follows the same pattern as EZPass, CURB and other modules.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # === Ledger Posting Operations ===

    async def create_posting(self, posting: LedgerPosting) -> LedgerPosting:
        """Create a new ledger posting"""
        logger.debug(f"Creating posting: {posting.posting_id}")
        self.db.add(posting)
        await self.db.flush()
        await self.db.refresh(posting)
        logger.info(f"Created posting: {posting.posting_id}")
        return posting
    
    async def get_posting_by_id(self, posting_id: int) -> Optional[LedgerPosting]:
        """Get posting by primary key"""
        stmt = select(LedgerPosting).where(LedgerPosting.id == posting_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_posting_by_posting_id(self, posting_id: str) -> Optional[LedgerPosting]:
        """Get posting by unique posting_id"""
        stmt = select(LedgerPosting).where(LedgerPosting.posting_id == posting_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_postings_filtered(
        self, filters: PostingFilterParams
    ) -> Tuple[List[LedgerPosting], int]:
        """Get postings with filters and pagination"""

        # Build query
        stmt = select(LedgerPosting)
        
        # Apply filters
        conditions = []
        
        if filters.driver_id:
            conditions.append(LedgerPosting.driver_id == filters.driver_id)
        
        if filters.vehicle_id:
            conditions.append(LedgerPosting.vehicle_id == filters.vehicle_id)
        
        if filters.medallion_id:
            conditions.append(LedgerPosting.medallion_id == filters.medallion_id)
        
        if filters.lease_id:
            conditions.append(LedgerPosting.lease_id == filters.lease_id)
        
        if filters.category:
            conditions.append(LedgerPosting.category == filters.category.value)
        
        if filters.entry_type:
            conditions.append(LedgerPosting.entry_type == filters.entry_type.value)
        
        if filters.status:
            conditions.append(LedgerPosting.status == filters.status.value)
        
        if filters.reference_id:
            conditions.append(LedgerPosting.reference_id == filters.reference_id)
        
        if filters.date_from:
            conditions.append(LedgerPosting.transaction_date >= filters.date_from)
        
        if filters.date_to:
            conditions.append(LedgerPosting.transaction_date <= filters.date_to)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total_items = total_result.scalar()
        
        # Apply sorting and pagination
        stmt = stmt.order_by(desc(LedgerPosting.posted_on))
        stmt = stmt.offset((filters.page - 1) * filters.per_page)
        stmt = stmt.limit(filters.per_page)
        
        # Execute query
        result = await self.db.execute(stmt)
        postings = result.scalars().all()
        
        logger.debug(f"Retrieved {len(postings)} postings (total: {total_items})")
        return list(postings), total_items
    
    async def get_postings_by_reference(
        self, reference_id: str, reference_type: Optional[str] = None
    ) -> List[LedgerPosting]:
        """Get all postings for a specific reference"""
        conditions = [LedgerPosting.reference_id == reference_id]

        if reference_type:
            conditions.append(LedgerPosting.reference_type == reference_type)

        stmt = select(LedgerPosting).where(and_(*conditions))
        stmt = stmt.order_by(LedgerPosting.posted_on)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def void_posting(
        self, posting: LedgerPosting, voided_by_posting_id: str
    ) -> LedgerPosting:
        """Mark a posting as voided"""
        logger.debug(f"Voiding posting: {posting.posting_id}")
        posting.status = "Voided"
        posting.voided_by_posting_id = voided_by_posting_id
        await self.db.flush()
        await self.db.refresh(posting)
        logger.info(f"Voided posting: {posting.posting_id}")
        return posting
    
    async def get_driver_postings(
        self, driver_id: int, date_from: Optional[date] = None, date_to: Optional[date] = None
    ) -> List[LedgerPosting]:
        """Get all postings for a driver"""
        conditions = [
            LedgerPosting.driver_id == driver_id,
            LedgerPosting.status == "Posted"
        ]

        if date_from:
            conditions.append(LedgerPosting.transaction_date >= date_from)

        if date_to:
            conditions.append(LedgerPosting.transaction_date <= date_to)

        stmt = select(LedgerPosting).where(and_(*conditions))
        stmt = stmt.order_by(desc(LedgerPosting.transaction_date), desc(LedgerPosting.posted_on))

        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    # === Ledger Balance Operations ===

    async def create_balance(self, balance: LedgerBalance) -> LedgerBalance:
        """Create a new ledger balance"""
        logger.debug(f"Creating balance: {balance.balance_id}")
        self.db.add(balance)
        await self.db.flush()
        await self.db.refresh(balance)
        logger.info(f"Created balance: {balance.balance_id}")
        return balance
    
    async def get_balance_by_id(self, balance_id: int) -> Optional[LedgerBalance]:
        """Get balance by primary key"""
        stmt = select(LedgerBalance).where(LedgerBalance.id == balance_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_balance_by_balance_id(self, balance_id: str) -> Optional[LedgerBalance]:
        """Get balance by unique balance_id"""
        stmt = select(LedgerBalance).where(LedgerBalance.balance_id == balance_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_balance_by_reference(
        self, reference_id: str, reference_type: Optional[str] = None
    ) -> Optional[LedgerBalance]:
        """Get balance by reference ID"""
        conditions = [LedgerBalance.reference_id == reference_id]

        if reference_type:
            conditions.append(LedgerBalance.reference_type == reference_type)

        stmt = select(LedgerBalance).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_balances_filtered(
        self, filters: BalanceFilterParams
    ) -> Tuple[List[LedgerBalance], int]:
        """Get balances with filters and pagination"""

        # Build query
        stmt = select(LedgerBalance)
        
        # Apply filters
        conditions = []
        
        if filters.driver_id:
            conditions.append(LedgerBalance.driver_id == filters.driver_id)
        
        if filters.vehicle_id:
            conditions.append(LedgerBalance.vehicle_id == filters.vehicle_id)
        
        if filters.medallion_id:
            conditions.append(LedgerBalance.medallion_id == filters.medallion_id)
        
        if filters.lease_id:
            conditions.append(LedgerBalance.lease_id == filters.lease_id)
        
        if filters.category:
            conditions.append(LedgerBalance.category == filters.category.value)
        
        if filters.status:
            conditions.append(LedgerBalance.status == filters.status.value)
        
        if filters.reference_id:
            conditions.append(LedgerBalance.reference_id == filters.reference_id)
        
        if filters.min_balance is not None:
            conditions.append(LedgerBalance.balance >= filters.min_balance)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total_items = total_result.scalar()
        
        # Apply sorting and pagination
        stmt = stmt.order_by(LedgerBalance.obligation_date, LedgerBalance.category)
        stmt = stmt.offset((filters.page - 1) * filters.per_page)
        stmt = stmt.limit(filters.per_page)
        
        # Execute query
        result = await self.db.execute(stmt)
        balances = result.scalars().all()
        
        logger.debug(f"Retrieved {len(balances)} balances (total: {total_items})")
        return list(balances), total_items
    
    async def get_open_balances_by_driver(
        self, driver_id: int, category: Optional[str] = None 
    ) -> List[LedgerBalance]:
        """Get all open balances for a driver"""
        conditions = [
            LedgerBalance.driver_id == driver_id,
            LedgerBalance.status == "Open"
        ]

        if category:
            conditions.append(LedgerBalance.category == category)

        stmt = select(LedgerBalance).where(and_(*conditions))
        stmt = stmt.order_by(LedgerBalance.obligation_date)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())
    
    async def update_balance(self, balance: LedgerBalance) -> LedgerBalance:
        """Update a balance record"""
        logger.debug(f"Updating balance: {balance.balance_id}")
        balance.updated_on = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(balance)
        logger.info(f"Updated balance: {balance.balance_id}")
        return balance

    async def close_balance(self, balance: LedgerBalance) -> LedgerBalance:
        """Mark a balance as closed"""
        logger.debug(f"Closing balance: {balance.balance_id}")
        balance.status = "Closed"
        balance.balance = Decimal("0.00")
        balance.closed_on = datetime.now(timezone.utc)
        balance.updated_on = datetime.now(timezone.utc)
        await self.db.flush()
        await self.db.refresh(balance)
        logger.info(f"Closed balance: {balance.balance_id}")
        return balance

    async def get_driver_balance_summary(
        self, driver_id: int, as_of_date: Optional[date] = None
    ) -> dict:
        """Get summary of driver's blanaces by category"""
        conditions = [
            LedgerBalance.driver_id == driver_id,
            LedgerBalance.status == "Open"
        ]

        if as_of_date:
            conditions.append(LedgerBalance.obligation_date <= as_of_date)

        stmt = select(
            LedgerBalance.category,
            func.sum(LedgerBalance.balance).label("total_due"),
            func.count(LedgerBalance.id).label("count")
        ).where(and_(*conditions))
        stmt = stmt.group_by(LedgerBalance.category)

        result = await self.db.execute(stmt)
        rows = result.all()

        summary = {
            "Lease": Decimal("0.00"),
            "Repair": Decimal("0.00"),
            "Loan": Decimal("0.00"),
            "EZPass": Decimal("0.00"),
            "PVB": Decimal("0.00"),
            "TLC": Decimal("0.00"),
            "Taxes": Decimal("0.00"),
            "Misc": Decimal("0.00"),
            "Deposit": Decimal("0.00"),
            "open_count": 0
        }
        
        for row in rows:
            category = row.category
            total_due = row.total_due or Decimal("0.00")
            count = row.count or 0
            
            summary[category] = total_due
            summary["open_count"] += count
        
        return summary

    # === Transaction Management ===

    async def commit(self):
        """Commit the current transaction"""
        await self.db.commit()
        logger.debug("Transaction committed")

    async def rollback(self):
        """Rollback the current transaction"""
        await self.db.rollback()
        logger.debug("Transaction rolled back")



