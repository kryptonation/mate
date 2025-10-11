## app/driver_payment/router.py

import csv
from io import StringIO , BytesIO
from typing import Optional
from datetime import date , datetime
import math
import json

# Third party imports
from fastapi import (
    APIRouter, Depends, HTTPException, Query
)
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

# Local imports
from app.core.db import get_db
from app.utils.logger import get_logger
from app.users.utils import get_current_user
from app.utils.lambda_utils import invoke_lambda_function
from app.users.models import User
from app.driver_payment.services import driver_payment_service
from app.utils.exporter.excel_exporter import ExcelExporter
from app.utils.exporter.pdf_exporter import PDFExporter
from app.driver_payment.utils import prepare_driver_transaction_payload
from app.utils.s3_utils import s3_utils
from app.core.config import settings

logger = get_logger(__name__)
router = APIRouter(tags=["Driver Payments"])

@router.get("/payments" , summary="Get driver payments")
def get_driver_payments(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    receipt_number :Optional[str] = Query(None, description="Comman separated filter by receipt numbers"),
    medallion_number: Optional[str] = Query(None, description="Comman separated filter by medallion numbers"),
    tlc_license_number : Optional[str] = Query(None, description="Comman separated filter by tlc license numbers"),
    plate_number : Optional[str] = Query(None, description="Comman separated filter by plate numbers"),
    mode : Optional[str] = Query(None) ,
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
    logged_in_user: User = Depends(get_current_user)
    ):
    """Get driver payments"""

    try:
        results = driver_payment_service.search_driver_payments(
            db=db,page=page, per_page=per_page,
            receipt_number=receipt_number,
            medallion_number=medallion_number, 
            tlc_license_number=tlc_license_number, 
            plate_number=plate_number, 
            mode=mode, 
            sort_by=sort_by, 
            sort_order=sort_order,
            multiple=True)
        
        return results
    except Exception as e:
        logger.error("Error getting driver payments: %s", e)
        raise HTTPException(status_code=500, detail="Error getting driver payments") from e
    
@router.get("/payments/export" , summary="Export driver payments")
def export_driver_payments(
    db: Session = Depends(get_db),
    format: Optional[str] = Query("excel", enum=["excel", "pdf"]),
    receipt_number :Optional[str] = Query(None, description="Comman separated filter by receipt numbers"),
    medallion_number: Optional[str] = Query(None, description="Comman separated filter by medallion numbers"),
    tlc_license_number : Optional[str] = Query(None, description="Comman separated filter by tlc license numbers"),
    plate_number : Optional[str] = Query(None, description="Comman separated filter by plate numbers"),
    mode : Optional[str] = Query(None) ,
    sort_by: Optional[str] = Query(None),
    sort_order: Optional[str] = Query("asc"),
    logged_in_user: User = Depends(get_current_user),
    ):
    """Export driver payments"""
    try:
        result = driver_payment_service.search_driver_payments(
            db=db,page=1, per_page=1000,
            receipt_number=receipt_number,
            medallion_number=medallion_number, 
            tlc_license_number=tlc_license_number, 
            plate_number=plate_number,
            mode=mode, 
            sort_by=sort_by, 
            sort_order=sort_order,
            multiple=True
        )

        if not result:
            logger.warning("No driver payments found for export")
            raise HTTPException(status_code=404, detail="No driver payments found for export")
        
        file = None
        media_type = None
        headers = None

        if format == "excel":
            excel_exporter = ExcelExporter(result["items"])
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            headers = {"Content-Disposition": "attachment; filename=driver_payments_export.xlsx"}
        elif format == "pdf":
            pdf_exporter = PDFExporter(result["items"])
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            headers = {"Content-Disposition": "attachment; filename=driver_payments_export.pdf"}
        else:
            raise HTTPException(status_code=400, detail="Invalid format")

        return StreamingResponse(
            file,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        logger.error(f"Error exporting Driver Payments logs: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
    
@router.get("/dtr_receipt/{receipt_number}", summary="Export DTR receipt")
def export_dtr_receipt(
    receipt_number: str,
    db: Session = Depends(get_db),
    logged_in_user: User = Depends(get_current_user)
):
    """Export DTR receipt"""
    try:
        dtr = driver_payment_service.search_driver_payments(db=db, receipt_number=receipt_number)

        if not dtr:
            raise HTTPException(status_code=404, detail="DTR receipt not found")

        dtr_payload = prepare_driver_transaction_payload(dtr)

        payload = {
            "data": dtr_payload,
            "identifier": f"form_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "template_id": settings.driver_transaction_template_id,
            "bucket": settings.s3_bucket_name
        }

        logger.info("Calling Lambda function with payload: %s", payload)

        response = invoke_lambda_function(
            function_name="pdf_filler",
            payload=payload
        )

        logger.info("Response from Lambda: %s", response)

        response_body = json.loads(response.get("body", "{}"))
        s3_key = response_body.get("s3_key")

        if not s3_key:
            raise HTTPException(status_code=500, detail="Missing S3 key from Lambda response")

        url = s3_utils.generate_presigned_url(s3_key)
        return JSONResponse(content={"presigned_url": url})

    except HTTPException:
        raise  # re-raise known exceptions
    except Exception as e:
        logger.error("Error exporting DTR receipt: %s", e)
        raise HTTPException(status_code=500, detail=str(e))