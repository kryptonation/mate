# app/driver_loans/models.py

"""
SQLAlchemy 2.x models for Driver Loan Module.
"""

from datetime import datetime, date
from typing import Optional, List
from decimal import Decimal

from sqlalchemy import (
    String, Date, DateTime, Numeric, Text, ForeignKey,
    UniqueConstraint, Index, CheckConstraint,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.db import Base
from app.users.models import AuditMixin


class DriverLoan(Base, AuditMixin):
    """
    Driver loan model representing the master loan record.

    Tracks the lifecycle of personal loans extended to drivers by BAT,
    including principal, interest rates, and repayment status.
    """
    __tablename__ = "driver_loans"

    __table_args__ = (
        Index('idx_driver_loan_status', 'status'),
        Index('idx_driver_loan_driver', 'driver_id', 'status'),
        Index('idx_driver_loan_medallion', 'medallion_id'),
        CheckConstraint('loan_amount >= 1', name='check_loan_amount_positive'),
        CheckConstraint('interest_rate >= 0 AND interest_rate <= 20', name='check_interest_rate_range'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    loan_id: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="RESTRICT"), nullable=False)
    medallion_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medallions.id", ondelete="SET NULL"), nullable=True
    )
    lease_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leases.id", ondelete="SET NULL"),
        nullable=True,
    )

    loan_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="Principal loan amount")
    interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0.0, nullable=False, comment="Annual interest rate percentage")

    loan_date: Mapped[date] = mapped_column(Date, nullable=False, comment="Date when loan was disbursed")
    start_week: Mapped[date] = mapped_column(Date, nullable=False, comment="Sunday of the week when repayments start")

    purpose: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Reason for the loan")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Additional notes about the loan")

    status: Mapped[str] = mapped_column(String(16), default="Draft", nullable=False, comment="Lifecycle state: Draft, Open, Closed, Hold, Cancelled")
    total_principal_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0, nullable=False, comment="Total principal paid")
    total_interest_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0, nullable=False, comment="Total interest paid")
    outstanding_balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0, nullable=False, comment="Remaining principal balance")

    driver: Mapped["Driver"] = relationship("Driver", foreign_keys=[driver_id], lazy="selectin")
    medallion: Mapped[Optional["Medallion"]] = relationship("Medallion", foreign_keys=[medallion_id], lazy="selectin")
    lease: Mapped[Optional["Lease"]] = relationship("Lease", foreign_keys=[lease_id], lazy="selectin")
    installments: Mapped[List["DriverLoanInstallment"]] = relationship(
        "DriverLoanInstallment",
        back_populates="loan",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="DriverLoanInstallment.week_start_date"
    )

    def __repr__(self) -> str:
        return (
            f"<DriverLoan(id={self.id}, "
            f"loan_id={self.loan_id}, "
            f"driver_id={self.driver_id}, "
            f"amount={self.loan_amount}, "
            f"status={self.status})>"
        )
    

class DriverLoanInstallment(Base, AuditMixin):
    """
    Driver Loan Installment model representing scheduled weekly payments.

    Tracks individual installments with principal and interest components,
    aligned with BAT's weekly payment periods.
    """
    __tablename__ = "driver_loan_installments"

    __table_args__ = (
        UniqueConstraint('loan_id', 'installment_number', name='uq_loan_installment'),
        Index('idx_installment_status', 'status'),
        Index('idx_installment_dates', 'week_start_date', 'week_end_date'),
        Index('idx_installment_loan', 'loan_id', 'status'),
    )
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    installment_id: Mapped[str] = mapped_column(String(48), unique=True, nullable=False)
    loan_id: Mapped[int] = mapped_column(
        ForeignKey("driver_loans.id", ondelete="CASCADE"),
        nullable=False,
        comment="Reference to the parent loan"
    )
    installment_number: Mapped[int] = mapped_column(nullable=False, comment="Sequential installment number")

    week_start_date: Mapped[date] = mapped_column(Date, nullable=False, comment="Start date of payment period")
    week_end_date: Mapped[date] = mapped_column(Date, nullable=False, comment="End date of payment period")

    principal_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="Weekly portion from Loan repayment")
    interest_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0, nullable=False, comment="Interest accrued for this period")
    total_due: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="Total amount due (Principal + Interest)")

    prior_balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0, nullable=False, comment="Remaining unpaid principal from earlier cycles")
    outstanding_principal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="Outstanding principal before this installment")
    remaining_balance: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="Remaining principal after this installment")

    status: Mapped[str] = mapped_column(String(16), default="Scheduled", nullable=False, comment="Lifecycle state: Scheduled, Due, Posted, Paid")
    posting_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="DateTime when installment was posted to ledger")
    ledger_posting_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="Ledger Entry ID created when installment is posted")

    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0.0, nullable=False, comment="Amount paid against this installment")
    payment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=False, comment="Date when payment was received")

    loan: Mapped["DriverLoan"] = relationship("DriverLoan", back_populates="installments", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<DriverLoanInstallment(id={self.id}, "
            f"installment_id={self.installment_id}, "
            f"total_due={self.total_due}, "
            f"status={self.status})>"
        )
    

class DriverLoanLog(Base, AuditMixin):
    """
    Driver Loan log for tracking loan operations.

    Maintains audit trail of loan creation, schedule generation,
    posting operations, and status changes.
    """
    __tablename__ = "driver_loan_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    log_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True, comment="Date and Time of log entry")
    log_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="Type of log: Create, Schedule, Post, StatusChange, Adjustment")
    loan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("driver_loans.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to loan if applicable"
    )
    records_impacted: Mapped[Optional[int]] = mapped_column(nullable=True, comment="Number of records affected")
    status: Mapped[str] = mapped_column(String(48), default="Success", nullable=False, comment="Status: Success, Failure, Partial")
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Additional details about the operation")

    loan: Mapped[Optional["DriverLoan"]] = relationship("DriverLoan", foreign_keys=[loan_id], lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<DriverLoanLog(id={self.id}, "
            f"log_type={self.log_type}, "
            f"log_date={self.log_date}, "
            f"status={self.status})>"
        )
