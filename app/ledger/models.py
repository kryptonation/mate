### app/ledger/models.py

# Third party imports
from sqlalchemy import (
    Column, Integer, String, Enum, Numeric, Boolean, ForeignKey,
    Float, DateTime , Date , Time
)
from sqlalchemy.orm import relationship

# Local imports
from app.core.db import Base
from app.users.models import AuditMixin
from app.ledger.schemas import LedgerSourceType, DTRStatus
from app.utils.s3_utils import s3_utils
from app.utils.general import generate_alphanumeric_code


class LedgerEntry(Base, AuditMixin):
    """Leger entry model"""
    __tablename__ = "ledger_entries"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer,ForeignKey("drivers.id"), nullable=True)
    medallion_id = Column(Integer,ForeignKey("medallions.id"),nullable=True)
    vehicle_id = Column(Integer,ForeignKey("vehicles.id"),nullable=True)

    amount = Column(Numeric(10, 2), nullable=True)
    debit = Column(Boolean, default=False)
    description = Column(String(255), nullable=True)
    receipt_number = Column(String(255), nullable=True)
    transaction_date = Column(Date, nullable=True)
    transaction_time = Column(Time, nullable=True)

    source_type = Column(Enum(LedgerSourceType),nullable=True)
    source_id = Column(Integer, nullable=True)
    ledger_id = Column(String(255) , nullable=True)
    driver = relationship("Driver", back_populates="ledger_entries")
    medallion = relationship("Medallion", back_populates="ledger_entries")
    vehicle = relationship("Vehicle", back_populates="ledger_entries")

    def to_dict(self):
        """Convert the LedgerEntry model to a dictionary"""
        return {
            "id": self.id,
            "driver_id": self.driver_id,
            "medallion_id": self.medallion_id,
            "vehicle_id": self.vehicle_id,
            "amount": self.amount,
            "debit": self.debit,
            "description": self.description,
            "receipt_number": self.receipt_number,
            "transaction_date": self.transaction_date,
            "transaction_time": self.transaction_time,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "ledger_id": self.ledger_id,
            "medallion": self.medallion.to_dict() if self.medallion else None,
            "vehicle": self.vehicle.to_dict() if self.vehicle else None,
            "driver": self.driver.to_dict() if self.driver else None,
            "created_on": self.created_on,
            "updated_on": self.updated_on
        }

class DailyReceipt(Base, AuditMixin):
    """Daily Receipt Model"""
    __tablename__ = "daily_receipts"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(Integer, ForeignKey("drivers.id"), nullable=False)
    vehicle_id = Column(Integer, ForeignKey("vehicles.id"), nullable=False)
    medallion_id = Column(Integer, ForeignKey("medallions.id"), nullable=False)
    lease_id = Column(Integer, ForeignKey("leases.id"), nullable=False)
    receipt_number = Column(String(255), nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    cc_earnings = Column(Float)
    cash_earnings = Column(Float)
    tips = Column(Float)
    lease_due = Column(Float)
    ezpass_due = Column(Float)
    pvb_due = Column(Float)
    curb_due = Column(Float)
    manual_fee = Column(Float)
    incentives = Column(Float)
    cash_paid = Column(Float)

    balance = Column(Float)
    status = Column(Enum(DTRStatus), default=DTRStatus.DRAFT)

    ledger_snapshot_id = Column(Integer, nullable=True)
    receipt_html_key = Column(String(255), nullable=True)
    receipt_pdf_key = Column(String(255), nullable=True)
    receipt_excel_key = Column(String(255), nullable=True)

    driver = relationship("Driver", back_populates="daily_receipts")
    vehicle = relationship("Vehicle", back_populates="daily_receipts")
    medallion = relationship("Medallion", back_populates="daily_receipts")
    lease = relationship("Lease", back_populates="daily_receipts")

    @property
    def receipt_html_url(self):
        """Get the receipt presigned URL"""
        if self.receipt_html_key:
            return s3_utils.generate_presigned_url(self.receipt_html_key)
        return None
    
    @property
    def receipt_pdf_url(self):
        """Get the receipt PDF presigned URL"""
        if self.receipt_pdf_key:
            return s3_utils.generate_presigned_url(self.receipt_pdf_key)
        return None
    
    @property
    def receipt_excel_url(self):
        """Get the receipt Excel presigned URL"""
        if self.receipt_excel_key:
            return s3_utils.generate_presigned_url(self.receipt_excel_key)
        return None
    

class ReportLog(Base, AuditMixin):
    """Report Log Model"""
    __tablename__ = "report_logs"

    id = Column(Integer, primary_key=True, index=True)
    report_type = Column(String(50), nullable=False)
    filename = Column(String(255), nullable=False)
    file_key = Column(String(255), nullable=False)
    status = Column(String(54), default="PENDING")
    is_autormated = Column(Boolean, default=False)
    error_message = Column(String(255), nullable=True)
    generated_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ReportLog(id={self.id}, report_type={self.report_type}, status={self.status})>"