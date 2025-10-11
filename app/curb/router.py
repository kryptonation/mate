## app/curb/router.py

# Standard library imports
from datetime import datetime , time , date
from typing import Optional, List
from io import BytesIO


# Third party imports
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from fastapi.responses import StreamingResponse

# Local imports
from app.core.db import get_db
from app.utils.logger import get_logger
from app.curb.services import curb_service
from app.curb.soap_client import fetch_trips_log10, fetch_trans_by_date_cab12
from app.users.models import User
from app.users.utils import get_current_user
from app.utils.exporter.excel_exporter import ExcelExporter
from app.utils.exporter.pdf_exporter import PDFExporter

router = APIRouter(prefix="/curb", tags=["CURB"])
logger = get_logger(__name__)

@router.post("/import-trips")
async def import_curb_trips_log10(
    db: Session = Depends(get_db),
    from_datetime: str = Query(..., description="Start date in MM/DD/YYYY format"),
    to_datetime: str = Query(..., description="End date in MM/DD/YYYY format"),
    recon_stat: Optional[int] = Query(None, description="Reconciliation status"),
    cab_number: Optional[str] = Query(None, description="Cab number"),
    driver_id: Optional[str] = Query(None, description="Driver ID"),
    user: User = Depends(get_current_user)
):
    """Import CURB trips from log10"""
    try:
        trips = fetch_trans_by_date_cab12(from_datetime=from_datetime, to_datetime=to_datetime, cab_number=cab_number)
        cash_trips = fetch_trips_log10(from_date=from_datetime, to_date=to_datetime, recon_stat=recon_stat or -1, cab_number=cab_number or "", driver_id=driver_id or "")
        if not trips:
            raise HTTPException(status_code=404, detail="No trips found")

        trip_records = curb_service.import_curb_trips(db, xml_data=trips, cash_xml_data=cash_trips)
        return trip_records
    except Exception as e:
        logger.error("Error importing CURB trips: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/reconcile-trips")
async def reconcile_curb_trips(
    db: Session = Depends(get_db),
    trip_ids: List[str] = Query(..., description="List of trip IDs to reconcile"),
    recon_stat: int = Query(..., description="Reconciliation status"),
    user: User = Depends(get_current_user)
):
    """Reconcile CURB trips locally (no remote API call)"""
    try:
        if recon_stat < 0:
            raise HTTPException(status_code=400, detail="RECON_STAT must be a positive receipt number")
        
        if not trip_ids:
            raise HTTPException(status_code=400, detail="At least one trip ID is required")
        
        if len(trip_ids) > 100:
            raise HTTPException(status_code=400, detail="Cannot reconcile more than 100 trips at once")
            
        result = curb_service.reconcile_curb_trips(db, trip_ids, recon_stat, recon_by=user.first_name)
        return result
    except Exception as e:
        logger.error("Error reconciling CURB trips locally: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.post("/bulk-post-trips")
async def bulk_post_curb_trips(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Bulk associate and post trips to CURB"""
    try:
        result = curb_service.bulk_associate_and_post_trips(db=db, posted_by=current_user.first_name)
        return {
            "status": "success",
            "summary": result
        }
    except Exception as e:
        logger.error("Error bulk associating and posting trips to CURB: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/trips")
async def get_curb_trip_list(
    page: int = Query(1, alias="page", description="Page number (1-based)"),
    per_page: int = Query(20, alias="per_page", description="Number of items per page"),
    sort_by: Optional[str] = Query("start_date", description="Field to sort by"),
    sort_order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    driver_id: Optional[str] = None,
    cab_number: Optional[str] = None,
    trip_id: Optional[str] = None,
    medallion_number: Optional[str] = None,
    tlc_license_number: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    start_date_from: Optional[date] = None,
    start_date_to: Optional[date] = None,
    end_date_from: Optional[date] = None,
    end_end_to: Optional[date] = None,
    start_time_from: Optional[time] = None,
    start_time_to: Optional[time] = None,
    end_time_from: Optional[time] = None,
    end_time_to: Optional[time] = None,
    payment_type: Optional[str] = None,
    distance: Optional[str] = None,
    status: Optional[str] = None,
    gps_start_lat: Optional[str] = None,
    gps_end_lat: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get CURB trip list"""
    try:
        logger.debug("get_curb_trip_list called with: page=%d, per_page=%d, sort_by=%s, sort_order=%s", 
                    page, per_page, sort_by, sort_order)
        
        result = curb_service.list_curb_trips(
            db=db,
            page=page,
            per_page=per_page,
            sort_by=sort_by,
            sort_order=sort_order,
            filters={
                "driver_id": driver_id,
                "cab_number": cab_number,
                "trip_id": trip_id,
                "medallion_number": medallion_number,
                "tlc_license_number": tlc_license_number,
                "from_date": from_date,
                "to_date": to_date,
                "start_date_from": start_date_from,
                "start_date_to": start_date_to,
                "end_date_from": end_date_from,
                "end_end_to": end_end_to,
                "start_time_from": start_time_from,
                "start_time_to": start_time_to,
                "end_time_from": end_time_from,
                "end_time_to": end_time_to,
                "payment_type": payment_type,
                "status": status,
                "gps_start_lat": gps_start_lat,
                "gps_end_lat": gps_end_lat,
                "distance": distance,
            }
        )
        return result
    except Exception as e:
        logger.error("Error getting CURB trip list: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e

@router.get("/trips/{trip_id}")
async def get_curb_trip(
    trip_id: int,
    db: Session = Depends(get_db)
):
    """Get CURB trip by ID"""
    try:
        result = curb_service.get_curb_trip(db, trip_id=trip_id)
        return {
            "trip_id": result.id,
            "record_id": result.record_id,
            "period": result.period,
            "driver_id": result.driver_id,
            "cab_number": result.cab_number,
            "start_date": result.start_date,
            "end_date": result.end_date,
            "trip_amount": result.trip_amount,
            "tips": result.tips,
            "extras": result.extras,
            "tolls": result.tolls,
            "tax": result.tax,
            "imp_tax": result.imp_tax,
            "total_amount": result.total_amount,
            "payment_type": result.payment_type,
            "is_reconciled": result.is_reconciled,
            "is_posted": result.is_posted,
            "gps_start_lat": result.gps_start_lat,
            "gps_start_lon": result.gps_start_lon,
            "gps_end_lat": result.gps_end_lat,
            "gps_end_lon": result.gps_end_lon,
            "from_address": result.from_address,
            "to_address": result.to_address,
            "payment_type": result.payment_type,
            "cc_number": result.cc_number,
            "auth_code": result.auth_code,
            "auth_amount": result.auth_amount,
            "ehail_fee": result.ehail_fee,
            "health_fee": result.health_fee,
            "passengers": result.passengers,
            "distance_service": result.distance_service,
            "distance_bs": result.distance_bs,
            "reservation_number": result.reservation_number,
            "congestion_fee": result.congestion_fee,
            "airport_fee": result.airport_fee,
            "cbdt_fee": result.cbdt_fee,
        }
    except Exception as e:
        logger.error("Error getting CURB trip: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    
@router.get("/export")
async def export_curb_trips(
    db: Session = Depends(get_db),
    format: Optional[str] = Query("excel", enum=["excel", "pdf"]),
    trip_id: Optional[int] = None,
    record_id: Optional[str] = None,
    period: Optional[str] = None,
    driver_id: Optional[str] = None,
    cab_number: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    payment_type: Optional[str] = None,
    is_reconciled: Optional[bool] = None,
    is_posted: Optional[bool] = None,
    sort_by: Optional[str] = Query("start_date"),
    sort_order: Optional[str] = Query("desc")
):
    """Export CURB trips"""
    try:
        
        result=curb_service.get_curb_trip(db=db,trip_id= trip_id , record_id= record_id,
                                   period= period , driver_id= driver_id , cab_number= cab_number,
                                   from_date= start_date , end_date=end_date,
                                   payment_type= payment_type , is_reconciled= is_reconciled , is_posted= is_posted,
                                   multiple= True , sort_by= sort_by , sort_order= sort_order)
        

        trips_data = [
                {
                    "Trip Id": trip.id,
                    "Driver Id": trip.driver_id,
                    "Cab Number": trip.cab_number,
                    "Trip Date": trip.start_date,
                    "Gps Start Lat": trip.gps_start_lat,
                    "Gps Start Lon": trip.gps_start_lon,
                    "Gps End Lat": trip.gps_end_lat,
                    "Gps End Lon": trip.gps_end_lon,
                    "From Address": trip.from_address,
                    "To Address": trip.to_address,
                    "Tips": trip.tips,
                    "Extras": trip.extras,
                    "Tolls": trip.tolls,
                    "Tax": trip.tax,
                    "Imp Tax": trip.imp_tax,
                    "Ehail Fee": trip.ehail_fee,
                    "Health Fee": trip.health_fee,
                    "Total Amount": trip.total_amount,
                    "Payment Type": trip.payment_type,
                    "Is Reconciled": trip.is_reconciled,
                    "Is Posted": trip.is_posted
                } for trip in result
            ]
        
        if not trips_data :
            logger.warning("No trips available to export.")
            raise HTTPException(status_code=400, detail="No Trips available to export.")
        
        file = None
        media_type = None
        headers = None

        if format == "excel":
            excel_exporter = ExcelExporter(trips_data)
            file: BytesIO = excel_exporter.export()
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            headers = {"Content-Disposition": "attachment; filename=trips_export.xlsx"}
        elif format == "pdf":
            pdf_exporter = PDFExporter(trips_data)
            file: BytesIO = pdf_exporter.export()
            media_type = "application/pdf"
            headers = {"Content-Disposition": "attachment; filename=trips_export.pdf"}
        else:
            raise HTTPException(status_code=400, detail="Invalid format")
        
        return StreamingResponse(
            file,
            media_type=media_type,
            headers=headers
        )
    except Exception as e:
        logger.error("Error exporting trips list: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Error exporting trips list") from e

@router.post("/bulk-reconcile-locally")
async def bulk_reconcile_trips_locally(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Bulk reconcile all unreconciled CURB trips locally (no remote API call)"""
    try:
        result = curb_service.bulk_reconcile_trips_locally(db=db, recon_by=user.first_name)
        return {
            "status": "success",
            "summary": result
        }
    except Exception as e:
        logger.error("Error bulk reconciling CURB trips locally: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e
    
@router.post("/manual-import-by-date", status_code=202, summary="Manually trigger CURB trip import for a date range")
def manual_import_by_date(
    background_tasks: BackgroundTasks,
    from_date: date = Query(..., description="Start date in YYYY-MM-DD format"),
    to_date: date = Query(..., description="End date in YYYY-MM-DD format"),
    driver_id: Optional[str] = Query(None, description="Driver ID"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Manually triggers a background task to fetch, import, reconcile, and post
    CURB trips for a specified date range.
    """
    try:
        logger.info(f"Manual CURB import requested by {user.email_address} for dates {from_date} to {to_date}")

        # the FastAPI's BackgroundTasks to run the process without blocking the API response
        background_tasks.add_task(
            curb_service.process_trips_for_date_range,
            db=db,
            from_date=from_date,
            to_date=to_date,
            import_by=user.email_address,
            driver_id=driver_id
        )

        return {
            "status": "success",
            "message": "CURB trip import process has been started in the background."
                        "Check the CURB import logs for progress and results."
        }
    except Exception as e:
        logger.error("Failed to initiate manual CURB trip import: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to start the import process") from e
    





