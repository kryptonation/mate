## app/correspondence/services.py

# Standard library imports
from datetime import datetime, time
from typing import List, Optional, Union

# Third party imports
from sqlalchemy import or_, asc, desc
from sqlalchemy.orm import Session

# Local imports
from app.utils.logger import get_logger
from app.correspondence.models import Correspondence

logger = get_logger(__name__)


class CorrespondenceService:
    """Service for correspondence operations"""
    def get_correspondence(
        self, db: Session,
        correspondence_id: Optional[int] = None,
        driver_id: Optional[str] = None,
        vehicle_id: Optional[int] = None,
        medallion_number: Optional[str] = None,
        note : Optional[str] = None,
        multiple: Optional[bool] = False,
    ) -> Union[Correspondence, List[Correspondence]]:
        """Get correspondence by ID, driver ID, vehicle ID, or medallion number"""
        try:
            query = db.query(Correspondence)

            if correspondence_id:
                query = query.filter(Correspondence.id == correspondence_id)
            if driver_id:
                query = query.filter(Correspondence.driver_id == driver_id)
            if vehicle_id:
                query = query.filter(Correspondence.vehicle_id == vehicle_id)
            if medallion_number:
                query = query.filter(Correspondence.medallion_number == medallion_number)
            if note:
                query = query.filter(Correspondence.note.ilike(f"%{note}%"))

            query = query.order_by(desc(Correspondence.created_on)) 

            if multiple:
                return query.all()

            return query.first()
        except Exception as e:
            logger.error("Error getting correspondence: %s", e)
            raise e
        
    def search_correspondences(
        self, db: Session, page: int, per_page: int, sort_by: Optional[str] = None,
        sort_order: Optional[str] = "asc", medallion_number: Optional[str] = None,
        driver_id: Optional[str] = None, vehicle_id: Optional[int] = None,
        correspondence_mode: Optional[str] = None,
        from_date: Optional[datetime] = None, to_date: Optional[datetime] = None,
        from_time: Optional[time] = None, to_time: Optional[time] = None
    ) -> List[Correspondence]:
        """Search correspondences"""
        try:
            query = db.query(Correspondence)

            if medallion_number:
                numbers = [n.strip() for n in medallion_number.split(",") if n.strip()]
                query = query.filter(or_(
                    *[Correspondence.medallion_number.ilike(f"%{n}%") for n in numbers]
                ))
            if driver_id:
                driver_ids = [d.strip() for d in driver_id.split(",") if d.strip()]
                query = query.filter(or_(
                    *[Correspondence.driver_id.ilike(f"%{d}%") for d in driver_ids]
                ))
            if vehicle_id:
                vehicle_ids = [v.strip() for v in vehicle_id.split(",") if v.strip()]
                query = query.filter(or_(
                    *[Correspondence.vehicle_id.ilike(f"%{v}%") for v in vehicle_ids]
                ))
            if correspondence_mode:
                modes = [m.strip() for m in correspondence_mode.split(",") if m.strip()]
                query = query.filter(or_(
                    *[Correspondence.mode.ilike(f"%{m}%") for m in modes]
                ))
            if from_date:
                query = query.filter(Correspondence.date_sent >= from_date)
            if to_date:
                query = query.filter(Correspondence.date_sent <= to_date)
            if from_time:
                query = query.filter(Correspondence.time_sent >= from_time)
            if to_time:
                query = query.filter(Correspondence.time_sent <= to_time)

            if sort_by:
                if sort_by == "created_on":
                    query = query.order_by(asc(Correspondence.created_on) if sort_order == "asc" else desc(Correspondence.created_on))
                elif sort_by == "correspondence_status":
                    query = query.order_by(asc(Correspondence.correspondence_status) if sort_order == "asc" else desc(Correspondence.correspondence_status))
                elif sort_by == "correspondence_mode":
                    query = query.order_by(asc(Correspondence.correspondence_mode) if sort_order == "asc" else desc(Correspondence.correspondence_mode))
                elif sort_by == "driver_id":
                    query = query.order_by(asc(Correspondence.driver_id) if sort_order == "asc" else desc(Correspondence.driver_id))
                elif sort_by == "vehicle_id":
                    query = query.order_by(asc(Correspondence.vehicle_id) if sort_order == "asc" else desc(Correspondence.vehicle_id))
                elif sort_by == "medallion_number":
                    query = query.order_by(asc(Correspondence.medallion_number) if sort_order == "asc" else desc(Correspondence.medallion_number))
                elif sort_by == "date_sent":
                    query = query.order_by(asc(Correspondence.date_sent) if sort_order == "asc" else desc(Correspondence.date_sent))
                elif sort_by == "time_sent":
                    query = query.order_by(asc(Correspondence.time_sent) if sort_order == "asc" else desc(Correspondence.time_sent))
                
            total_count = query.count()
            if per_page:
                query = query.limit(per_page)
            if page:
                query = query.offset((page - 1) * per_page)

            return query.all(), total_count    
        except Exception as e:
            logger.error("Error searching correspondences: %s", e)
            raise e
        
        
    def upsert_correspondence(
        self, db: Session, correspondence_data: dict
    ) -> Correspondence:
        """Upsert correspondence"""
        try:
            if correspondence_data.get("id"):
                correspondence = self.get_correspondence(
                    db, correspondence_id=correspondence_data["id"]
                )
                if correspondence:
                    for key, value in correspondence_data.items():
                        setattr(correspondence, key, value)
                    db.commit()
                    db.refresh(correspondence)
                    return correspondence
            else:
                correspondence = Correspondence(**correspondence_data)
                db.add(correspondence)
                db.commit()
                db.refresh(correspondence)
                return correspondence
        except Exception as e:
            logger.error("Error upserting correspondence: %s", e)
            raise e
        

correspondence_service = CorrespondenceService()

            