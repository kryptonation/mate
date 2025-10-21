# app/interim_payments/models.py

"""
SQLAlchemy 2.x models for Interim Payments module.

This module handles ad-hoc payments made by drivers outside the weekly DTR cycle.
Payments are captured against drivers and allocated to specific obligations
(Lease, Repair, Loan, EZPass, PVB, Misc) with immediate ledger posting.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    String, Integer, Numeric, Date, DateTime, ForeignKey,
    Index, UniqueConstraint, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.db import Base
from app.users.models import AuditMixin


class InterimPayment(Base, AuditMixin):
    """
    Main Interim Payment record capturing the payment transaction.

    Each interim payment is made by a driver against a specific medallion/lease
    and can be allocated across multiple obligations.
    """
    __tablename__ = "interim_payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    payment_id: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True,
        comment="Unique payment identifier (IMP-YYYY-####)"
    )

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.id", ondelete="RESTRICT"),
        nullable=False, index=True,
        comment="Driver making the payment"
    )
    medallion_id: Mapped[int] = mapped_column(
        ForeignKey("medallions.id", ondelete="RESTRICT"),
        nullable=False, index=True,
        comment="Medallion associated with payment"
    )
    lease_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leases.id", ondelete="SET NULL"),
        nullable=True, index=True,
        comment="Active lease at time of payment (optional)"
    )

    payment_date: Mapped[date] = mapped_column(
        Date, nullable=False, index=True,
        comment="Date when the payment was received"
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False,
        comment="Total payment amount"
    )
    payment_method: Mapped[str] = mapped_column(
        SQLEnum("Cash", "Check", "ACH", name="payment_method_enum"),
        nullable=False,
        comment="Payment method: Cash, Check, ACH"
    )
    check_number: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
        comment="Check number if payment method is check"
    )

    allocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False,
        comment="Total amount allocated across all categories"
    )
    unallocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False,
        comment="Amount not yet allocated (auto-applied to Lease)"
    )

    status: Mapped[str] = mapped_column(
        String(16), default="Completed", nullable=False, index=True,
        comment="Payment status: Completed, Voided, Reversed"
    )
    notes: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True,
        comment="Additional notes or comments"
    )

    receipt_number: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
        comment="Receipt number for this payment"
    )
    receipt_issued_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, comment="When receipt was issued"
    )

    driver: Mapped["Driver"] = relationship(
        "Driver", back_populates="interim_payments", lazy="selectin"
    )
    medallion: Mapped["Medallion"] = relationship(
        "Medallion", lazy="selectin"
    )
    lease: Mapped[Optional["Lease"]] = relationship(
        "Lease", lazy="selectin"
    )

    allocations: Mapped[list["InterimPaymentAllocation"]] = relationship(
        "InterimPaymentAllocation", back_populates="payment",
        cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return (
            f"<InterimPayment(id={self.id}, "
            f"payment_id='{self.payment_id}', "
            f"total_amount={self.total_amount}, "
            f"status='{self.status}')>"
        )

    # Table indexes for query optimization
    __table_args__ = (
        Index("idx_payment_driver_date", "driver_id", "payment_date"),
        Index("idx_payment_medallion_date", "medallion_id", "payment_date"),
        Index("idx_payment_status", "status"),
    )


class InterimPaymentAllocation(Base, AuditMixin):
    """
    Individual allocation of payment to specific obligation.

    Each allocation links a payment to a specific category and reference
    (e.g., Repair Invoice #2456, Loan ID LN-3001, etc.)
    """
    __tablename__ = "interim_payment_allocations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    payment_id: Mapped[int] = mapped_column(
        ForeignKey("interim_payments.id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="Reference to parent payment"
    )

    category: Mapped[str] = mapped_column(
        SQLEnum("Lease", "Repair", "Loan", "EZPass", "PVB", "Misc", name="allocation_category_enum"),
        nullable=False,
        index=True,
        comment="Obligation category"
    )
    reference_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="Reference to specific obligation (Invoice ID, Loan ID, Ticket #m etc.)"
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True,
        comment="Human-readable description of the obligation"
    )

    allocated_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False,
        comment="Amount allocated to this obligation"
    )
    outstanding_before: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False,
        comment="Outstanding balance before payment"
    )
    outstanding_after: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False,
        comment="Outstanding balance after payment"
    )

    ledger_posting_ref: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True,
        comment="Reference to ledger posting entry"
    )
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True,
        comment="When this allocation was posted to ledger"
    )

    payment: Mapped["InterimPayment"] = relationship(
        "InterimPayment", back_populates="allocations"
    )

    def __repr__(self) -> str:
        return (
            f"<InterimPaymentAllocation(id={self.id}, "
            f"category='{self.category}', "
            f"reference_id='{self.reference_id}', "
            f"allocated_amount={self.allocated_amount})>"
        )

    # Table indexes for query optimization
    __table_args__ = (
        Index("idx_allocation_category_ref", "category", "reference_id"),
        Index("idx_allocation_payment", "payment_id"),
    )


class InterimPaymentLog(Base, AuditMixin):
    """
    Audit log for interim payment operations.

    Tracks all payment processing activities including creation,
    allocation changes, voids, and reversals.
    """
    __tablename__ = "interim_payment_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    log_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True,
        comment="When the operation occurred"
    )
    log_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
        comment="Type of operation: Create, Allocate, Void, Reverse"
    )
    payment_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("interim_payments.id", ondelete="CASCADE"),
        nullable=True, index=True, comment="Related payment (if applicable)"
    )

    records_impacted: Mapped[int] = mapped_column(
        default=0, nullable=False, comment="Number of records affected"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="Success",
        index=True, comment="Operation status: Success, Failure, Partial"
    )
    details: Mapped[Optional[str]] = mapped_column(
        String(1024), nullable=True,
        comment="Detailed information about the operation"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True,
        comment="Error message if operation failed"
    )

    def __repr__(self) -> str:
        return (
            f"<InterimPaymentLog(id={self.id}, "
            f"log_type='{self.log_type}', "
            f"status='{self.status}')>"
        )

    # Table indexes
    __table_args__ = (
        Index("idx_log_date_type", "log_date", "log_type"),
        Index("idx_log_status", "status"),
    )



