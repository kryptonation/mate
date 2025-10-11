### app/ezpass/models.py

from datetime import datetime, date, time
from typing import Optional, List

from sqlalchemy import Integer, String, Date, DateTime, Numeric, Text, ForeignKey, Time
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.db import Base
from app.users.models import AuditMixin

class EZPassTransaction(Base, AuditMixin):
    """EZPass Transaction Model using modern SQLAlchemy 2.x syntax."""
    __tablename__ = "ezpass_transactions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    transaction_id: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    transaction_date: Mapped[date] = mapped_column(Date, comment="Original EZPass transaction date")
    transaction_time: Mapped[Optional[time]] = mapped_column(Time)
    posting_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="Date when transaction was posted to BATM")

    medallion_no: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Medallion number of the vehicle")
    driver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("drivers.id"), nullable=True)
    vehicle_id: Mapped[Optional[int]] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    plate_no: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True, comment="Plate number of the vehicle")
    tag_or_plate: Mapped[str] = mapped_column(String(30))

    agency: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    entry_plaza: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    exit_plaza: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0)

    status: Mapped[str] = mapped_column(String(50), default="Imported", comment="Imported, Associated, Posted, Failed")
    associate_failed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    post_failed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    log_id: Mapped[Optional[int]] = mapped_column(ForeignKey("ezpass_logs.id"), nullable=True)

    log: Mapped["EZPassLog"] = relationship(back_populates="transactions")
    driver: Mapped[Optional["Driver"]] = relationship()
    vehicle: Mapped[Optional["Vehicle"]] = relationship()

class EZPassLog(Base, AuditMixin):
    """EZPass Log Model using modern SQLAlchemy 2.x syntax."""
    __tablename__ = "ezpass_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    log_date: Mapped[datetime]
    log_type: Mapped[str] = mapped_column(String(255))
    
    records_impacted: Mapped[Optional[int]]
    success_count: Mapped[Optional[int]]
    unidentified_count: Mapped[Optional[int]]
    status: Mapped[str] = mapped_column(String(50), default="Imported")

    transactions: Mapped[List["EZPassTransaction"]] = relationship(back_populates="log")