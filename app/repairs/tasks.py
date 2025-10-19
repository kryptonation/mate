# app/repairs/tasks.py

"""
Celery tasks for Vehicle Repairs module.
Handles automated posting of repair installments on schedule.
"""

import asyncio
from datetime import date
from celery import shared_task

from app.core.db import AsyncSessionLocal
from app.repairs.services import RepairService
from app.utils.logger import get_logger

logger = get_logger(__name__)


@shared_task(name="repairs.process_scheduled_installments")
def process_scheduled_repair_installments():
    """
    Celery task to process scheduled repair installments.
    
    This task runs every Sunday at 05:00 AM to:
    1. Find all installments scheduled for the current payment period
    2. Post them to the ledger
    3. Update installment and invoice statuses
    
    This is the automated version of the manual posting endpoint.
    """
    
    async def _process():
        async with AsyncSessionLocal() as db:
            try:
                service = RepairService(db=db)
                posting_date = date.today()
                
                logger.info(f"Starting automated repair installment posting for {posting_date}")
                
                result = await service.post_due_installments(posting_date)
                
                logger.info(
                    "Completed repair installment posting",
                    posted_count=result["posted_count"],
                    failed_count=result["failed_count"]
                )
                
                return result
                
            except Exception as e:
                logger.error(f"Error in automated repair posting: {str(e)}")
                raise
    
    # Run the async function
    loop = asyncio.get_event_loop()
    if loop.is_running():
        # If loop is already running, create a new one
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_process())
        return result
    finally:
        if not loop.is_running():
            loop.close()


@shared_task(name="repairs.close_fully_paid_invoices")
def close_fully_paid_invoices():
    """
    Celery task to close invoices that are fully paid.
    
    This task runs daily to ensure invoices are properly closed
    when all installments have been posted and balance is zero.
    """
    async def _close_invoices():
        async with AsyncSessionLocal() as db:
            try:
                from app.repairs.repository import RepairRepository
                from app.repairs.schemas import InvoiceStatus, InstallmentStatus
                
                repo = RepairRepository(db)
                
                logger.info("Checking for fully paid invoices to close")
                
                # Get all open invoices
                open_invoices = await repo.get_invoices_by_status(InvoiceStatus.OPEN)
                
                closed_count = 0
                for invoice in open_invoices:
                    # Check if all installments are posted/paid and balance is zero
                    all_posted = all(
                        inst.status in [InstallmentStatus.POSTED, InstallmentStatus.PAID]
                        for inst in invoice.installments
                    )
                    
                    if all_posted and invoice.balance <= 0.01:
                        invoice.status = InvoiceStatus.CLOSED
                        await repo.update_invoice(invoice)
                        closed_count += 1
                        logger.info("Closed fully paid invoice", repair_id=invoice.repair_id)
                
                await db.commit()
                
                logger.info(f"Closed {closed_count} fully paid invoices")
                return {"closed_count": closed_count}
                
            except Exception as e:
                logger.error(f"Error closing fully paid invoices: {str(e)}")
                raise
    
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(_close_invoices())
        return result
    finally:
        if not loop.is_running():
            loop.close()