# app/repairs/models.py

"""
SQLAlchemy 2.x models for vehicle repairs module
"""

from datetime import date
from typing import Optional

from sqlalchemy import (
    String, Float, Date, Text, ForeignKey, Index,
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.users.models import AuditMixin
from app.repairs.schemas import InvoiceStatus, InstallmentStatus, WorkshopType, StartWeekOption


class RepairInvoice(Base, AuditMixin):
    """
    Model for Repair Invoice Master.
    Represents the overall repair obligation created when a repair is logged.
    """
    __tablename__ = "repair_invoices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    repair_id: Mapped[str] = mapped_column(
        String(48), unique=True, nullable=False, index=True,
        comment="System-generated unique repair ID (e.g., VRPR-2025-001)"
    )
    invoice_number: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Actual invoice number from workshop"
    )
    invoice_date: Mapped[date] = mapped_column(
        Date, nullable=False, comment="Date repair was billed"
    )

    vin: Mapped[str] = mapped_column(
        String(18), nullable=False,
        comment="Vehicle Identification Number"
    )
    plate_number: Mapped[str] = mapped_column(
        String(24), nullable=False, index=True,
        comment="Vehicle plate number"
    )
    medallion_number: Mapped[str] = mapped_column(
        String(24), nullable=False, index=True,
        comment="Medallion associated with repair"
    )
    hack_license_number: Mapped[Optional[str]] = mapped_column(
        String(24), nullable=True, index=True,
        comment="TLC license of responsible driver"
    )

    driver_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("drivers.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="Foreign Key to Driver"
    )
    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles.id", ondelete="RESTRICT"),
        nullable=False, index=True,
        comment="Foreign Key to verhicles"
    )
    medallion_id: Mapped[int] = mapped_column(
        ForeignKey("medallions.id", ondelete="RESTRICT"),
        nullable=False, index=True,
        comment="Foreign Key to medallions"
    )
    lease_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leases.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="Foreign Key to leases table (if associated with active lease)"
    )

    workshop_type: Mapped[WorkshopType] = mapped_column(
        SQLEnum(WorkshopType, native_enum=False, length=48),
        nullable=False, comment="Type of workshop (Big Apple / External)"
    )
    repair_description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Details of repair work performed"
    )

    repair_amount: Mapped[float] = mapped_column(Float, nullable=False, comment="Total cost of repair invoice")
    weekly_installment: Mapped[float] = mapped_column(Float, nullable=False, comment="Weekly installment amount (from payment matrix)")
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, comment="Remaining unpaid balance")

    start_week: Mapped[StartWeekOption] = mapped_column(
        SQLEnum(StartWeekOption, native_enum=False, length=48),
        nullable=False, default=StartWeekOption.CURRENT,
        comment="When repayment schedule begins"
    )

    status: Mapped[InvoiceStatus] = mapped_column(
        SQLEnum(InvoiceStatus, native_enum=False, length=24),
        nullable=False, default=InvoiceStatus.DRAFT,
        index=True, comment="Invoice lifecycle status"
    )

    installments: Mapped[list["RepairInstallment"]] = relationship(
        "RepairInstallment", back_populates="invoice", cascade="all, delete-orphan",
        lazy="selectin"
    )

    # Indexes for performance
    __table_args__ = (
        Index('idx_repair_invoice_driver_status', 'driver_id', 'status'),
        Index('idx_repair_invoice_vehicle_date', 'vehicle_id', 'invoice_date'),
        Index('idx_repair_invoice_medallion_status', 'medallion_id', 'status'),
        Index('idx_repair_invoice_unique', 'invoice_number', 'vehicle_id', 'invoice_date', unique=True),
    )
    
    def __repr__(self):
        return f"<RepairInvoice(repair_id={self.repair_id}, invoice_number={self.invoice_number}, amount={self.repair_amount}, status={self.status})>"
    

class RepairInstallment(Base, AuditMixin):
    """
    Model for Repair Payment Schedule.
    Represents individual weekly installments derived from a Repair Invoice.
    """
    __tablename__ = "repair_installments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    repair_invoice_id: Mapped[int] = mapped_column(
        ForeignKey("repair_invoices.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="Foreign Key to RepairInvoice"
    )
    installment_id: Mapped[str] = mapped_column(
        String(48), nullable=False, unique=True, index=True,
        comment="Unique installment identifier (e.g., VRPR-2025-012-01)"
    )

    week_start_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True,
        comment="Start of payment period (Sunday 00:00:00)"
    )
    week_end_date: Mapped[date] = mapped_column(
        Date, nullable=False,
        comment="End of payment period (Saturday 23:59:59)"
    )

    payment_amount: Mapped[float] = mapped_column(
        Float, nullable=False,
        comment="Installment amount due for this week"
    )
    prior_balance: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Remaining unpaid balance from earlier cycles"
    )
    balance: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        comment="Remaining unpaid portion after this installment"
    )

    ledger_posting_ref: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, index=True,
        comment="Reference to ledger entry (null until posted)"
    )

    status: Mapped[InstallmentStatus] = mapped_column(
        SQLEnum(InstallmentStatus, native_enum=False, length=24),
        nullable=False, default=InstallmentStatus.SCHEDULED,
        index=True, comment="Installment lifecycle status"
    )

    invoice: Mapped["RepairInvoice"] = relationship(
        "RepairInvoice", back_populates="installments"
    )

    # Indexes for performance
    __table_args__ = (
        Index('idx_repair_installment_week', 'week_start_date', 'week_end_date'),
        Index('idx_repair_installment_status_week', 'status', 'week_start_date'),
        Index('idx_repair_installment_invoice_status', 'repair_invoice_id', 'status'),
    )

    def __repr__(self):
        return f"<RepairInstallment(installment_id={self.installment_id}, amount={self.payment_amount}, status={self.status})>"
    
