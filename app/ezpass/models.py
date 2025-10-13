# app/ezpass/models.py

"""
EZPass models using SQLAlchemy 2.x async style for MySQL
Enhanced to match client CSV format
"""

from datetime import datetime, date, time
from typing import Optional, List

from sqlalchemy import (
    String, Date, DateTime, Numeric, Text, ForeignKey, Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.users.models import AuditMixin


class EZPassTransaction(Base, AuditMixin):
    """
    EZPass Transaction Model using modern SQLAlchemy 2.x syntax.

    Represents individual toll transactions from EZPass system.
    Matches client CSV format with Lane Txn ID, Tag/Plate #, Agency, etc.
    """
    __tablename__ = "ezpass_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    transaction_id: Mapped[Optional[str]] = mapped_column(String(64), index=True, comment="External EZPass transaction ID")
    transaction_date: Mapped[date] = mapped_column(Date, index=True, comment="Transaction date from CSV")
    transaction_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True, comment="Exit Time from CSV")
    posting_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True, comment="Date when transaction was posted to ledger")

    medallion_no: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True, comment="Medallion number from active lease")
    driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drivers.id"), nullable=True, index=True, comment="Associated Driver ID from active lease")
    vehicle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vehicles.id"), nullable=True, index=True, comment="Associated vehicle ID from active lease")
    plate_no: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True, comment="Tag/Plate # from CSV - used for vehicle matching")
    tag_or_plate: Mapped[str] = mapped_column(String(32), comment="Tag or Plate Identifier from CSV")

    agency: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="Agency from CSV (toll agency name)")
    entry_plaza: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="Entry Plaza from CSV")
    exit_plaza: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="Exit Plaza from CSV")
    vehicle_class: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, comment="Class from CSV (vehicle class)")

    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, comment="Amount from CSV (transaction amount)")

    status: Mapped[str] = mapped_column(String(48), default="Imported", index=True, comment="Status: Imported, Associated, Posted, Failed")
    associate_failed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Reason for association failure")
    post_failed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="Reason for posting failure")

    # === Log Reference ===
    log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ezpass_logs.id"), nullable=True, comment="Reference to import log")

    # === Relationships ===
    log: Mapped[Optional["EZPassLog"]] = relationship(back_populates="transactions", lazy="selectin")
    driver: Mapped[Optional["Driver"]] = relationship(lazy="selectin")
    vehicle: Mapped[Optional["Vehicle"]] = relationship(lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<EZPassTransaction(id={self.id}, "
            f"transaction_id={self.transaction_id}, "
            f"plate_no={self.plate_no}, "
            f"amount={self.amount}, "
            f"status={self.status})>"
        )
    

class EZPassLog(Base, AuditMixin):
    """
    EZPass Log Model using modern SQLAlchemy 2.x syntax.
    Tracks import, association, and posting operations for EZPass data.
    """
    __tablename__ = "ezpass_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    log_date: Mapped[datetime] = mapped_column(DateTime, index=True, comment="Date and time of log entry")
    log_type: Mapped[str] = mapped_column(String(32), comment="Type of log entry: Import, Associate, Post")

    records_impacted: Mapped[Optional[int]] = mapped_column(nullable=True, comment="Total number of records affected")
    success_count: Mapped[Optional[int]] = mapped_column(nullable=True, comment="Number of successfully processed records.")
    unidentified_count: Mapped[Optional[int]] = mapped_column(nullable=True, comment="Number of records that could not be processed")

    status: Mapped[str] = mapped_column(String(48), default="Imported", comment="Status: Success, Failure, Partial, Processing")

    # === Relationships ===
    transactions: Mapped[List["EZPassTransaction"]] = relationship(back_populates="log", lazy="selectin")

    def __repr__(self) -> str:
        return (
            f"<EZPassLog(id={self.id}, "
            f"log_type={self.log_type}, "
            f"log_date={self.log_date}, "
            f"status={self.status})>"
        )

