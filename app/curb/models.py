# app/curb/models.py

"""
SQLAlchemy 2.x models for CURB (Taxi Fleet) module.
"""

from datetime import datetime, timezone, date, time
from typing import Optional

from sqlalchemy import (
    String, Date, Time, DateTime, Float, Boolean, ForeignKey, Text,
    UniqueConstraint, Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.users.models import AuditMixin


class CURBTrip(Base, AuditMixin):
    """
    CURB Trip model representing taxi trip data from the CURB system.

    Stores trip details including location, fare breakdown, payment information,
    and associations to drivers, medallions, and vehicles.
    """
    __tablename__ = "curb_trips"

    __table_args__ = (
        Index('idx_curb_trip_record_period', 'record_id', 'period'),
        Index('idx_curb_trip_dates', 'start_date', 'end_date'),
        Index('idx_curb_trip_cab_driver', 'cab_number', 'driver_id'),
        Index('idx_curb_trip_reconcile', 'is_reconciled', 'is_posted'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    record_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    period: Mapped[Optional[str]] = mapped_column(String(12), nullable=True)
    trip_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    cab_number: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    driver_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)

    trip_amount: Mapped[float] = mapped_column(Float, default=0.0)
    tips: Mapped[float] = mapped_column(Float, default=0.0)
    extras: Mapped[float] = mapped_column(Float, default=0.0)
    tolls: Mapped[float] = mapped_column(Float, default=0.0)
    tax: Mapped[float] = mapped_column(Float, default=0.0)
    imp_tax: Mapped[float] = mapped_column(Float, default=0.0)
    total_amount: Mapped[float] = mapped_column(Float, default=0.0)

    gps_start_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_start_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_end_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_end_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    from_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    to_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    payment_type: Mapped[str] = mapped_column(String(2), nullable=False)
    cc_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    auth_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    auth_amount: Mapped[float] = mapped_column(Float, default=0.0)

    ehail_fee: Mapped[float] = mapped_column(Float, default=0.0)
    health_fee: Mapped[float] = mapped_column(Float, default=0.0)
    congestion_fee: Mapped[float] = mapped_column(Float, default=0.0)
    airport_fee: Mapped[float] = mapped_column(Float, default=0.0)
    cbdt_fee: Mapped[float] = mapped_column(Float, default=0.0)

    passengers: Mapped[int] = mapped_column(default=1)
    distance_service: Mapped[float] = mapped_column(Float, default=0.0)
    distance_bs: Mapped[float] = mapped_column(Float, default=0.0)
    reservation_number: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    is_reconciled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_posted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    recon_stat: Mapped[Optional[int]] = mapped_column(nullable=True)

    status: Mapped[str] = mapped_column(String(48), nullable=False, default="Imported", index=True)
    associate_failed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    post_failed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    import_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("curb_import_logs.id", ondelete="SET NULL"), nullable=True
    )
    driver_fk: Mapped[Optional[int]] = mapped_column(
        ForeignKey("drivers.id", ondelete="SET NULL"), nullable=True
    )
    medallion_fk: Mapped[Optional[int]] = mapped_column(
        ForeignKey("medallions.id", ondelete="SET NULL"), nullable=True
    )
    vehicle_fk: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )

    import_log: Mapped["CURBImportLog"] = relationship("CURBImportLog", back_populates="trips")
    reconciliation: Mapped[Optional["CURBTripReconciliation"]] = relationship(
        "CURBTripReconciliation", back_populates="trip", uselist=False
    )
    driver: Mapped[Optional["Driver"]] = relationship("Driver", foreign_keys=[driver_fk])
    medallion: Mapped[Optional["Medallion"]] = relationship("Medallion", foreign_keys=[medallion_fk])
    vehicle: Mapped[Optional["Vehicle"]] = relationship("Vehicle", foreign_keys=[vehicle_fk])

    def __repr__(self) -> str:
        return f"<CURBTrip(id={self.id}, record_id={self.record_id}, cab={self.cab_number})>"
    

class CURBImportLog(Base, AuditMixin):
    """
    CURB Import Log for tracking import operations.
    """
    __tablename__ = "curb_import_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    import_source: Mapped[str] = mapped_column(String(64), nullable=False)
    imported_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")

    import_start: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    import_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    total_records: Mapped[int] = mapped_column(default=0)
    success_count: Mapped[int] = mapped_column(default=0)
    failure_count: Mapped[int] = mapped_column(default=0)
    duplicate_count: Mapped[int] = mapped_column(default=0)

    status: Mapped[str] = mapped_column(String(32), default="IN_PROGRESS", index=True)
    error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    trips: Mapped[list["CURBTrip"]] = relationship("CURBTrip", back_populates="import_log")

    def __repr__(self) -> str:
        return f"<CURBImportLog(id={self.id}, status={self.status}, records={self.total_records})>"
    

class CURBTripReconciliation(Base, AuditMixin):
    """
    CURB Trip Reconciliation tracking.
    Records when trips are marked as reconciled with the CURB system.
    """
    __tablename__ = "curb_trip_reconciliation"

    __table_args__ = (
        UniqueConstraint('trip_id', name='uq_trip_reconciliation'),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    trip_id: Mapped[int] = mapped_column(
        ForeignKey("curb_trips.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    recon_stat: Mapped[int] = mapped_column(nullable=False, index=True)
    
    reconciled_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    reconciled_by: Mapped[str] = mapped_column(String(64), default="SYSTEM")

    trip: Mapped["CURBTrip"] = relationship("CURBTrip", back_populates="reconciliation")

    def __repr__(self) -> str:
        return f"<CURBTripReconciliation(id={self.id}, trip_id={self.trip_id}, recon_stat={self.recon_stat})>"
    

