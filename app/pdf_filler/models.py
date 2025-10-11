# app/pdf_filler/models.py

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import JSON

from app.core.db import Base
from app.users.models import AuditMixin


class PDFTemplate(Base, AuditMixin):
    """
    Model to store information about fillable PDF templates.
    """
    __tablename__ = "pdf_templates"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # A unique, human readable name to identify the template
    template_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)

    # The path to the PDF template file in the S3 bucket.
    s3_key: Mapped[str] = mapped_column(String(255), comment="The S3 key for the PDF template file.")

    # A JSON object that maps the PDF's form field names to the keys in the data you will provide.
    # Example: {"pdf_field_for_name": "driver_name", "pdf_field_for_date": "lease_start_date"}
    field_mapping: Mapped[dict] = mapped_column(JSON)