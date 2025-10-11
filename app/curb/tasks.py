## app/curb/tasks.py

# Standard library imports
from datetime import datetime, timedelta
from typing import Optional

# Third party imports
from celery import shared_task

# Local imports
from app.utils.logger import get_logger
from app.core.db import get_db
from app.curb.soap_client import fetch_trips_log10
from app.curb.services import curb_service

logger = get_logger(__name__)

@shared_task(bind=True, name='app.curb.tasks.fetch_and_reconcile_curb_trips')
def fetch_and_reconcile_curb_trips(self):
    """
    Fetch curb trips from the CURB API every 24 hours, reconcile them, and post to ledgers.
    
    This task:
    1. Fetches trips from the last 24 hours from CURB API
    2. Imports new trips into the database
    3. Reconciles trips with CURB system
    4. Associates trips with leases and posts to ledgers
    """
    task_id = self.request.id
    logger.info("[Task ID: %s] Starting CURB trip fetch and reconciliation process", task_id)

    try:
        # Get database session
        db = next(get_db())
        logger.info("[Task ID: %s] Database connection established", task_id)
        
        # Step 1: Fetch trips from the last 24 hours
        from_date = datetime.now() - timedelta(days=1)
        to_date = datetime.now()

        logger.info("[Task ID: %s] Fetching trips from %s to %s", task_id, from_date.strftime('%m/%d/%Y'), to_date.strftime('%m/%d/%Y'))

        trip_records = fetch_trips_log10(
            from_date=from_date.strftime('%m/%d/%Y'), 
            to_date=to_date.strftime('%m/%d/%Y')
        )

        logger.debug("[Task ID: %s] Retrieved trip: %s", task_id, trip_records)
        logger.info("[Task ID: %s] Retrieved %d trip records from CURB API", task_id, len(trip_records) if trip_records else 0)

        # Step 2: Import trips into database
        if trip_records:
            import_result = curb_service.import_curb_trips(db, trip_records)
            logger.info("[Task ID: %s] Imported %d new trips, %d total processed", task_id, import_result.get('inserted', 0), import_result.get('total', 0))
        else:
            logger.info("[Task ID: %s] No new trips to import", task_id)
            import_result = {"inserted": 0, "total": 0}
        
        # Step 3: Reconcile trips locally (only if we have new trips)
        if import_result.get('inserted', 0) > 0:
            logger.info("[Task ID: %s] Starting local reconciliation of unreconciled trips", task_id)

            # Use the bulk local reconciliation method
            reconcile_result = curb_service.bulk_reconcile_trips_locally(db)
            
            logger.info("[Task ID: %s] Locally reconciled %d trips", task_id, reconcile_result.get('reconciled_count', 0))
        else:
            logger.info("[Task ID: %s] Skipping reconciliation - no new trips", task_id)

        # Step 4: Bulk associate and post trips to ledgers
        logger.info("[Task ID: %s] Starting bulk association and posting to ledgers", task_id)
        post_result = curb_service.bulk_associate_and_post_trips(db)

        logger.info("[Task ID: %s] Posted %d trips to ledgers", task_id, post_result.get('posted_count', 0))
        if post_result.get('skipped'):
            logger.info("[Task ID: %s] Skipped %d trips", task_id, len(post_result['skipped']))
        if post_result.get('errors'):
            logger.warning("[Task ID: %s] Errors occurred: %s", task_id, post_result['errors'])

        # Return summary
        result = {
            "status": "success",
            "task_id": task_id,
            "import_result": import_result,
            "post_result": post_result,
            "processed_at": datetime.now().isoformat()
        }
        
        logger.info("[Task ID: %s] CURB trip processing completed successfully", task_id)
        return result
        
    except Exception as e:
        logger.error("[Task ID: %s] Error in CURB trip processing: %s", task_id, str(e), exc_info=True)
        # Re-raise the exception so Celery can handle it properly
        raise
    finally:
        try:
            db.close()
            logger.info("[Task ID: %s] Database session closed", task_id)
        except Exception as e:
            logger.error("[Task ID: %s] Error closing database session: %s", task_id, str(e), exc_info=True)

@shared_task(bind=True, name='app.curb.tasks.reconcile_curb_trips_only')
def reconcile_curb_trips_only(self, recon_stat: Optional[int] = None):
    """
    Reconcile existing unreconciled CURB trips locally only.
    
    Args:
        recon_stat: Receipt number for reconciliation. If None, uses timestamp.
    """
    task_id = self.request.id
    logger.info("[Task ID: %s] Starting CURB trip local reconciliation only", task_id)
    
    try:
        db = next(get_db())
        
        # Check if we have a specific recon_stat or should generate one
        if recon_stat is None:
            # Use bulk reconciliation which generates its own recon_stat
            result = curb_service.bulk_reconcile_trips_locally(db)
        else:
            # Get unreconciled trips for specific recon_stat reconciliation
            unreconciled_trips = curb_service.get_curb_trip(
                db, is_reconciled=False, multiple=True
            )
            
            if not unreconciled_trips:
                logger.info("[Task ID: %s] No unreconciled trips found", task_id)
                return {"status": "success", "message": "No trips to reconcile"}
            
            # Convert trip IDs to strings as required by the service method
            trip_ids = [str(trip.id) for trip in unreconciled_trips]
            
            logger.info("[Task ID: %s] Reconciling %s trips locally with recon_stat: %s", task_id, len(trip_ids), recon_stat)
            
            result = curb_service.reconcile_curb_trips(db, trip_ids=trip_ids, recon_stat=recon_stat)
        
        logger.info("[Task ID: %s] Local reconciliation completed successfully", task_id)
        return result
        
    except Exception as e:
        logger.error("[Task ID: %s] Error in local reconciliation: %s", task_id, str(e), exc_info=True)
        raise
    finally:
        try:
            db.close()
        except Exception as e:
            logger.error("[Task ID: %s] Error closing database session: %s", task_id, str(e), exc_info=True)

@shared_task(bind=True, name='app.curb.tasks.post_curb_trips_only')
def post_curb_trips_only(self):
    """
    Post already reconciled CURB trips to ledgers only.
    """
    task_id = self.request.id
    logger.info("[Task ID: %s] Starting CURB trip posting only", task_id)

    try:
        db = next(get_db())
        
        result = curb_service.bulk_associate_and_post_trips(db)

        logger.info("[Task ID: %s] Posting completed successfully", task_id)
        return result
        
    except Exception as e:
        logger.error("[Task ID: %s] Error in posting: %s", task_id, str(e), exc_info=True)
        raise
    finally:
        try:
            db.close()
        except Exception as e:
            logger.error("[Task ID: %s] Error closing database session: %s", task_id, str(e), exc_info=True)


