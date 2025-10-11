## app/correspondence/models.py

# Third party imports
from sqlalchemy import Column, Integer, Date, Time, Text, String

# Local imports
from app.core.db import Base
from app.users.models import AuditMixin


class Correspondence(Base, AuditMixin):
    """Correspondence model"""
    __tablename__ = "correspondence"

    id = Column(Integer, primary_key=True, index=True)
    driver_id = Column(String(64), nullable=True)
    vehicle_id = Column(String(64), nullable=True)
    medallion_number = Column(String(64), nullable=True)
    date_sent = Column(Date, nullable=True)
    time_sent = Column(Time, nullable=True)
    mode = Column(String(64), nullable=True)
    note = Column(Text, nullable=True)
    email = Column(String(128), nullable=True)
    text = Column(String(128), nullable=True)

    