# app/pvb/models.py

"""
SQLAlchemy 2.x models for PVB (Parking Violation Bureau) module.
"""

from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    Integer, String, Date, DateTime, Text, ForeignKey, Boolean,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.users.models import AuditMixin


class PVBViolation(Base, AuditMixin):
    """
    PVB Violation model representing parking violations.

    Stores violation details including plate information, dates, amounts,
    and associations to drivers, medallions, and vehicles.
    """
    __tablename__ = "pvb_violations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    plate_number: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    vehicle_type: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    summons_number: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, unique=True, index=True
    )

    issue_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    issue_time: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    amount_due: Mapped[int] = mapped_column(default=0)
    amount_paid: Mapped[int] = mapped_column(default=0)

    driver_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    medallion_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("medallions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vehicle_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    log_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("pvb_logs.id", ondelete="SET NULL"), nullable=True
    )

    status: Mapped[str] = mapped_column(
        String(48), nullable=False, default="Imported", index=True
    )
    associated_failed_reason: Mapped[str] = mapped_column(Text, nullable=True)
    post_failed_reason: Mapped[str] = mapped_column(Text, nullable=True)

    log: Mapped["PVBLog"] = relationship("PVBLog", back_populates="violations")
    driver: Mapped["Driver"] = relationship("Driver", foreign_keys=[driver_id])
    medallion: Mapped["Medallion"] = relationship("Medallion", foreign_keys=[medallion_id])
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", foreign_keys=[vehicle_id])

    def __repr__(self) -> str:
        return f"<PVBViolation(id={self.id}, plate={self.plate_number}, summons={self.summons_number})>"
    

class PVBLog(Base, AuditMixin):
    """
    PVB Log for tracking import, association, and posting operations.
    """
    __tablename__ = "pvb_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    log_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True,
    )
    log_type: Mapped[str] = mapped_column(
        String(48), nullable=False, index=True,
        comment="Type of operation: Import, Associate, Post"
    )

    records_impacted: Mapped[int] = mapped_column(Integer, nullable=True)
    success_count: Mapped[int] = mapped_column(Integer, nullable=True, default=0)
    unidentified_count: Mapped[int] = mapped_column(Integer, nullable=True, default=0)

    status: Mapped[str] = mapped_column(
        String(48), nullable=False, default="Pending",
        comment="Status: Pending, Success, Failure, Partial"
    )

    violations: Mapped[List["PVBViolation"]] = relationship(
        "PVBViolation", back_populates="log"
    )

    def __repr__(self) -> str:
        return f"<PVBLog(id={self.id}, type={self.log_type}, date={self.log_date})>"
    
