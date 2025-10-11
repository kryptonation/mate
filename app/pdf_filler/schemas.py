# app/pdf_filler/schemas.py

from typing import Dict, Any

from pydantic import BaseModel


class PDFRequest(BaseModel):
    """Schema for PDF generation requests."""
    template_name: str
    data: Dict[str, Any]


class PDFResponse(BaseModel):
    """Schema for PDF generation responses."""
    s3_key: str
    presigned_url: str

