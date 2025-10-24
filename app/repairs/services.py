# app/repairs/services.py

"""
Business Logic Layer for Vehicle Repairs module.
Implements all business rules and orchestrates repository operations.
"""

from typing import List, Tuple
from datetime import datetime, date, timezone

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_db
from app.repairs.repository import RepairRepository
from app.repairs.models import RepairInvoice, RepairInstallment
from app.repairs.schemas import (
    RepairInvoiceCreate, RepairInvoiceUpdate, RepairInvoiceFilters,
    RepairInstallmentFilters, InvoiceStatus, InstallmentStatus,
)
from app.repairs.exceptions import (
    RepairNotFoundException, DuplicateInvoiceException,
    InvalidRepairAmountException, InvalidPaymentScheduleException,
    RepairStateException, RepairCancellationException,
)
from app.repairs.utils import (
    calculate_weekly_installment, generate_payment_schedule,
    generate_repair_id, generate_installment_id,
    validate_invoice_date, validate_repair_amount,
    validate_state_transition
)
from app.ledger.services import LedgerService
from app.ledger.schemas import LedgerCategory
from app.utils.logger import get_logger

logger = get_logger(__name__)


class RepairService:
    """
    Service layer for repair operations.
    Handles business logic and orchestrates repository calls.
    """

    def __init__(self, db: AsyncSession = Depends(get_async_db)):
        self.db = db
        self.repo = RepairRepository(db)

    # === Invoice Operations ===

    async def create_repair_invoice(
        self, invoice_data: RepairInvoiceCreate, user_id: int
    ) -> RepairInvoice:
        """
        Create a new repair invoice with auto-generated payment schedule.
        
        Business Rules:
        1. Validate invoice date (must be <= today)
        2. Validate repair amount (must be >= $1)
        3. Check for duplicate invoice
        4. Generate unique repair_id
        5. Calculate weekly installment from payment matrix
        6. Generate payment schedule
        7. Create invoice in DRAFT status
        8. Create all installments
        
        Args:
            invoice_data: Invoice creation data
            user_id: ID of user creating the invoice
            
        Returns:
            Created RepairInvoice with installments
            
        Raises:
            InvalidRepairAmountException: If amount is invalid
            DuplicateInvoiceException: If invoice already exists
            InvalidPaymentScheduleException: If schedule generation fails
        """
        logger.info(
            "Creating repair invoice",
            invoice_number=invoice_data.invoice_number,
            vehicle_id=invoice_data.vehicle_id,
            amount=invoice_data.repair_amount,
        )

        # === Validate invoice date ===
        if not validate_invoice_date(invoice_data.invoice_date):
            raise InvalidPaymentScheduleException(
                "Invoice date cannot be in the future.",
                repair_amount=invoice_data.repair_amount
            )
        
        # === Validate repair amount ===
        if not validate_repair_amount(invoice_data.repair_amount):
            raise InvalidRepairAmountException(invoice_data.repair_amount)
        
        # === Check for duplicate invoice ===
        is_duplicate = await self.repo.check_duplicate_invoice(
            invoice_data.invoice_number,
            invoice_data.vehicle_id,
            invoice_data.invoice_date,
        )
        if is_duplicate:
            raise DuplicateInvoiceException(
                invoice_data.invoice_number,
                invoice_data.vehicle_id,
                str(invoice_data.invoice_date)
            )
        
        # === Generate repair ID ===
        year = invoice_data.invoice_date.year
        sequence = await self.repo.get_next_repair_sequence(year)
        repair_id = generate_repair_id(year, sequence)

        # === Calculate weekly installment ===
        weekly_installment = calculate_weekly_installment(invoice_data.repair_amount)

        # === Create invoice entity ===
        invoice = RepairInvoice(
           repair_id=repair_id,
            invoice_number=invoice_data.invoice_number,
            invoice_date=invoice_data.invoice_date,
            vin=invoice_data.vin,
            plate_number=invoice_data.plate_number,
            medallion_number=invoice_data.medallion_number,
            hack_license_number=invoice_data.hack_license_number,
            driver_id=invoice_data.driver_id,
            vehicle_id=invoice_data.vehicle_id,
            medallion_id=invoice_data.medallion_id,
            lease_id=invoice_data.lease_id,
            workshop_type=invoice_data.workshop_type,
            repair_description=invoice_data.repair_description,
            repair_amount=invoice_data.repair_amount,
            weekly_installment=weekly_installment,
            balance=invoice_data.repair_amount,
            start_week=invoice_data.start_week,
            status=InvoiceStatus.DRAFT,
            created_by=user_id,
            modified_by=user_id 
        )

        # === Save invoice ===
        invoice = await self.repo.create_invoice(invoice)

        # === Generate and create payment schedule ===
        try:
            installments = await self._generate_and_create_installments(
                invoice.id,
                repair_id,
                invoice_data.repair_amount,
                invoice_data.invoice_date,
                invoice_data.start_week.value
            )
            logger.info(
                f"Created repair invoice with {len(installments)} installments",
                repair_id=repair_id,
                invoice_id=invoice.id
            )
        except Exception as e:
            logger.error(f"Failed to generate payment schedule: {str(e)}")
            raise InvalidPaymentScheduleException(
                f"Failed to generate payment schedule: {str(e)}",
                repair_amount=invoice_data.repair_amount
            )
        
        await self.db.commit()
        await self.db.refresh(invoice)

        return invoice
    
    async def _generate_and_create_installments(
        self,
        invoice_id: int,
        repair_id: str,
        repair_amount: float,
        invoice_date: date,
        start_week: str
    ) -> List[RepairInstallment]:
        """
        Generate and create installments for a repair invoice.
        
        Args:
            invoice_id: ID of the parent invoice
            repair_id: Repair ID string
            repair_amount: Total repair amount
            invoice_date: Date of invoice
            start_week: When to start repayment
            
        Returns:
            List of created RepairInstallment objects
        """
        # === Generate pyament schedule ===
        schedule = generate_payment_schedule(repair_amount, invoice_date, start_week)

        # === Create installment entities ===
        installments = []
        for item in schedule:
            installment_id_str = generate_installment_id(repair_id, item["sequence"])

            installment = RepairInstallment(
                repair_invoice_id=invoice_id,
                installment_id=installment_id_str,
                week_start_date=item["week_start_date"],
                week_end_date=item["week_end_date"],
                payment_amount=item["payment_amount"],
                prior_balance=item["prior_balance"],
                balance=item["balance"],
                status=InstallmentStatus.SCHEDULED
            )
            installments.append(installment)

        # === Bulk create installments ===
        created_installments = await self.repo.create_installments(installments)
        return created_installments
    
    async def confirm_repair_invoice(self, invoice_id: int, user_id: int) -> RepairInvoice:
        """
        Confirm a draft repair invoice, moving it to OPEN status.
        
        Args:
            invoice_id: ID of invoice to confirm
            user_id: ID of user confirming
            
        Returns:
            Updated RepairInvoice
            
        Raises:
            RepairNotFoundException: If invoice not found
            RepairStateException: If invalid state transition
        """
        invoice = await self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise RepairNotFoundException(repair_id=invoice_id)
        
        # === Validate state transition ===
        is_valid, error_msg = validate_state_transition(
            invoice.status.value,
            InvoiceStatus.OPEN.value
        )
        if not is_valid:
            raise RepairStateException(
                invoice.status.value,
                InvoiceStatus.OPEN.value,
                error_msg
            )
        
        invoice.status = InvoiceStatus.OPEN
        invoice.modified_by = user_id
        invoice.updated_on = datetime.now(timezone.utc)

        await self.repo.update_invoice(invoice)
        await self.db.commit()

        logger.info(
            "Confirmed repair invoice",
            repair_id=invoice.repair_id,
            invoice_id=invoice.id
        )

        return invoice
    
    async def update_repair_invoice(
        self, invoice_id: int, update_data: RepairInvoiceUpdate, user_id: int
    ) -> RepairInvoice:
        """
        Update a repair invoice.
        
        Args:
            invoice_id: ID of invoice to update
            update_data: Update data
            user_id: ID of user updating
            
        Returns:
            Updated RepairInvoice
            
        Raises:
            RepairNotFoundException: If invoice not found
        """
        invoice = await self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise RepairNotFoundException(repair_id=invoice_id)
        
        # === Update fields if provided ===
        if update_data.invoice_number is not None:
            invoice.invoice_number = update_data.invoice_number
        if update_data.invoice_date is not None:
            invoice.invoice_date = update_data.invoice_date
        if update_data.repair_description is not None:
            invoice.repair_description = update_data.repair_description
        if update_data.status is not None:
            # Validate state transition
            is_valid, error_msg = validate_state_transition(
                invoice.status.value,
                update_data.status.value
            )
            if not is_valid:
                raise RepairStateException(
                    invoice.status.value,
                    update_data.status.value,
                    error_msg
                )
            invoice.status = update_data.status
        
        # If repair amount changes, regenerate payment schedule
        if update_data.repair_amount is not None and update_data.repair_amount != invoice.repair_amount:
            if invoice.status != InvoiceStatus.DRAFT:
                raise RepairStateException(
                    invoice.status.value,
                    "AMOUNT_CHANGE",
                    "Cannot change repair amount after invoice is confirmed"
                )
            
            # Delete existing installments
            for installment in invoice.installments:
                await self.db.delete(installment)
            
            # Recalculate and regenerate
            invoice.repair_amount = update_data.repair_amount
            invoice.weekly_installment = calculate_weekly_installment(update_data.repair_amount)
            invoice.balance = update_data.repair_amount
            
            await self._generate_and_create_installments(
                invoice.id,
                invoice.repair_id,
                invoice.repair_amount,
                invoice.invoice_date,
                invoice.start_week.value
            )
        
        invoice.modified_by = user_id
        invoice.updated_on = datetime.utcnow()
        
        await self.repo.update_invoice(invoice)
        await self.db.commit()
        
        logger.info(
            f"Updated repair invoice",
            repair_id=invoice.repair_id,
            invoice_id=invoice.id
        )
        
        return invoice
    
    async def hold_repair_invoice(self, invoice_id: int, user_id: int) -> RepairInvoice:
        """
        Put repair invoice on hold (freezes installment postings).
        
        Args:
            invoice_id: ID of invoice to hold
            user_id: ID of user performing action
            
        Returns:
            Updated RepairInvoice
        """
        invoice = await self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise RepairNotFoundException(repair_id=invoice_id)
        
        is_valid, error_msg = validate_state_transition(
            invoice.status.value,
            InvoiceStatus.HOLD.value
        )
        if not is_valid:
            raise RepairStateException(
                invoice.status.value,
                InvoiceStatus.HOLD.value,
                error_msg
            )
        
        invoice.status = InvoiceStatus.HOLD
        invoice.modified_by = user_id
        invoice.updated_on = datetime.utcnow()
        
        await self.repo.update_invoice(invoice)
        await self.db.commit()
        
        logger.info(f"Put repair invoice on hold", repair_id=invoice.repair_id)
        
        return invoice
    
    async def cancel_repair_invoice(
        self,
        invoice_id: int,
        user_id: int
    ) -> RepairInvoice:
        """
        Cancel a repair invoice.
        Only allowed if no installments have been posted.
        
        Args:
            invoice_id: ID of invoice to cancel
            user_id: ID of user performing action
            
        Returns:
            Cancelled RepairInvoice
            
        Raises:
            RepairCancellationException: If cancellation not allowed
        """
        invoice = await self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise RepairNotFoundException(repair_id=invoice_id)
        
        # Check if any installments have been posted
        posted_count = sum(1 for inst in invoice.installments 
                          if inst.status in [InstallmentStatus.POSTED, InstallmentStatus.PAID])
        
        if posted_count > 0:
            raise RepairCancellationException(
                invoice_id,
                f"{posted_count} installments have already been posted"
            )
        
        is_valid, error_msg = validate_state_transition(
            invoice.status.value,
            InvoiceStatus.CANCELLED.value
        )
        if not is_valid:
            raise RepairStateException(
                invoice.status.value,
                InvoiceStatus.CANCELLED.value,
                error_msg
            )
        
        invoice.status = InvoiceStatus.CANCELLED
        invoice.modified_by = user_id
        invoice.updated_on = datetime.utcnow()
        
        # Cancel all scheduled installments
        for installment in invoice.installments:
            if installment.status == InstallmentStatus.SCHEDULED:
                installment.status = InstallmentStatus.PAID  # Mark as cleared
        
        await self.repo.update_invoice(invoice)
        await self.db.commit()
        
        logger.info(f"Cancelled repair invoice", repair_id=invoice.repair_id)
        
        return invoice
    
    async def get_repair_invoice(self, invoice_id: int) -> RepairInvoice:
        """Get repair invoice by ID."""
        invoice = await self.repo.get_invoice_by_id(invoice_id)
        if not invoice:
            raise RepairNotFoundException(repair_id=invoice_id)
        return invoice
    
    async def get_repair_invoice_by_repair_id(self, repair_id: str) -> RepairInvoice:
        """Get repair invoice by repair_id."""
        invoice = await self.repo.get_invoice_by_repair_id(repair_id)
        if not invoice:
            raise RepairNotFoundException(repair_id=repair_id)
        return invoice
    
    async def list_repair_invoices(
        self,
        filters: RepairInvoiceFilters,
        page: int = 1,
        per_page: int = 50,
        sort_by: str = "created_on",
        sort_order: str = "desc"
    ) -> Tuple[List[RepairInvoice], int]:
        """Get paginated list of repair invoices with filters."""
        return await self.repo.get_invoices_paginated(
            filters, page, per_page, sort_by, sort_order
        )
    
    # === Installment Operations ===

    async def get_installment(self, installment_id: int) -> RepairInstallment:
        """Get installment by ID."""
        installment = await self.repo.get_installment_by_id(installment_id)
        if not installment:
            raise RepairNotFoundException(installment_id=installment_id)
        return installment
    
    async def get_installments_for_invoice(
        self,
        invoice_id: int
    ) -> List[RepairInstallment]:
        """Get all installments for a repair invoice."""
        return await self.repo.get_installments_by_invoice(invoice_id)
    
    async def list_installments(
        self,
        filters: RepairInstallmentFilters,
        page: int = 1,
        per_page: int = 50,
        sort_by: str = "week_start_date",
        sort_order: str = "desc"
    ) -> Tuple[List[RepairInstallment], int]:
        """Get paginated list of installments with filters."""
        return await self.repo.get_installments_paginated(
            filters, page, per_page, sort_by, sort_order
        )
    
    # === Posting Operations ===

    async def post_due_installments(self, posting_date: date) -> dict:
        """
        Post installments that are due for the given date.
        This is a placeholder for future ledger integration.
        
        Business Rules:
        1. Find all installments with status=SCHEDULED and week_start <= posting_date
        2. For each installment:
           - Create ledger entry (PLACEHOLDER)
           - Update installment status to POSTED
           - Set ledger_posting_ref
           - Update invoice balance
        3. Close invoice if all installments are posted and balance = 0
        
        Args:
            posting_date: Date to post installments for (usually Sunday)
            
        Returns:
            Dictionary with posting results
        """
        logger.info(f"Processing installment postings for {posting_date}")
        
        # Get due installments
        due_installments = await self.repo.get_installments_due_for_posting(posting_date)
        
        posted_count = 0
        failed_count = 0
        details = []
        
        for installment in due_installments:
            try:
                # Skip if parent invoice is on HOLD or CANCELLED
                if installment.invoice.status in [InvoiceStatus.HOLD, InvoiceStatus.CANCELLED]:
                    logger.info(
                        f"Skipping installment - invoice is {installment.invoice.status}",
                        installment_id=installment.installment_id
                    )
                    continue
                
                ledger_service = LedgerService(self.repo.db)

                posting, balance = await ledger_service.create_obligation_posting(
                    category=LedgerCategory.REPAIR,
                    reference_id=installment.installment_id,
                    reference_type="REPAIR_INSTALLMENT",
                    amount=installment.payment_amount,
                    driver_id=installment.invoice.driver_id,
                    vehicle_id=installment.invoice.vehicle_id,
                    vin=installment.invoice.vin,
                    plate=installment.invoice.plate,
                    medallion_id=installment.invoice.medallion_id,
                    lease_id=installment.invoice.lease_id,
                    transaction_date=posting_date,
                    description=f"Repair installment for invoice {installment.invoice.invoice_number}",
                    created_by=None  # System posting
                )

                ledger_ref = posting.posting_id
                
                # Update installment
                installment.status = InstallmentStatus.POSTED
                installment.ledger_posting_ref = ledger_ref
                await self.repo.update_installment(installment)
                
                # Update invoice balance
                invoice = installment.invoice
                invoice.balance = max(0, invoice.balance - installment.payment_amount)
                
                # Check if invoice should be closed
                all_posted = all(
                    inst.status in [InstallmentStatus.POSTED, InstallmentStatus.PAID]
                    for inst in invoice.installments
                )
                if all_posted and invoice.balance <= 0.01:
                    invoice.status = InvoiceStatus.CLOSED
                
                await self.repo.update_invoice(invoice)
                
                posted_count += 1
                details.append({
                    "installment_id": installment.installment_id,
                    "amount": installment.payment_amount,
                    "status": "posted",
                    "ledger_ref": ledger_ref
                })
                
                logger.info(
                    f"Posted installment",
                    installment_id=installment.installment_id,
                    amount=installment.payment_amount
                )
                
            except Exception as e:
                failed_count += 1
                details.append({
                    "installment_id": installment.installment_id,
                    "status": "failed",
                    "error": str(e)
                })
                logger.error(
                    f"Failed to post installment: {str(e)}",
                    installment_id=installment.installment_id
                )
        
        await self.db.commit()
        
        result = {
            "success": failed_count == 0,
            "total_processed": len(due_installments),
            "posted_count": posted_count,
            "failed_count": failed_count,
            "message": f"Posted {posted_count} of {len(due_installments)} installments",
            "details": details
        }
        
        logger.info(f"Installment posting completed", **result)
        return result
    
    # ==================== Statistics and Reporting ====================
    
    async def get_invoice_statistics(self) -> dict:
        """Get statistics about repair invoices."""
        return await self.repo.get_invoice_statistics()
    
    async def get_driver_repair_summary(self, driver_id: int) -> dict:
        """Get repair summary for a specific driver."""
        return await self.repo.get_driver_repair_summary(driver_id)