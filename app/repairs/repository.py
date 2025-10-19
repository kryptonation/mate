# app/repairs/repository.py

"""
Data Access Layer for Vehicle Repairs module.
Handles all database interactions using async SQLAlchemy 2.x patterns.
"""

from typing import List, Optional, Tuple
from datetime import date

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.repairs.models import RepairInvoice, RepairInstallment
from app.repairs.schemas import (
    RepairInvoiceFilters, RepairInstallmentFilters,
    InvoiceStatus, InstallmentStatus,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RepairRepository:
    """
    Repository for Repair Invoice and Installment data access.
    Provides async database operations following the repository pattern.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==== Repair Invoice Operations ====

    async def create_invoice(self, invoice: RepairInvoice) -> RepairInvoice:
        """Create a new repair invoice."""
        self.db.add(invoice)
        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice
    
    async def get_invoice_by_id(self, invoice_id: int) -> Optional[RepairInvoice]:
        """Get repair invoice by ID with installments loaded."""
        stmt = select(RepairInvoice).options(
            selectinload(RepairInvoice.installments)
        ).where(RepairInvoice.id == invoice_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_invoice_by_repair_id(self, repair_id: str) -> Optional[RepairInvoice]:
        """Get repair invoice by repair_id"""
        stmt = select(RepairInvoice).options(
            selectinload(RepairInvoice.installments)
        ).where(RepairInvoice.repair_id == repair_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def check_duplicate_invoice(
        self, invoice_number: str, vehicle_id: int, invoice_date: date
    ) -> bool:
        """Check if invoice already exists for same vehicle and date."""
        stmt = select(func.count(RepairInvoice.id)).where(
            and_(
                RepairInvoice.invoice_number == invoice_number,
                RepairInvoice.vehicle_id == vehicle_id,
                RepairInvoice.invoice_date == invoice_date,
            )
        )
        result = await self.db.execute(stmt)
        count = result.scalar_one()
        return count > 0
    
    async def get_next_repair_sequence(self, year: int) -> int:
        """Get next sequence number for repair ID generation."""
        stmt = select(func.count(RepairInvoice.id)).where(
            func.year(RepairInvoice.invoice_date) == year
        )
        result = await self.db.execute(stmt)
        count = result.scalar_one()
        return count + 1
    
    async def update_invoice(self, invoice: RepairInvoice) -> RepairInvoice:
        """Update an existing repair invoice."""
        await self.db.flush()
        await self.db.refresh(invoice)
        return invoice
    
    async def get_invoices_paginated(
        self, filters: RepairInvoiceFilters,
        page: int = 1, per_page: int = 50,
        sort_by: str = "created_on",
        sort_order: str = "desc"
    ) -> Tuple[List[RepairInvoice], int]:
        """Get paginated list of repair invoices with filters."""
        # === Build base query ===
        stmt = select(RepairInvoice)

        # Apply filters
        conditions = []
        if filters.status:
            conditions.append(RepairInvoice.status == filters.status)
        if filters.workshop_type:
            conditions.append(RepairInvoice.workshop_type == filters.workshop_type)
        if filters.driver_id:
            conditions.append(RepairInvoice.driver_id == filters.driver_id)
        if filters.vehicle_id:
            conditions.append(RepairInvoice.vehicle_id == filters.vehicle_id)
        if filters.medallion_id:
            conditions.append(RepairInvoice.medallion_id == filters.medallion_id)
        if filters.invoice_number:
            conditions.append(RepairInvoice.invoice_number.ilike(f"%{filters.invoice_number}%"))
        if filters.from_date:
            conditions.append(RepairInvoice.invoice_date >= filters.from_date)
        if filters.to_date:
            conditions.append(RepairInvoice.invoice_date <= filters.to_date)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        
        # Apply sorting
        sort_column = getattr(RepairInvoice, sort_by, RepairInvoice.created_on)
        if sort_order == "desc":
            stmt = stmt.order_by(desc(sort_column))
        else:
            stmt = stmt.order_by(sort_column)
        
        # Apply pagination
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        
        # Execute query
        result = await self.db.execute(stmt)
        invoices = result.scalars().all()
        
        return invoices, total
    
    async def get_invoices_by_status(
        self, status: InvoiceStatus,
        limit: Optional[int] = None
    ) -> List[RepairInvoice]:
        """Get all repair invoices with specific status."""
        stmt = select(RepairInvoice).where(RepairInvoice.status == status)
        if limit:
            stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_invoices_by_driver(
        self, driver_id: int,
        status: Optional[InvoiceStatus] = None
    ) -> List[RepairInvoice]:
        """Get all repair invoices for a specific driver."""
        conditions = [RepairInvoice.driver_id == driver_id]
        if status:
            conditions.append(RepairInvoice.status == status)

        stmt = select(RepairInvoice).where(and_(*conditions))
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    # === Repair Installment Operations ====

    async def create_installments(
        self, installments: List[RepairInstallment]
    ) -> List[RepairInstallment]:
        """Bulk create repair installments."""
        self.db.add_all(installments)
        await self.db.flush()
        return installments
    
    async def get_installment_by_id(self, installment_id: int) -> Optional[RepairInstallment]:
        """Get installment by ID."""
        stmt = select(RepairInstallment).where(RepairInstallment.id == installment_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_installment_by_installment_id(
        self, installment_id: str
    ) -> Optional[RepairInstallment]:
        """Get installment by installment_id string."""
        stmt = select(RepairInstallment).where(
            RepairInstallment.installment_id == installment_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def get_installments_by_invoice(
        self, repair_invoice_id: int
    ) -> List[RepairInstallment]:
        """Get all installments for a repair invoice."""
        stmt = select(RepairInstallment).where(
            RepairInstallment.repair_invoice_id == repair_invoice_id
        ).order_by(RepairInstallment.week_start_date)
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_installments_due_for_posting(
        self, current_date: date
    ) -> List[RepairInstallment]:
        """Get installments that should be posted (status=Scheduled, week has started)"""
        stmt = select(RepairInstallment).options(
            selectinload(RepairInstallment.invoice)
        ).where(
            and_(
                RepairInstallment.status == InstallmentStatus.SCHEDULED,
                RepairInstallment.week_start_date <= current_date,
            )
        ).order_by(RepairInstallment.week_start_date)

        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def update_installment(self, installment: RepairInstallment) -> RepairInstallment:
        """Update an existing installment."""
        await self.db.flush()
        await self.db.refresh(installment)
        return installment
    
    async def get_installments_paginated(
        self, filters: RepairInstallmentFilters,
        page: int = 1, per_page: int = 50,
        sort_by: str = "week_start_date",
        sort_order: str = "desc"
    ) -> Tuple[List[RepairInstallment], int]:
        """Get paginated list of installments with filters."""
        # Build base query
        stmt = select(RepairInstallment)
        
        # Apply filters
        conditions = []
        if filters.repair_invoice_id:
            conditions.append(RepairInstallment.repair_invoice_id == filters.repair_invoice_id)
        if filters.status:
            conditions.append(RepairInstallment.status == filters.status)
        if filters.week_start_date:
            conditions.append(RepairInstallment.week_start_date == filters.week_start_date)
        if filters.week_end_date:
            conditions.append(RepairInstallment.week_end_date == filters.week_end_date)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar_one()
        
        # Apply sorting
        sort_column = getattr(RepairInstallment, sort_by, RepairInstallment.week_start_date)
        if sort_order == "desc":
            stmt = stmt.order_by(desc(sort_column))
        else:
            stmt = stmt.order_by(sort_column)
        
        # Apply pagination
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)
        
        # Execute query
        result = await self.db.execute(stmt)
        installments = result.scalars().all()
        
        return installments, total
    
    async def get_installments_by_status(
        self, status: InstallmentStatus,
        limit: Optional[int] = None
    ) -> List[RepairInstallment]:
        """Get installments by status."""
        stmt = select(RepairInstallment).where(RepairInstallment.status == status)
        if limit:
            stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    # === Statistics and Reporting ===

    async def get_invoice_statistics(self) -> dict:
        """Get statistics about repair invoices."""
        # === Total invoices by status ===
        status_stmt = select(
            RepairInvoice.status,
            func.count(RepairInvoice.id).label("count"),
            func.sum(RepairInvoice.repair_amount).label("total_amount"),
            func.sum(RepairInvoice.balance).label("total_balance")
        ).group_by(RepairInvoice.status)

        status_result = await self.db.execute(status_stmt)
        status_data = status_result.all()

        stats = {
            "by_status": [
                {
                    "status": row.status.value,
                    "count": row.count,
                    "total_amount": float(row.total_amount or 0),
                    "total_balance": float(row.total_balance or 0)
                }
                for row in status_data
            ]
        }

        return stats
    
    async def get_driver_repair_summary(self, driver_id: int) -> dict:
        """Get repair summary for a specific driver."""
        # === Total amounts ===
        summary_stmt = select(
            func.count(RepairInvoice.id).label("total_invoices"),
            func.sum(RepairInvoice.repair_amount).label("total_amount"),
            func.sum(RepairInvoice.balance).label("outstanding_balance")
        ).where(
            and_(
                RepairInvoice.driver_id == driver_id,
                RepairInvoice.status.in_([InvoiceStatus.OPEN, InvoiceStatus.HOLD])
            )
        )

        result = await self.db.execute(summary_stmt)
        row = result.one()

        return {
            "driver_id": driver_id,
            "total_invoices": row.total_invoices or 0,
            "total_amount": float(row.total_amount or 0),
            "outstanding_balance": float(row.outstanding_balance or 0)
        }


