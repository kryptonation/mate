### app/ledger/tasks.py

# Standard library imports
from datetime import datetime, timedelta, timezone

# Third party imports
from celery import shared_task

# Local imports
from app.utils.logger import get_logger
from app.core.db import get_db
from app.ledger.services import ledger_service
from app.drivers.services import driver_service
from app.leases.services import lease_service
from app.vehicles.services import vehicle_service
from app.medallions.services import medallion_service
from app.ledger.utils import generate_dtr_html_doc, generate_dtr_pdf_doc, generate_dtr_excel_doc_styled

logger = get_logger(__name__)

@shared_task(bind=True, name='app.ledger.tasks.generate_weekly_dtrs')
def generate_weekly_dtrs(self):
    """
    Generate weekly Driver Transaction Receipts (DTRs) for all active drivers.
    This task runs every Sunday and covers the previous week from Sunday to Saturday.
    """
    from app.curb.models import CURBTrip
    from app.ezpass.models import EZPassTransaction
    from app.pvb.models import PVBViolation

    task_id = self.request.id
    logger.info(f"[Task ID: {task_id}] Starting weekly DTR generation process")
    db = next(get_db())
    try:
        # Determine the date range for the last week (Sun 12:00 AM to Sat 11:59 PM)
        today = datetime.now(timezone.utc)
        start_of_this_week = today - timedelta(days=today.weekday() + 1) # Last Sunday
        end_of_last_week = start_of_this_week - timedelta(seconds=1)
        start_of_last_week = end_of_last_week - timedelta(days=6)

        from_date = start_of_last_week.replace(hour=0, minute=0, second=0, microsecond=0)
        to_date = end_of_last_week.replace(hour=23, minute=59, second=59, microsecond=999999)

        logger.info(f"Generating DTRs for period: {from_date} to {to_date}")

        # Find all drivers who had activity in this period (e.g., had CURB trips)
        active_driver_ids = db.query(CURBTrip.driver_id).filter(
            CURBTrip.start_date.between(from_date.date(), to_date.date())
        ).distinct().all()

        driver_ids_to_process = [d[0] for d in active_driver_ids]
        logger.info(f"Found {len(driver_ids_to_process)} active drivers for the period.")

        for driver_id in driver_ids_to_process:
            try:
                # Find the internal integer ID for the driver
                driver = driver_service.get_drivers(db, driver_id=driver_id)
                if not driver:
                    logger.warning(f"Could not find driver for CURB driver_id {driver_id}. Skipping.")
                    continue
                
                logger.info(f"Generating DTR for driver: {driver.full_name} (ID: {driver.id})")
                ledger_service.create_and_generate_dtr_files(db, driver.id, from_date, to_date)
            except Exception as e:
                logger.error(f"Failed to generate DTR for driver ID {driver_id}: {e}", exc_info=True)

        logger.info(f"[Task ID: {task_id}] Weekly DTR generation completed successfully.")
    except Exception as e:
        logger.error(f"[Task ID: {task_id}] A critical error occurred during DTR generation: {e}", exc_info=True)
        raise
    finally:
        db.close()