# app/curb/tasks.py

"""
Celery tasks for CURB (Taxi Fleet) operations

This module contains all Celery tasks for automated CURB trip processing.
Tasks are scheduled via Celery Beat and can also be triggered manually.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from celery import shared_task

from app.utils.logger import get_logger
from app.core.db import get_async_db
from app.core.config import settings
from app.curb.soap_client import fetch_trips_log10, fetch_trans_by_date_cab12
from app.curb.services import CURBService
from app.curb.repository import CURBRepository

logger = get_logger(__name__)


@shared_task(bind=True, name='app.curb.tasks.fetch_and_import_curb_trips')
def fetch_and_import_curb_trips(self):
    """
    Fetch and import CURB trips from the API for the last 24 hours.
    
    This task runs every 24 hours and:
    1. Fetches card transactions from the last 24 hours
    2. Fetches cash trips from the last 24 hours
    3. Imports new trips into the database
    
    Note: This task only imports trips. Reconciliation and posting are separate tasks.
    """
    task_id = self.request.id
    logger.info("[Task ID: %s] Starting CURB trip fetch and import", task_id)

    try:
        # Calculate date range (last 24 hours)
        to_date = datetime.now(timezone.utc)
        from_date = to_date - timedelta(days=1)

        from_date_str = from_date.strftime('%m/%d/%Y')
        to_date_str = to_date.strftime('%m/%d/%Y')

        logger.info(
            "[Task ID: %s] Fetching trips from %s to %s",
            task_id, from_date_str, to_date_str
        )

        # Fetch card transactions
        try:
            card_xml = fetch_trans_by_date_cab12(
                from_datetime=from_date_str,
                to_datetime=to_date_str,
                cab_number="",
                tran_type="ALL"
            )
            logger.info("[Task ID: %s] Card transactions fetched", task_id)
        except Exception as e:
            logger.error(
                "[Task ID: %s] Failed to fetch card transactions: %s",
                task_id, str(e), exc_info=True
            )
            card_xml = ""

        # Fetch cash trips
        try:
            cash_xml = fetch_trips_log10(
                from_date=from_date_str,
                to_date=to_date_str,
                recon_stat=-1,  # Get all trips
                cab_number="",
                driver_id=""
            )
            logger.info("[Task ID: %s] Cash trips fetched", task_id)
        except Exception as e:
            logger.error(
                "[Task ID: %s] Failed to fetch cash trips: %s",
                task_id, str(e), exc_info=True
            )
            cash_xml = ""

        if not card_xml and not cash_xml:
            logger.warning("[Task ID: %s] No trip data retrieved", task_id)
            return {
                "status": "no_data",
                "task_id": task_id,
                "message": "No trip data available for the specified period"
            }

        # Import trips using async service
        import asyncio
        
        async def import_trips_async():
            async for db in get_async_db():
                try:
                    repo = CURBRepository(db)
                    service = CURBService(repo)
                    
                    result = await service.import_trips(
                        xml_data=card_xml,
                        cash_xml_data=cash_xml,
                        import_source="SOAP",
                        import_by="SYSTEM"
                    )
                    
                    return result
                finally:
                    await db.close()

        import_result = asyncio.run(import_trips_async())

        logger.info(
            "[Task ID: %s] Import completed: %d total, %d imported, %d duplicates",
            task_id,
            import_result.total_records,
            import_result.success_count,
            import_result.duplicate_count
        )

        return {
            "status": "success",
            "task_id": task_id,
            "import_result": {
                "log_id": import_result.log_id,
                "total_records": import_result.total_records,
                "success_count": import_result.success_count,
                "duplicate_count": import_result.duplicate_count,
                "failure_count": import_result.failure_count,
            },
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(
            "[Task ID: %s] Error in CURB trip fetch and import: %s",
            task_id, str(e), exc_info=True
        )
        raise


@shared_task(bind=True, name='app.curb.tasks.reconcile_curb_trips')
def reconcile_curb_trips(self, recon_stat: Optional[int] = None):
    """
    Reconcile unreconciled CURB trips.
    
    For dev/uat: reconciles locally without calling CURB API.
    For production: calls CURB API to reconcile on server.
    
    Args:
        recon_stat: Optional reconciliation receipt number.
                   If None, generates timestamp-based number.
    """
    task_id = self.request.id
    logger.info("[Task ID: %s] Starting CURB trip reconciliation", task_id)

    try:
        # Determine environment
        is_production = settings.environment.lower() == "production"
        
        logger.info(
            "[Task ID: %s] Reconciliation mode: %s",
            task_id, "PRODUCTION (server)" if is_production else "DEV/UAT (local)"
        )

        # Reconcile trips using async service
        import asyncio
        
        async def reconcile_trips_async():
            async for db in get_async_db():
                try:
                    repo = CURBRepository(db)
                    service = CURBService(repo)
                    
                    if is_production:
                        # Production: Get unreconciled trips and reconcile on server
                        trips = await repo.get_unreconciled_trips(limit=1000)
                        
                        if not trips:
                            logger.info("[Task ID: %s] No trips to reconcile", task_id)
                            return None
                        
                        trip_ids = [trip.id for trip in trips]
                        recon_stat_value = recon_stat or int(datetime.now(timezone.utc).timestamp())
                        
                        result = await service.reconcile_trips_on_server(
                            trip_ids=trip_ids,
                            recon_stat=recon_stat_value,
                            recon_by="SYSTEM"
                        )
                    else:
                        # Dev/UAT: Reconcile locally
                        result = await service.reconcile_trips_locally(
                            trip_ids=None,  # Process all unreconciled
                            recon_stat=recon_stat,
                            recon_by="SYSTEM"
                        )
                    
                    return result
                finally:
                    await db.close()

        reconcile_result = asyncio.run(reconcile_trips_async())

        if not reconcile_result:
            return {
                "status": "no_trips",
                "task_id": task_id,
                "message": "No trips to reconcile"
            }

        logger.info(
            "[Task ID: %s] Reconciliation completed: %d reconciled",
            task_id, reconcile_result.reconciled_count
        )

        return {
            "status": "success",
            "task_id": task_id,
            "reconcile_result": {
                "total_processed": reconcile_result.total_processed,
                "reconciled_count": reconcile_result.reconciled_count,
                "already_reconciled_count": reconcile_result.already_reconciled_count,
                "failed_count": reconcile_result.failed_count,
                "recon_stat": reconcile_result.recon_stat,
            },
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(
            "[Task ID: %s] Error in CURB trip reconciliation: %s",
            task_id, str(e), exc_info=True
        )
        raise


@shared_task(bind=True, name='app.curb.tasks.post_curb_trips')
def post_curb_trips(self):
    """
    Post reconciled CURB trips to ledger.
    
    Processes all reconciled but unposted trips by:
    1. Associating trips with active leases
    2. Creating ledger entries
    3. Marking trips as posted
    """
    task_id = self.request.id
    logger.info("[Task ID: %s] Starting CURB trip posting", task_id)

    try:
        # Post trips using async service
        import asyncio
        
        async def post_trips_async():
            async for db in get_async_db():
                try:
                    repo = CURBRepository(db)
                    service = CURBService(repo)
                    
                    result = await service.associate_and_post_trips(
                        posted_by="SYSTEM"
                    )
                    
                    return result
                finally:
                    await db.close()

        post_result = asyncio.run(post_trips_async())

        logger.info(
            "[Task ID: %s] Posting completed: %d posted, %d failed, %d skipped",
            task_id,
            post_result.posted_count,
            post_result.failed_count,
            post_result.skipped_count
        )

        return {
            "status": "success",
            "task_id": task_id,
            "post_result": {
                "total_processed": post_result.total_processed,
                "posted_count": post_result.posted_count,
                "failed_count": post_result.failed_count,
                "skipped_count": post_result.skipped_count,
            },
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(
            "[Task ID: %s] Error in CURB trip posting: %s",
            task_id, str(e), exc_info=True
        )
        raise


@shared_task(bind=True, name='app.curb.tasks.process_curb_trips_full')
def process_curb_trips_full(self):
    """
    Complete CURB trip processing workflow.
    
    This is a convenience task that runs the full workflow:
    1. Fetch and import trips
    2. Reconcile trips
    3. Post trips to ledger
    
    This task can be used for manual processing or as an alternative
    to running individual tasks separately.
    """
    task_id = self.request.id
    logger.info("[Task ID: %s] Starting full CURB trip processing", task_id)

    try:
        # Step 1: Fetch and import
        logger.info("[Task ID: %s] Step 1: Fetching and importing trips", task_id)
        import_result = fetch_and_import_curb_trips.apply()
        import_data = import_result.get()
        
        if import_data.get("status") == "no_data":
            logger.info("[Task ID: %s] No new trips to process", task_id)
            return {
                "status": "no_data",
                "task_id": task_id,
                "message": "No new trips to process"
            }

        # Step 2: Reconcile
        logger.info("[Task ID: %s] Step 2: Reconciling trips", task_id)
        reconcile_result = reconcile_curb_trips.apply()
        reconcile_data = reconcile_result.get()

        # Step 3: Post to ledger
        logger.info("[Task ID: %s] Step 3: Posting trips to ledger", task_id)
        post_result = post_curb_trips.apply()
        post_data = post_result.get()

        logger.info("[Task ID: %s] Full processing completed successfully", task_id)

        return {
            "status": "success",
            "task_id": task_id,
            "import_result": import_data.get("import_result"),
            "reconcile_result": reconcile_data.get("reconcile_result"),
            "post_result": post_data.get("post_result"),
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(
            "[Task ID: %s] Error in full CURB trip processing: %s",
            task_id, str(e), exc_info=True
        )
        raise


@shared_task(bind=True, name='app.curb.tasks.manual_fetch_curb_trips')
def manual_fetch_curb_trips(
    self,
    from_date: str,
    to_date: str,
    driver_id: Optional[str] = None,
    cab_number: Optional[str] = None,
    import_by: str = "MANUAL"
):
    """
    Manually fetch and import CURB trips for a specific date range.
    
    This task is useful for:
    - Backfilling historical data
    - Reprocessing specific date ranges
    - Testing with specific drivers or vehicles
    
    Args:
        from_date: Start date in MM/DD/YYYY format
        to_date: End date in MM/DD/YYYY format
        driver_id: Optional driver ID filter
        cab_number: Optional cab number filter
        import_by: User or system performing import
    """
    task_id = self.request.id
    logger.info(
        "[Task ID: %s] Manual fetch requested: %s to %s",
        task_id, from_date, to_date
    )

    try:
        # Fetch card transactions
        card_xml = fetch_trans_by_date_cab12(
            from_datetime=from_date,
            to_datetime=to_date,
            cab_number=cab_number or ""
        )

        # Fetch cash trips
        cash_xml = fetch_trips_log10(
            from_date=from_date,
            to_date=to_date,
            recon_stat=-1,
            cab_number=cab_number or "",
            driver_id=driver_id or ""
        )

        if not card_xml and not cash_xml:
            raise ValueError("No trip data found for the specified date range")

        # Import trips
        import asyncio
        
        async def import_trips_async():
            async for db in get_async_db():
                try:
                    repo = CURBRepository(db)
                    service = CURBService(repo)
                    
                    result = await service.import_trips(
                        xml_data=card_xml,
                        cash_xml_data=cash_xml,
                        import_source="Manual",
                        import_by=import_by
                    )
                    
                    return result
                finally:
                    await db.close()

        import_result = asyncio.run(import_trips_async())

        logger.info(
            "[Task ID: %s] Manual import completed: %d imported",
            task_id, import_result.success_count
        )

        return {
            "status": "success",
            "task_id": task_id,
            "from_date": from_date,
            "to_date": to_date,
            "import_result": {
                "log_id": import_result.log_id,
                "total_records": import_result.total_records,
                "success_count": import_result.success_count,
                "duplicate_count": import_result.duplicate_count,
            },
            "processed_at": datetime.now(timezone.utc).isoformat()
        }

    except Exception as e:
        logger.error(
            "[Task ID: %s] Error in manual fetch: %s",
            task_id, str(e), exc_info=True
        )
        raise