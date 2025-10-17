# app/driver_loans/repository.py

"""
Data Access Layer for Driver Loans module using SQLAlchemy 2.x
"""

from typing import List, Optional, Tuple
from datetime import date
from decimal import Decimal

from sqlalchemy import select, func, and_, desc, asc, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.driver_loans.models import DriverLoan, DriverLoanInstallment, DriverLoanLog
from app.driver_loans.schemas import (
    DriverLoanCreate, DriverLoanUpdate, DriverLoanInstallmentCreate,
    DriverLoanInstallmentUpdate, DriverLoanFilters, DriverLoanInstallmentFilters,
    DriverLoanLogCreate,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DriverLoanRepository:
    """
    Data Access Layer for Driver Loan Operations.
    Handles all database interactions using async SQLAlchemy 2.x.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        logger.debug("DriverLoanRepository initialized", session_id=id(db))

    async def create_loan(self, loan_data: DriverLoanCreate, loan_id: str, start_week: date) -> DriverLoan:
        """Create a new driver loan."""
        logger.info("Creating new driver loan", loan_id=loan_id, driver_id=loan_data.driver_id)

        loan = DriverLoan(
            loan_id=loan_id,
            driver_id=loan_data.driver_id,
            medallion_id=loan_data.medallion_id,
            lease_id=loan_data.lease_id,
            loan_amount=loan_data.loan_amount,
            interest_rate=loan_data.interest_rate,
            loan_date=loan_data.loan_date,
            start_week=start_week,
            purpose=loan_data.purpose,
            notes=loan_data.notes,
            status="Draft",
            outstanding_balance=loan_data.loan_amount,
        )

        self.db.add(loan)
        await self.db.flush()
        await self.db.refresh(loan, ["driver", "medallion", "lease"])

        logger.info("Driver loan created", loan_id=loan.loan_id, id=loan.id)
        return loan
    
    async def get_loan_by_id(self, loan_id: int) -> Optional[DriverLoan]:
        """Fetch a loan by ID with relationships."""
        logger.debug("Fetching loan by ID", loan_id=loan_id)

        stmt = (
            select(DriverLoan)
            .options(
                selectinload(DriverLoan.driver),
                selectinload(DriverLoan.medallion),
                selectinload(DriverLoan.lease),
                selectinload(DriverLoan.installments),
            )
            .where(DriverLoan.id == loan_id)
        )

        result = await self.db.execute(stmt)
        loan = result.scalar_one_or_none()

        if loan:
            logger.info("Loan found", loan_id=loan_id, loan_id_str=loan.loan_id)
        else:
            logger.warning("Loan not found", loan_id=loan_id)

        return loan
    
    async def get_loan_by_loan_id(self, loan_id: str) -> Optional[DriverLoan]:
        """Fetch a loan by loan_id string."""
        logger.debug("Fetching loan by loan_id", loan_id=loan_id)

        stmt = (
            select(DriverLoan)
            .options(
                selectinload(DriverLoan.driver),
                selectinload(DriverLoan.medallion),
                selectinload(DriverLoan.lease),
                selectinload(DriverLoan.installments),
            )
            .where(DriverLoan.loan_id == loan_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_loans(
        self,
        filters: DriverLoanFilters,
    ) -> Tuple[List[DriverLoan], int]:
        """Fetch loans with filters, pagination, and sorting."""
        logger.debug("Fetching loans with filters", filters=filters.model_dump())

        # === Base query with filters ===
        query = select(DriverLoan).options(
            selectinload(DriverLoan.driver),
            selectinload(DriverLoan.medallion),
        )

        # === Apply filters ===
        conditions = []
        if filters.driver_id:
            conditions.append(DriverLoan.driver_id == filters.driver_id)
        if filters.medallion_id:
            conditions.append(DriverLoan.medallion_id == filters.medallion_id)
        if filters.status:
            conditions.append(DriverLoan.status == filters.status)
        if filters.loan_date_from:
            conditions.append(DriverLoan.loan_date >= filters.loan_date_from)
        if filters.loan_date_to:
            conditions.append(DriverLoan.loan_date <= filters.loan_date_to)
        if filters.outstanding_only:
            conditions.append(DriverLoan.outstanding_balance > 0)

        if conditions:
            query = query.where(and_(*conditions))

        # === Count total items ===
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total_items = total_result.scalar() or 0

        # === Apply sorting ===
        sort_column = getattr(DriverLoan, filters.sort_by, DriverLoan.created_on)
        if filters.sort_order == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        # === Apply pagination ===
        offset = (filters.page - 1) * filters.per_page
        query = query.limit(filters.per_page).offset(offset)

        # === Execute query ===
        result = await self.db.execute(query)
        loans = result.scalars().all()

        logger.info(
            "Loans retrieved",
            total_items=total_items,
            page=filters.page,
            per_page=filters.per_page,
        )

        return loans, total_items
    
    async def update_loan(self, loan: DriverLoan, loan_data: DriverLoanUpdate) -> DriverLoan:
        """Update a loan."""
        logger.info("Updating loan", loan_id=loan.loan_id)

        for field, value in loan_data.model_dump(exclude_unset=True).items():
            setattr(loan, field, value)

        await self.db.flush()
        await self.db.refresh(loan)

        logger.info("Loan Updated", loan_id=loan.loan_id)
        return loan
    
    async def update_loan_balances(
        self, loan_id: int, principal_paid: Decimal, interest_paid: Decimal,
    ) -> None:
        """Update loan payment totals and outstanding balance."""
        logger.debug("Updating loan balances", loan_id=loan_id)

        stmt = (
            update(DriverLoan)
            .where(DriverLoan.id == loan_id)
            .values(
                total_principal_paid=DriverLoan.total_principal_paid + principal_paid,
                total_interest_paid=DriverLoan.total_interest_paid + interest_paid,
                outstanding_balance=DriverLoan.outstanding_balance - principal_paid,
            )
        )

        await self.db.execute(stmt)
        await self.db.flush()

    async def get_next_loan_number(self, year: int) -> int:
        """Get the next sequential loan number for the year."""
        prefix = f"DLN{year}-"

        stmt = (
            select(func.max(DriverLoan.loan_id))
            .where(DriverLoan.loan_id.like(f"{prefix}%"))
        )

        result = await self.db.execute(stmt)
        max_loan_id = result.scalar()

        if max_loan_id:
            last_number = int(max_loan_id.split("-")[1])
            return last_number + 1
        else:
            return 1
        
    # === Installment Operations ===

    async def create_installments(
        self,
        installments_data: List[DriverLoanInstallmentCreate],
    ) -> List[DriverLoanInstallment]:
        """Create multiple loan installments."""
        logger.info("Creating loan installments", count=len(installments_data))

        installments = []
        for data in installments_data:
            installment = DriverLoanInstallment(
                installment_id=data.installment_id,
                loan_id=data.loan_id,
                installment_number=data.installment_number,
                week_start_date=data.week_start_date,
                week_end_date=data.week_end_date,
                principal_amount=data.principal_amount,
                interest_amount=data.interest_amount,
                total_due=data.total_due,
                prior_balance=data.prior_balance,
                outstanding_principal=data.outstanding_principal,
                remaining_balance=data.remaining_balance,
                status="Scheduled"
            )
            installments.append(installment)
            self.db.add(installment)

        await self.db.flush()

        logger.info("Loan installments created", count=len(installments))
        return installments
    
    async def get_installment_by_id(self, installment_id: int) -> Optional[DriverLoanInstallment]:
        """Fetch an installment by ID"""
        logger.debug("Fetching installment by ID", installment_id=installment_id)

        stmt = (
            select(DriverLoanInstallment)
            .options(selectinload(DriverLoanInstallment.loan))
            .where(DriverLoanInstallment.id == installment_id)
        )

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_installments(
        self,
        filters: DriverLoanInstallmentFilters,
    ) -> Tuple[List[DriverLoanInstallment], int]:
        """Fetch installments with filters, pagination, and sorting."""
        logger.debug("Fetching installments with filters", filters=filters.model_dump())

        # === Build query ===
        query = select(DriverLoanInstallment)

        # === Apply filters ===
        conditions = []
        if filters.loan_id:
            conditions.append(DriverLoanInstallment.loan_id == filters.loan_id)
        if filters.status:
            conditions.append(DriverLoanInstallment.status == filters.status)
        if filters.week_start_from:
            conditions.append(DriverLoanInstallment.week_start_date >= filters.week_start_from)
        if filters.week_start_to:
            conditions.append(DriverLoanInstallment.week_start_date <= filters.week_start_to)
        if filters.due_only:
            conditions.append(DriverLoanInstallment.status == "Due")

        if conditions:
            query = query.where(and_(*conditions))

        # === Count total items ===
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total_items = total_result.scalar() or 0

        # === Apply sorting ===
        sort_column = getattr(DriverLoanInstallment, filters.sort_by, DriverLoanInstallment.week_start_date)
        if filters.sort_order == "asc":
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))

        # === Apply pagination ===
        offset = (filters.page - 1) * filters.per_page
        query = query.limit(filters.per_page).offset(offset)

        # === Execute query ===
        result = await self.db.execute(query)
        installments = result.scalars().all()

        return installments, total_items
    
    async def get_due_installments(self, as_of_date: date) -> List[DriverLoanInstallment]:
        """Get all installments that are due for posting."""
        logger.debug("Fetching due installments", as_of_date=as_of_date)

        stmt = (
            select(DriverLoanInstallment)
            .options(
                selectinload(DriverLoanInstallment.loan)
                .selectinload(DriverLoan.driver)
            )
            .where(
                and_(
                    DriverLoanInstallment.week_start_date <= as_of_date,
                    DriverLoanInstallment.status == "Scheduled",
                )
            )
            .order_by(DriverLoanInstallment.week_start_date)
        )

        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def update_installment(
        self,
        installment: DriverLoanInstallment,
        installment_data: DriverLoanInstallmentUpdate,
    ) -> DriverLoanInstallment:
        """Update an installment."""
        logger.debug("Updating installment", installment_id=installment.installment_id)

        for field, value in installment_data.model_dump(exclude_unset=True).items():
            setattr(installment, field, value)

        await self.db.flush()
        await self.db.refresh(installment)

        return installment
    
    async def mark_installments_due(self, as_of_date: date) -> int:
        """Mark scheduled installments as due"""
        logger.info("Marking installments as due", as_of_date=as_of_date)

        stmt = (
            update(DriverLoanInstallment)
            .where(
                and_(
                    DriverLoanInstallment.week_start_date <= as_of_date,
                    DriverLoanInstallment.status == "Scheduled"
                )
            )
            .values(status="Due")
        )

        result = await self.db.execute(stmt)
        await self.db.flush()

        count = result.rowcount
        logger.info("Installments marked as due", count=count)
        return count
    
    # === Log Operations ===

    async def create_log(self, log_data: DriverLoanLogCreate) -> DriverLoanLog:
        """Create a loan operation log entry."""
        logger.debug("Creating loan log", log_type=log_data.log_type)

        log = DriverLoanLog(
            log_date=log_data.log_date,
            log_type=log_data.log_type,
            loan_id=log_data.loan_id,
            records_impacted=log_data.records_impacted,
            status=log_data.status,
            details=log_data.details,
        )

        self.db.add(log)
        await self.db.flush()
        await self.db.refresh(log)

        logger.info("Loan log created", log_id=log.id, log_type=log.log_type)
        return log
    
    # === Transaction Management ===

    async def commit(self) -> None:
        """Commit the current transaction."""
        await self.db.commit()
        logger.debug("Transaction committed")

    async def rollback(self) -> None:
        """Rollback the current transaction."""
        await self.db.rollback()
        logger.warning("Transaction rolled back")


