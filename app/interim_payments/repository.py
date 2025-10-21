# app/interim_payments/repository.py

"""
Data Access Layer for Interim Payments module using SQLAlchemy 2.x.
Handles all database interactions with async operations.
"""

from typing import List, Optional, Tuple
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, func, and_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.interim_payments.models import (
    InterimPayment, InterimPaymentAllocation, InterimPaymentLog
)
from app.interim_payments.schemas import (
    InterimPaymentCreate, InterimPaymentUpdate,
    InterimPaymentAllocationCreate, InterimPaymentFilters,
    InterimPaymentAllocationFilters, InterimPaymentLogCreate,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class InterimPaymentRepository:
    """
    Data Access Layer for Interim Payment Operations.
    Handles all database interactions using async SQLAlchemy 2.x.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        logger.debug("InterimPaymentRepository intialized", session_id=id(db))

    # === Payment Operations ===

    async def create_payment(
        self, payment_data: InterimPaymentCreate, payment_id: str, receipt_number: str
    ) -> InterimPayment:
        """Create a new interim payment record."""
        logger.info(
            "Creating new interim payment",
            payment_id=payment_id,
            driver_id=payment_data.driver_id,
            amount=str(payment_data.total_amount),
        )

        payment = InterimPayment(
            payment_id=payment_id,
            driver_id=payment_data.driver_id,
            medallion_id=payment_data.medallion_id,
            lease_id=payment_data.lease_id,
            payment_date=payment_data.payment_date,
            total_amount=payment_data.total_amount,
            payment_method=payment_data.payment_method.value,
            check_number=payment_data.check_number,
            notes=payment_data.notes,
            status="Completed",
            receipt_number=receipt_number,
            receipt_issued_at=datetime.now(timezone.utc),
            allocated_amount=Decimal("0.00"),
            unallocated_amount=payment_data.total_amount,
        )

        self.db.add(payment)
        await self.db.flush()
        await self.db.refresh(payment, ["driver", "medallion", "lease"])

        logger.info("Interim payment created", payment_id=payment_id, id=payment.id)
        return payment
    
    async def get_payment_by_id(self, payment_id: int) -> Optional[InterimPayment]:
        """Fetch a payment by ID with relationships."""
        logger.debug("Fetching payment by ID", payment_id=payment_id)

        stmt = (
            select(InterimPayment)
            .options(
                selectinload(InterimPayment.driver),
                selectinload(InterimPayment.medallion),
                selectinload(InterimPayment.lease),
                selectinload(InterimPayment.allocations),
            )
            .where(InterimPayment.id == payment_id)
        )

        result = await self.db.execute(stmt)
        payment = result.scalar_one_or_none()

        if payment:
            logger.info("Payment found", payment_id=payment_id)
        else:
            logger.warning("Payment not found", payment_id=payment_id)

        return payment
    
    async def get_payment_by_payment_id(self, payment_id: str) -> Optional[InterimPayment]:
        """Fetch a payment by payment_id string."""
        logger.debug("Fetching payment by payment_id", payment_id=payment_id)

        stmt = (
            select(InterimPayment)
            .options(
                selectinload(InterimPayment.driver),
                selectinload(InterimPayment.medallion),
                selectinload(InterimPayment.lease),
                selectinload(InterimPayment.allocations),
            )
            .where(InterimPayment.payment_id == payment_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_payments(
        self, filters: InterimPaymentFilters
    ) -> Tuple[list[InterimPayment], int]:
        """Get payments with filters and pagination."""
        logger.debug("Getting payments with filters", filters=filters.model_dump())

        # === Build base query ===
        stmt = select(InterimPayment).options(
            selectinload(InterimPayment.driver),
            selectinload(InterimPayment.medallion),
            selectinload(InterimPayment.allocations),
        )

        # Apply filters
        conditions = []
        
        if filters.driver_id:
            conditions.append(InterimPayment.driver_id == filters.driver_id)
        
        if filters.medallion_id:
            conditions.append(InterimPayment.medallion_id == filters.medallion_id)
        
        if filters.lease_id:
            conditions.append(InterimPayment.lease_id == filters.lease_id)
        
        if filters.payment_date_from:
            conditions.append(InterimPayment.payment_date >= filters.payment_date_from)
        
        if filters.payment_date_to:
            conditions.append(InterimPayment.payment_date <= filters.payment_date_to)
        
        if filters.payment_method:
            conditions.append(InterimPayment.payment_method == filters.payment_method.value)
        
        if filters.status:
            conditions.append(InterimPayment.status == filters.status.value)
        
        if filters.receipt_number:
            conditions.append(InterimPayment.receipt_number == filters.receipt_number)
        
        if filters.payment_id:
            conditions.append(InterimPayment.payment_id == filters.payment_id)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total_count = total_result.scalar()

        # Apply sorting
        sort_column = getattr(InterimPayment, filters.sort_by, InterimPayment.payment_date)
        if filters.sort_order == "asc":
            stmt = stmt.order_by(asc(sort_column))
        else:
            stmt = stmt.order_by(desc(sort_column))

        # Apply pagination
        offset = (filters.page - 1) * filters.per_page
        stmt = stmt.offset(offset).limit(filters.per_page)

        # Execute query
        result = await self.db.execute(stmt)
        payments = result.scalars().all()

        logger.info(
            "Retrieved payments",
            count=len(payments),
            total=total_count,
            page=filters.page
        )

        return list(payments), total_count
    
    async def update_payment(
        self, payment: InterimPayment, payment_data: InterimPaymentUpdate
    ) -> InterimPayment:
        """Update a payment record."""
        logger.debug("Updating payment", payment_id=payment.payment_id)

        update_data = payment_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(payment, field):
                setattr(payment, field, value)

        await self.db.flush()
        await self.db.refresh(payment)

        logger.info("Payment updated", payment_id=payment.payment_id)
        return payment
    
    async def update_payment_amounts(
        self, payment: InterimPayment, allocated_amount: Decimal, unallocated_amount: Decimal
    ) -> None:
        """Update payment allocation tracking amounts."""
        logger.debug(
            "Updating payment amounts",
            payment_id=payment.payment_id,
            allocated=str(allocated_amount),
            unallocated=str(unallocated_amount),
        )

        payment.allocated_amount = allocated_amount
        payment.unallocated_amount = unallocated_amount

        await self.db.flush()

    async def get_next_payment_number(self, year: int) -> int:
        """Get the next sequential payment number for a year."""
        logger.debug("Getting next payment number", year=year)

        prefix = f"IMP-{year}-"

        stmt = (
            select(InterimPayment.payment_id)
            .where(InterimPayment.payment_id.like(f"{prefix}%"))
            .order_by(desc(InterimPayment.payment_id))
        )

        result = await self.db.execute(stmt)
        last_payment_id = result.scalar_one_or_none()

        if last_payment_id:
            try:
                last_number = int(last_payment_id.split("-")[-1])
                next_number = last_number + 1
            except (ValueError, IndexError):
                next_number = 1
        else:
            next_number = 1

        logger.info("Next payment number", year=year, number=next_number)
        return next_number
    
    async def get_next_receipt_number(self) -> str:
        """Generate next receipt number."""
        logger.debug("Generating next receipt number")

        now = datetime.now(timezone.utc)
        prefix = f"RCP-{now.strftime("%Y%m%d")}-"

        stmt = (
            select(InterimPayment.receipt_number)
            .where(InterimPayment.receipt_number.like(f"{prefix}%"))
            .order_by(desc(InterimPayment.receipt_number))
        )

        result = await self.db.execute(stmt)
        last_receipt = result.scalar_one_or_none()

        if last_receipt:
            try:
                last_number = int(last_receipt.split("-")[-1])
                next_number = last_number + 1
            except (ValueError, IndexError):
                next_number = 1
        else:
            next_number = 1

        receipt_number = f"{prefix}{next_number:04d}"
        logger.info("Generated receipt number", receipt_number=receipt_number)
        return receipt_number
    
    # === Allocation Operations ===

    async def create_allocation(
        self, payment_id: int, allocation_data: InterimPaymentAllocationCreate
    ) -> InterimPaymentAllocation:
        """Create a payment allocation record."""
        logger.debug(
            "Creating allocation", payment_id=payment_id, category=allocation_data.category
        )

        allocation = InterimPaymentAllocation(
            payment_id=payment_id, **allocation_data.model_dump()
        )

        self.db.add(allocation)
        await self.db.flush()
        await self.db.refresh(allocation)

        logger.info("Allocation created", allocation_id=allocation.id)
        return allocation
    
    async def bulk_create_allocations(
        self, payment_id: int, allocation_data_list: List[InterimPaymentAllocationCreate]
    ) -> List[InterimPaymentAllocation]:
        """Bulk create allocation records."""
        logger.debug("Bulk creating allocations", count=len(allocation_data_list))

        allocations = [
            InterimPaymentAllocation(
                payment_id=payment_id, **data.model_dump()
            )
            for data in allocation_data_list
        ]

        self.db.add_all(allocations)
        await self.db.flush()

        logger.info("Allocations bulk created", count=len(allocations))
        return allocations
    
    async def get_allocation_by_id(
        self, allocation_id: int
    ) -> Optional[InterimPaymentAllocation]:
        """Fetch an allocation by ID."""
        logger.debug("Fetching allocation by ID", allocation_id=allocation_id)

        stmt = (
            select(InterimPaymentAllocation)
            .options(selectinload(InterimPaymentAllocation.payment))
            .where(InterimPaymentAllocation.id == allocation_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_allocations(
        self, filters: InterimPaymentAllocationFilters
    ) -> Tuple[List[InterimPaymentAllocation], int]:
        """Get allocations with filters and pagination."""
        logger.debug("Getting allocations with filters", filters=filters.model_dump())

        # === Build base query ===
        stmt = select(InterimPaymentAllocation).options(
            selectinload(InterimPaymentAllocation.payment)
        )

        # === Apply filters ===
        conditions = []

        if filters.payment_id:
            conditions.append(InterimPaymentAllocation.payment_id == filters.payment_id)

        if filters.category:
            conditions.append(InterimPaymentAllocation.category == filters.category.value)

        if filters.reference_id:
            conditions.append(InterimPaymentAllocation.reference_id == filters.reference_id)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # === Get total count ===
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total_count = total_result.scalar()

        # === Apply sorting ===
        sort_column = getattr(
            InterimPaymentAllocation, filters.sort_by, InterimPaymentAllocation.created_on
        )

        if filters.sort_order == "asc":
            stmt = stmt.order_by(asc(sort_column))
        else:
            stmt = stmt.order_by(desc(sort_column))

        # === Apply pagination ===
        offset = (filters.page - 1) * filters.per_page
        stmt = stmt.offset(offset).limit(filters.per_page)

        # === Execute query ===
        result = await self.db.execute(stmt)
        allocations = result.scalars().all()

        logger.info(
            "Retrieved allocations", count=len(allocations), total=total_count
        )

        return list(allocations), total_count
    
    async def update_allocation_ledger_ref(
        self, allocation: InterimPaymentAllocation, ledger_ref: str
    ) -> None:
        """Update allocation with ledger posting reference."""
        logger.debug(
            "Updating allocation ledger reference",
            allocation_id=allocation.id,
            ledger_ref=ledger_ref,
        )

        allocation.ledger_posting_ref = ledger_ref
        allocation.posted_at = datetime.now(timezone.utc)

        await self.db.flush()

    # === Log Operations ===

    async def create_log(self, log_data: InterimPaymentLogCreate) -> InterimPaymentLog:
        """Create a log entry"""
        logger.debug("Creating Log Entry", log_type=log_data.log_type)

        log = InterimPaymentLog(**log_data.model_dump())
        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)

        logger.info("Log entry created", log_id=log.id)
        return log
    
    # === Transaction management ===

    async def commit(self) -> None:
        """Commit the current transaction."""
        logger.debug("Committing transaction")
        await self.db.commit()
        logger.info("Transaction committed")

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        logger.debug("Rolling back transaction")
        await self.db.rollback()
        logger.warning("Transaction rolled back")

