# app/ledger/models.py

"""
Centralized ledger models - SQLAlchemy 2.x

Implements the dual-table ledger system:
- Ledger_Postings: Immutable audit trail of all transactions.
- Ledger_Balances: Rolling outstanding balances per obligation.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import (
    String, Numeric, DateTime, Date, Index, ForeignKey,
    Enum as SQLEnum, Text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.users.models import AuditMixin


# === Enums ===

class LedgerCategory(str, PyEnum):
    """Obligation/earning categories in the ledger."""
    LEASE = "Lease"
    REPAIR = "Repair"
    LOAN = "Loan"
    EZPASS = "EZPass"
    PVB = "PVB"
    TLC = "TLC"
    TAXES = "Taxes"
    MISC = "Misc"
    EARNINGS = "Earnings"
    INTERIM_PAYMENT = "InterimPayment"
    DEPOSIT = "Deposit"


class LedgerEntryType(str, PyEnum):
    """Entry type for double-entry bookkeeping."""
    DEBIT = "Debit"
    CREDIT = "Credit"


class LedgerStatus(str, PyEnum):
    """Status of ledger entries"""
    POSTED = "Posted"
    VOIDED = "Voided"


class BalanceStatus(str, PyEnum):
    """Status of ledger balances"""
    OPEN = "Open"
    CLOSED = "Closed"


# === Ledger_Postings Model ===

class LedgerPosting(Base, AuditMixin):
    """
    Immutable record of every financial transaction.

    Core Principles:
    - One posting per event (earnings, obligations, payments, reversals)
    - Never edited or deleted after creation
    - Corrections via reversal entries
    - Full audit trail of all financial activity

    Every posting updates corresponding Ledger_Balances in real-time.
    """
    __tablename__ = "ledger_postings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    posting_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        comment="Unique posting identifier (e.g., POST-20251021-001234)"
    )

    # === Category and Classification ===
    category: Mapped[str] = mapped_column(
        SQLEnum(
            "Lease", "Repair", "Loan", "EZPass", "PVB", "TLC",
            "Taxes", "Misc", "Earnings", "InterimPayment", "Deposit",
            name="ledger_category_enum"
        ),
        nullable=False, index=True, comment="Obligation or earning type"
    )

    # === Double entry fields ===
    entry_type: Mapped[str] = mapped_column(
        SQLEnum("Debit", "Credit", name="ledger_entry_type_enum"),
        nullable=False, comment="DEBIT = obligation, CREDIT = earning/payment"
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Dollar value (always positive; entry_type determines debit/credit)"
    )

    # === Entity Linkage (Multi-Entity Support) ===
    driver_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=True, index=True, comment="Driver reference"
    )

    vehicle_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="Vehicle reference"
    )

    vin: Mapped[Optional[str]] = mapped_column(
        String(17), nullable=True, index=True,
        comment="Vehicle VIN for filtering/reconciliation"
    )

    plate: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, index=True,
        comment="Vehicle plate for filtering/reconciliation"
    )

    medallion_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medallions.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="Medallion reference"
    )

    lease_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leases.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="Lease reference"
    )

    # === Source Traceability ===
    reference_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Source record ID (Lease ID, Repair Invoice ID, Loan ID, Trip ID, etc.)"
    )

    reference_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
        comment="Type of source record for clarity"
    )

    # === Status and Lifecycle ===
    status: Mapped[str] = mapped_column(
        SQLEnum("Posted", "Voided", name="ledger_status_enum"),
        default="Posted", nullable=False, index=True,
        comment="POSTED = active, VOIDED = neutralized by reversal"
    )

    voided_by_posting_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True,
        comment="Posting ID that voided this entry"
    )

    # === Posting Metadata ===
    posted_on: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True,
        comment="Timestamp when entry was posted"
    )

    transaction_date: Mapped[Optional[Date]] = mapped_column(
        Date, nullable=True, index=True,
        comment="Business date of the transaction"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Human-readable description"
    )

    # === Relationships ===
    driver: Mapped[Optional["Driver"]] = relationship(
        "Driver", lazy="select"
    )
    vehicle: Mapped[Optional["Vehicle"]] = relationship(
        "Vehicle", lazy="select"
    )
    medallion: Mapped[Optional["Medallion"]] = relationship(
        "Medallion", lazy="select"
    )
    lease: Mapped[Optional["Lease"]] = relationship(
        "Lease", lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LedgerPosting(id={self.id}, posting_id='{self.posting_id}', "
            f"category='{self.category}', entry_type='{self.entry_type}', "
            f"amount={self.amount})>"
        )
    
    # Indexes for query optimization
    __table_args__ = (
        Index("idx_posting_category_driver", "category", "driver_id"),
        Index("idx_posting_driver_date", "driver_id", "transaction_date"),
        Index("idx_posting_reference", "reference_type", "reference_id"),
        Index("idx_posting_status_date", "status", "posted_on"),
    )


# === Ledger_Balances Model ===

class LedgerBalance(Base, AuditMixin):
    """
    Rolling snapshot of each obligation until cleared

    Core Principles:
    - One balance line per obligation (Reference_ID)
    - Updated by Ledger_Postings (never manually)
    - Remains OPEN until fully settled
    - Marked CLOSED when Balance = 0 (retained for audit)
    - Tracks payment history via Applied_Payment_Refs
    """
    __tablename__ = "ledger_balances"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    balance_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        comment="Unique balance identifier (e.g., BAL-RPR-20251021-001234)"
    )

    # === Category and Classification ===
    category: Mapped[str] = mapped_column(
        SQLEnum(
            "Lease", "Repair", "Loan", "EZPass", "PVB", "TLC",
            "Taxes", "Misc", "Deposit", name="balance_category_enum"
        ),
        nullable=False, index=True, comment="Obligation type (no Earnings in balances)"
    )

    # === Entity Linkage ===
    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.id", ondelete="CASCADE"),
        nullable=False, index=True,
        comment="Driver reference (required)"
    )

    vehicle_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="Vehicle reference"
    )

    vin: Mapped[Optional[str]] = mapped_column(
        String(18), nullable=True, index=True,
        comment="Vehicle VIN"
    )

    plate: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, index=True,
        comment="Vehicle plate"
    )

    medallion_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medallions.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="Medallion reference"
    )

    lease_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("leases.id", ondelete="SET NULL"),
        nullable=True, index=True, comment="Lease reference"
    )

    # === Source Traceability ===
    reference_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        comment="Source obligation (Repair Invoice ID, Loan ID, Toll ID, Ticket ID, etc.)"
    )

    reference_type: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True,
        comment="Type of source for clarity"
    )

    # === Balance Tracking ===
    original_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False,
        comment="Total obligation from source (immutable)"
    )

    prior_balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False,
        comment="Carried over unpaid portion from previous cycle(s)"
    )

    payment: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False,
        comment="Amount settled this cycle"
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, index=True,
        comment="Remaining unpaid portion (updated after each payment/allocation)"
    )

    # === Payment References ===
    applied_payment_refs: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="JSON array of payment IDs applied (Interim Payment ID, Earnings Batch ID)"
    )

    # === Status and Lifecycle ===
    status: Mapped[str] = mapped_column(
        SQLEnum("Open", "Closed", name="balance_status_enum"),
        default="Open", nullable=False, index=True,
        comment="OPEN = unpaid, CLOSED = fully settled (Balance = 0)"
    )

    # === Dates ===
    obligation_date: Mapped[Optional[Date]] = mapped_column(
        Date, nullable=True, index=True,
        comment="Date obligation was created"
    )

    due_date: Mapped[Optional[Date]] = mapped_column(
        Date, nullable=True, index=True,
        comment="Due date for payment"
    )

    closed_on: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True,
        comment="When balance was fully settled"
    )

    updated_on: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True,
        comment="Timestamp of last update"
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True,
        comment="Human-readable description"
    )

    # === Relationships ===
    driver: Mapped["Driver"] = relationship(
        "Driver", lazy="select"
    )
    vehicle: Mapped[Optional["Vehicle"]] = relationship(
        "Vehicle", lazy="select"
    )
    medallion: Mapped[Optional["Medallion"]] = relationship(
        "Medallion", lazy="select"
    )
    lease: Mapped[Optional["Lease"]] = relationship(
        "Lease", lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LedgerBalance(id={self.id}, balance_id='{self.balance_id}', "
            f"category='{self.category}', balance={self.balance}, "
            f"status='{self.status}')>"
        )
    
    # Indexes for query optimization
    __table_args__ = (
        Index("idx_balance_category_driver", "category", "driver_id"),
        Index("idx_balance_driver_status", "driver_id", "status"),
        Index("idx_balance_reference", "reference_type", "reference_id"),
        Index("idx_balance_status_date", "status", "obligation_date"),
        Index("idx_balance_driver_category_status", "driver_id", "category", "status"),
    )