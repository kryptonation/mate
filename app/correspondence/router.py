## app/correspondence/router.py

# Standard library imports
from typing import List, Optional
from datetime import datetime, time
from io import BytesIO

# Third party imports
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# Local imports
from app.core.db import get_db
from app.utils.logger import get_logger
from app.correspondence.services import correspondence_service
from app.users.models import User
from app.users.utils import get_current_user
from app.utils.exporter.excel_exporter import ExcelExporter
from app.utils.exporter.pdf_exporter import PDFExporter

logger = get_logger(__name__)
router = APIRouter(tags=["Correspondence"], prefix="/correspondence")

@router.get("/list")
def list_correspondences(
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, le=100),
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc",
    medallion_number: Optional[str] = None,
    driver_id: Optional[str] = None,
    vehicle_id: Optional[int] = None,
    correspondence_mode: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    from_time: Optional[time] = None,
    to_time: Optional[time] = None,
):
    """List correspondences"""
    try:
        correspondences, total_count = correspondence_service.search_correspondences(
            db, page, per_page, sort_by, sort_order, medallion_number,
            driver_id, vehicle_id, correspondence_mode, from_date,
            to_date, from_time, to_time
        )
        
        return {
            "page": page,
            "per_page": per_page,
            "total_count": total_count,
            "items": correspondences,
            "total_pages": (total_count + per_page - 1) // per_page,
            "modes": ["In-Person", "Email"],
        }
    except Exception as e:
        logger.error("Error listing correspondences: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
    
@router.get("/export")
def export_correspondences(
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user),
    format: Optional[str] = Query("excel", enum=["excel", "pdf"]),
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc",
    medallion_number: Optional[str] = None,
    driver_id: Optional[str] = None,
    vehicle_id: Optional[int] = None,
    correspondence_mode: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    from_time: Optional[time] = None,
    to_time: Optional[time] = None,
):
    """Export correspondences"""
    try:
        correspondences , total_count = correspondence_service.search_correspondences(
            db=db, page=1, per_page=1000, sort_by=sort_by, sort_order=sort_order, 
            medallion_number=medallion_number,
            driver_id=driver_id,
            vehicle_id=vehicle_id,
            correspondence_mode=correspondence_mode,
            from_date=from_date,
            to_date=to_date,
            from_time=from_time,
            to_time=to_time
        )

        correspondence_data = [
            {
                "Correspondence Mode": c.mode,
                "Driver ID": c.driver_id,
                "Vehicle ID": c.vehicle_id,
                "Medallion Number": c.medallion_number,
                "Date Sent": c.date_sent,
                "Time Sent": c.time_sent,
                "Note": c.note,
                "Email": c.email,
                "Text": c.text,
                "Created On": c.created_on,
                "Created By": c.created_by,
            } for c in correspondences
        ]

        if not correspondence_data:
            logger.info("No correspondences found for export")
            raise HTTPException(status_code=404, detail="No correspondences found for export")

        file = None
        media_type = None
        headers = None

        if format == "excel":
            excel_exporter = ExcelExporter(correspondence_data)
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            headers = {"Content-Disposition": "attachment; filename=correspondence_export.xlsx"}
        elif format == "pdf":
            pdf_exporter = PDFExporter(correspondence_data)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            headers = {"Content-Disposition": "attachment; filename=correspondence_export.pdf"}
        else:
            raise HTTPException(status_code=400, detail="Invalid format")
        
        return StreamingResponse(
            file,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        logger.error(f"Error exporting correspondences: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
    