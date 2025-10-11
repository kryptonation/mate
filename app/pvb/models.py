### app/pvb/models.py

# Third party imports
from sqlalchemy import (
    Column, Integer, String, Date, Time, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import relationship

# Local imports
from app.core.db import Base
from app.users.models import AuditMixin


class PVBViolation(Base, AuditMixin):
    """PVB Violation model"""
    __tablename__ = "pvb_violations"

    id = Column(Integer, primary_key=True, index=True)
    plate_number = Column(String(64), nullable=False, index=True)
    state = Column(String(2), nullable=False)
    vehicle_type = Column(String(24), nullable=False)
    summons_number = Column(String(32), nullable=True, unique=True)
    issue_date = Column(Date, nullable=False)
    issue_time = Column(String(16), nullable=True)

    amount_due = Column(Integer, nullable=True)
    amount_paid = Column(Integer, nullable=True, default=0)

    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=True)
    medallion_id = Column(Integer, ForeignKey("medallions.id"), nullable=True)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=True)

    status = Column(String(50), nullable=False, default="Imported")
    associated_failed_reason = Column(Text, nullable=True)
    post_failed_reason = Column(Text, nullable=True)

    log_id = Column(Integer, ForeignKey("pvb_logs.id"), nullable=True)

    # Relationships
    log = relationship("PVBLog", back_populates="violations")


class PVBLog(Base, AuditMixin):
    """PVB Log model"""
    __tablename__ = "pvb_logs"

    id = Column(Integer, primary_key=True, index=True)
    log_date = Column(DateTime, nullable=False)
    log_type = Column(String(50), nullable=False)
    records_impacted = Column(Integer, nullable=True)
    success_count = Column(Integer, nullable=True, default=0)
    unidentified_count = Column(Integer, nullable=True, default=0)
    status = Column(String(50), nullable=False)

    violations = relationship("PVBViolation", back_populates="log")