## app/curb/models.py

"""
CURB Trip Models

This module contains the SQLAlchemy models for CURB trips.
"""
# Standard library imports
from datetime import datetime

# Third party imports
from sqlalchemy import (
    Column, Integer, String, Date, Float, Boolean, ForeignKey, Time , DateTime,
    Text
)
from sqlalchemy.orm import relationship

# Local imports
from app.core.db import Base


class CURBTrip(Base):
    """Model for CURB trips."""
    __tablename__ = "curb_trips"

    id = Column(Integer, primary_key=True, index=True)

    record_id = Column(String(32), nullable=False, index=True)
    period = Column(String(12), nullable=True)
    trip_number = Column(String(32), nullable=True)
    cab_number = Column(String(16), nullable=False)
    driver_id = Column(String(32), nullable=False)

    start_date = Column(Date)
    end_date = Column(Date)
    start_time = Column(Time)
    end_time = Column(Time)

    trip_amount = Column(Float)
    tips = Column(Float)
    extras = Column(Float)
    tolls = Column(Float)
    tax = Column(Float)
    imp_tax = Column(Float)
    total_amount = Column(Float)

    gps_start_lat = Column(Float)
    gps_start_lon = Column(Float)
    gps_end_lat = Column(Float)
    gps_end_lon = Column(Float)

    from_address = Column(String(255))
    to_address = Column(String(255))
    payment_type = Column(String(2)) # T = Cash, P = private, C = Creit Card
    cc_number = Column(String(32))
    auth_code = Column(String(32))
    auth_amount = Column(Float)

    ehail_fee = Column(Float)
    health_fee = Column(Float)
    passengers = Column(Integer)
    distance_service = Column(Float)
    distance_bs = Column(Float)
    reservation_number = Column(String(64))
    congestion_fee = Column(Float)
    airport_fee = Column(Float)
    cbdt_fee = Column(Float)

    imported_at = Column(DateTime, default=datetime.now)
    is_reconciled = Column(Boolean, default=False)
    is_posted = Column(Boolean, default=False)
    recon_stat = Column(Integer)

    import_id = Column(Integer, ForeignKey("curb_import_logs.id"))
    import_log = relationship("CURBImportLog", back_populates="trips")
    reconcilation_entry = relationship(
    "CURBTripReconcilation",
    back_populates="trip")


class CURBImportLog(Base):
    """Model for CURB import logs."""
    __tablename__ = "curb_import_logs"

    id = Column(Integer, primary_key=True, index=True)
    imported_by = Column(String(64), default="SYSTEM")
    import_start = Column(DateTime, default=datetime.now)
    import_end = Column(DateTime)
    import_source = Column(String(64)) # SOAP, Upload, etc
    total_records = Column(Integer, default=0)
    status = Column(String(32), default="IN_PROGRESS")
    error_summary = Column(Text)

    trips = relationship("CURBTrip", back_populates="import_log")


class CURBTripReconcilation(Base):
    """Model for CURB trip reconcilation."""
    __tablename__ = "curb_trip_reconcilation"

    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("curb_trips.id"), nullable=False)
    recon_stat = Column(Integer, nullable=False)
    reconciled_at = Column(DateTime, default=datetime.now)
    reconciled_by = Column(String(64), default="SYSTEM")

    trip = relationship("CURBTrip", back_populates="reconcilation_entry")