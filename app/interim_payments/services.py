# app/interim_payments/services.py

"""
Business logic layer for Interim Payments Operations.
Implements payment creation, allocation, posting, and validation logic.
"""

from datetime import datetime, timezone, date
from decimal import Decimal
from typing import List, Optional, Tuple

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_db
from app.interim_payments.repository import InterimPaymentRepository
from app.interim_payments.schemas import (
    InterimPaymentCreate, InterimPaymentUpdate, InterimPaymentFilters,
    InterimPaymentAllocationCreate, InterimPaymentAllocationFilters,
    InterimPaymentLogCreate, InterimPaymentCreationResult,
    AllocationResult, ObligationListResponse,
    ObligationItem, PaymentAllocationRequest, PaymentReceiptResponse,
    ReceiptLineItem, AllocationCategory, LogType, LogStatus,
)
from app.interim_payments.models import InterimPayment, InterimPaymentAllocation
from app.interim_payments.exceptions import (
    InterimPaymentNotFoundException, PaymentCreationException,
    AllocationExceedsPaymentException,
    PaymentAllocationException, ObligationNotFoundException,
    InsufficientOutstandingBalanceException,
    TaxAllocationException, DriverNotFoundException, MedallionNotFoundException,
    InvalidPaymentAmountException, PaymentVoidException,
)

# Import models from other modules for obligation lookup
from app.drivers.models import Driver
from app.medallions.models import Medallion
from app.repairs.models import RepairInvoice
from app.driver_loans.models import DriverLoan
from app.ledger.schemas import LedgerCategory as LedgerCat
from app.ledger.services import LedgerService

from app.utils.logger import get_logger

logger = get_logger(__name__)

def get_interim_payment_repository(
    db: AsyncSession = Depends(get_async_db),
) -> InterimPaymentRepository:
    """Dependency to get InterimPaymentRepository instance."""
    return InterimPaymentRepository(db)


class InterimPaymentService:
    """
    Business logic layer for Interim Payment Operations.
    Implements payment lifecycle management and allocation logic.
    """

    def __init__(
        self, repo: InterimPaymentRepository = Depends(get_interim_payment_repository)
    ):
        self.repo = repo
        logger.debug("InterimPaymentService initialized.")

    # === Payment Creation and Management ===

    async def create_payment_with_allocations(
        self, payment_request: PaymentAllocationRequest, created_by: int
    ) -> InterimPaymentCreationResult:
        """
        Create a new interim payment with allocations.

        This is the main entry point for creating payments from the UI.
        It handles validation, allocation, ledger posting, and receipt generation.
        """
        try:
            logger.info(
                "Creating interim payment with allocations",
                driver_id=payment_request.driver_id,
                amount=str(payment_request.total_amount)
            )

            # === Step 1: Validate driver and medallion exist ===
            await self._validate_driver_and_medallion(
                payment_request.driver_id, payment_request.medallion_id
            )

            # === Step 2: Validate allocations ===
            await self._validate_allocations(
                payment_request.allocations, payment_request.total_amount
            )

            # === Step 3: Generate Payment ID and receipt number ===
            year = payment_request.payment_date.year
            next_number = await self.repo.get_next_payment_number(year)
            payment_id = f"IMP-{year}-{next_number:04d}"

            receipt_number = await self.repo.get_next_receipt_number()

            # === Step 4: Create Payment Record ===
            payment_data = InterimPaymentCreate(
                driver_id=payment_request.driver_id,
                medallion_id=payment_request.medallion_id,
                lease_id=payment_request.lease_id,
                payment_date=payment_request.payment_date,
                total_amount=payment_request.total_amount,
                payment_method=payment_request.payment_method,
                check_number=payment_request.check_number,
                notes=payment_request.notes,
                allocations=[]
            )

            payment = await self.repo.create_payment(
                payment_data, payment_id, receipt_number
            )

            # === Step 5: Process allocations ===
            allocation_results = await self._process_allocations(
                payment.id, payment_request.allocations
            )

            # === Step 6: Handle unallocated amount (auto-apply to Lease) ===
            total_allocated = sum(a.allocated_amount for a in allocation_results)
            unallocated = payment_request.total_amount - total_allocated

            if unallocated > Decimal("0.00"):
                logger.info(
                    "Auto-applying unallocated amount to Lease",
                    amount=str(unallocated)
                )

                lease_allocation = await self._auto_apply_to_lease(
                    payment.id, payment_request.medallion_id, payment_request.lease_id, unallocated
                )
                allocation_results.append(lease_allocation)
                total_allocated += unallocated

            # === Step 7: Update payment amounts ===
            await self.repo.update_payment_amounts(
                payment, total_allocated, Decimal("0.00")
            )

            # === Step 8: Create log entry ===
            await self.repo.create_log(
                InterimPaymentLogCreate(
                    log_date=datetime.now(timezone.utc),
                    log_type=LogType.CREATE,
                    payment_id=payment.id,
                    records_impacted=len(allocation_results),
                    status=LogStatus.SUCCESS,
                    details=f"Payment created with {len(allocation_results)} allocations."
                )
            )

            # === Step 9: Commit transaction ===
            await self.repo.commit()

            # === Step 10: Refresh Payment to get updated relationships ===
            payment = await self.repo.get_payment_by_id(payment.id)

            logger.info(
                "Payment created successfully",
                payment_id=payment_id,
                allocations=len(allocation_results)
            )

            return InterimPaymentCreationResult(
                success=True,
                payment_id=payment_id,
                message=f"Payment created successfully with {len(allocation_results)} allocations.",
                payment=payment,
                receipt_number=receipt_number,
            )
        
        except Exception as e:
            await self.repo.rollback()
            logger.error("Failed to create payment", error=str(e), exc_info=True)

            # Create failure log
            try:
                await self.repo.create_log(
                    InterimPaymentLogCreate(
                        log_date=datetime.now(timezone.utc),
                        log_type=LogType.CREATE,
                        payment_id=None,
                        records_impacted=0,
                        status=LogStatus.FAILURE,
                        details="Payment creation failed",
                        error_message=str(e)
                    )
                )
                await self.repo.commit()
            except:
                pass

            raise PaymentCreationException(str(e)) from e
        
    async def _validate_driver_and_medallion(
        self, driver_id: int, medallion_id: int
    ) -> None:
        """Validate that driver and medallion exist."""
        logger.debug("Validating driver and medallion", driver_id=driver_id)

        # === Check driver exists ===
        stmt = select(Driver).where(Driver.id == driver_id)
        result = await self.repo.db.execute(stmt)
        driver = result.scalar_one_or_none()

        if not driver:
            raise DriverNotFoundException(driver_id)
        
        # === Check medallion exists ===
        stmt = select(Medallion).where(Medallion.id == medallion_id)
        result = await self.repo.db.execute(stmt)
        medallion = result.scalar_one_or_none()

        if not medallion:
            raise MedallionNotFoundException(medallion_id)
        
    async def _validate_allocations(self, allocations: List, total_amount: Decimal) -> None:
        """Validate allocation amounts and categories."""
        logger.debug("Validating allocations", count=len(allocations))

        if not allocations:
            raise PaymentAllocationException("At least one allocation is required.")
        
        # === Check total doesn't exceed payment amount ===
        total_allocated = sum(a.amount for a in allocations)
        if total_allocated > total_amount:
            raise AllocationExceedsPaymentException(
                float(total_amount), float(total_allocated)
            )
        
        # === Validate each allocation ===
        for alloc in allocations:
            # === Check amount is positive ===
            if alloc.amount <= 0:
                raise InvalidPaymentAmountException(
                    float(alloc.amount),
                    "Allocation amount must be greater than zero."
                )
            
            # === Check category is not Tax (taxes cannot receive interim payments) ===
            if alloc.category.upper() in ["TAX", "MTA", "TIF", "CONGESTION", "CBDT", "AIRPORT"]:
                raise TaxAllocationException()
            
    async def _process_allocations(
        self, payment_id: int, allocation_requests: List
    ) -> List[AllocationResult]:
        """Process and create allocation records with ledger posting."""
        logger.debug("Processing allocations", payment_id=payment_id)

        results = []

        for alloc_req in allocation_requests:
            try:
                # === Get current outstanding balance for the obligation ===
                outstanding_before = await self._get_outstanding_balance(
                    alloc_req.category, alloc_req.reference_id
                )

                # === Validate allocation doesn't exceed outstanding ===
                if alloc_req.amount > outstanding_before:
                    raise InsufficientOutstandingBalanceException(
                        alloc_req.category.value,
                        alloc_req.reference_id,
                        float(outstanding_before),
                        float(alloc_req.amount)
                    )
                
                # === Calculate new balance ===
                outstanding_after = outstanding_before - alloc_req.amount

                # === Get description ===
                description = await self._get_obligation_description(
                    alloc_req.category, alloc_req.reference_id
                )

                # === Create allocation record ===
                allocation_data = InterimPaymentAllocationCreate(
                    category=alloc_req.category,
                    reference_id=alloc_req.reference_id,
                    description=description,
                    allocated_amount=alloc_req.amount,
                    outstanding_before=outstanding_before,
                )

                allocation = await self.repo.create_allocation(
                    payment_id, allocation_data
                )

                # === Post to ledger (updates Ledger_Balances) ===
                ledger_ref = await self._post_allocaction_to_ledger(
                    allocation,
                    alloc_req.category,
                    alloc_req.reference_id,
                    alloc_req.amount
                )

                # === Update allocation with ledger reference ===
                await self.repo.update_allocation_ledger_ref(
                    alloc_req.category,
                    alloc_req.reference_id,
                    outstanding_after
                )

                results.append(AllocationResult(
                    category=alloc_req.category.value,
                    reference_id=alloc_req.reference_id,
                    allocated_amount=alloc_req.amount,
                    outstanding_before=outstanding_before,
                    outstanding_after=outstanding_after,
                    ledger_posting_ref=ledger_ref
                ))

                logger.info(
                    "Allocation processed",
                    category=alloc_req.category.value,
                    reference_id=alloc_req.reference_id,
                    amount=str(alloc_req.amount)
                )

            except Exception as e:
                logger.error(
                    "Failed to process allocation",
                    category=alloc_req.category.value,
                    reference_id=alloc_req.reference_id,
                    error=str(e)
                )
                raise

        return results
    
    async def _auto_apply_to_lease(
        self, payment_id: int, medallion_id: int, lease_id: Optional[int], amount: Decimal
    ) -> AllocationResult:
        """Auto-apply unallocated amount to Lease."""
        logger.info("Auto-applying to Lease", amount=str(amount))

        # === Find active lease or most recent lease ===
        if lease_id:
            lease_ref = f"LEASE-{lease_id}"
        else:
            lease_ref = f"MEDALLION-{medallion_id}-LEASE"

        # === Get current lease outstanding balance ===
        outstanding_before = await self._get_outstanding_balance(
            AllocationCategory.LEASE, lease_ref
        )

        outstanding_after = outstanding_before - amount

        # === Create allocation ===
        allocation_data = InterimPaymentAllocationCreate(
            category=AllocationCategory.LEASE,
            reference_id=lease_ref,
            description="Auto-applied excess payment to Lease",
            allocated_amount=amount,
            outstanding_before=outstanding_before
        )

        allocation = await self.repo.create_allocation(payment_id, allocation_data)

        # === Post to ledger ===
        ledger_ref = await self._post_allocation_to_ledger(
            allocation, AllocationCategory.LEASE, lease_ref, amount
        )

        await self.repo.update_allocation_ledger_ref(allocation, ledger_ref)

        # === Update lease balance ===
        await self._update_obligation_balance(
            AllocationCategory.LEASE, lease_ref, outstanding_after
        )

        return AllocationResult(
            category=AllocationCategory.LEASE.value,
            reference_id=lease_ref,
            allocated_amount=amount,
            outstanding_before=outstanding_before,
            outstanding_after=outstanding_after,
            ledger_posting_ref=ledger_ref
        )
    
    async def _get_outstanding_balance(
        self, category: AllocationCategory, reference_id: str
    ) -> Decimal:
        """
        Get current outstanding balance for an obligation from Ledger_Balances.

        NOTE: This assumes Ledger_Balances table exists with structure:
        - category (Lease/Repair/Loan/EZPass/PVB/Misc)
        - reference_id
        - outstanding_balance
        """
        logger.debug(
            "Getting outstanding balance",
            category=category.value,
            reference_id=reference_id
        )

        ledger_service = LedgerService(self.repo.db)

        balance = await ledger_service.get_outstanding_balance(
            reference_id=reference_id,
            reference_type=category.value
        )

        if balance is None:
            raise ObligationNotFoundException(category.value, reference_id)
        
        return balance
        
    async def _get_obligation_description(
        self, category: AllocationCategory, reference_id: str
    ) -> str:
        """Get human-readable description for an obligation."""
        logger.debug(
            "Getting obligation description",
            category=category.value,
            reference_id=reference_id
        )

        try:
            if category == AllocationCategory.REPAIR:
                # Query repair invoice
                stmt = select(RepairInvoice).where(
                    RepairInvoice.invoice_number == reference_id
                )
                result = await self.repo.db.execute(stmt)
                repair = result.scalar_one_or_none()
                if repair:
                    return f"Repair Invoice #{reference_id} - {repair.workshop_type}"
                
            elif category == AllocationCategory.LOAN:
                # Query driver loan
                stmt = select(DriverLoan).where(
                    DriverLoan.loan_id == reference_id
                )
                result = await self.repo.db.execute(stmt)
                loan = result.scalar_one_or_none()
                if loan:
                    return f"Driver Loan {reference_id} - {loan.purpose or 'Cash Advance'}"
                
            elif category == AllocationCategory.EZPASS:
                # Query EZPass transaction
                return f"EZPass Toll - Transaction {reference_id}"
                
            elif category == AllocationCategory.PVB:
                # Query PVB violation
                return f"PVB Violation - Ticket {reference_id}"
                
            elif category == AllocationCategory.LEASE:
                return f"Lease Payment - {reference_id}"
                
            elif category == AllocationCategory.MISC:
                return f"Miscellaneous - {reference_id}"

        except Exception as e:
            logger.warning(
                "Could not get detailed description",
                category=category.value,
                reference_id=reference_id,
                error=str(e)
            )

        # Fallback description
        return f"{category.value} - {reference_id}"
    
    async def _post_allocation_to_ledger(
        self,
        allocation: InterimPaymentAllocation,
        category: AllocationCategory,
        reference_id: str,
        amount: Decimal
    ) -> str:
        """
        Post allocation to Ledger_Postings table.
        
        NOTE: This creates a posting that reduces Ledger_Balances.
        Ledger_Postings = audit trail of all payments/allocations.
        """
        logger.debug(
            "Posting allocation to ledger",
            category=category.value,
            reference_id=reference_id,
            amount=str(amount)
        )

        # === Map Interim Payment category to ledger category ===
        category_mapping = {
            AllocationCategory.LEASE: LedgerCat.LEASE,
            AllocationCategory.REPAIR: LedgerCat.REPAIR,
            AllocationCategory.LOAN: LedgerCat.LOAN,
            AllocationCategory.EZPASS: LedgerCat.EZPASS,
            AllocationCategory.PVB: LedgerCat.PVB,
            AllocationCategory.MISC: LedgerCat.MISC,
        }

        ledger_category = category_mapping.get(category, LedgerCat.MISC)

        # === User LedgerService to apply payment ===
        ledger_service = LedgerService(self.repo.db)

        # === Get balance_id for this reference ===
        balance = await ledger_service.repo.get_balance_by_reference(
            reference_id=reference_id,
            reference_type=category.value
        )

        if not balance:
            raise ObligationNotFoundException(category.value, reference_id)
        
        # === Apply Payment ===
        posting, updated_balance = await ledger_service.apply_payment_to_balance(
            balance_id=balance.balance_id,
            payment_amount=amount,
            payment_source="INTERIM_PAYMENT",
            payment_source_id=str(allocation.payment_id),
            created_by=allocation.created_by
        )

        logger.info("Ledger posting created", ledger_ref=posting.posting_id)
        return posting.posting_id
    
    async def _update_obligation_balance(
        self,
        category: AllocationCategory,
        reference_id: str,
        new_balance: Decimal
    ) -> None:
        """
        Update outstanding balance in Ledger_Balances table.
        """
        logger.debug(
            "Updating obligation balance",
            category=category.value,
            reference_id=reference_id,
            new_balance=str(new_balance)
        )

        # TODO: Replace with actual Ledger_Balances update
        # In production, this would:
        # UPDATE ledger_balances 
        # SET outstanding_balance = new_balance
        # WHERE category = ? AND reference_id = ?
        
        # Actual implementation:
        # from app.ledger.models import LedgerBalance
        # stmt = (
        #     select(LedgerBalance)
        #     .where(
        #         and_(
        #             LedgerBalance.category == category.value,
        #             LedgerBalance.reference_id == reference_id
        #         )
        #     )
        # )
        # result = await self.repo.db.execute(stmt)
        # ledger_balance = result.scalar_one_or_none()
        # 
        # if ledger_balance:
        #     ledger_balance.outstanding_balance = new_balance
        #     if new_balance <= Decimal("0.00"):
        #         ledger_balance.status = "Closed"
        #     await self.repo.db.flush()
        
        logger.info("Balance updated", new_balance=str(new_balance))

    # === Query Operations ===

    async def get_payment_by_id(self, payment_id: int) -> InterimPayment:
        """Get a single payment by ID."""
        logger.info("Getting payment by ID", payment_id=payment_id)

        payment = await self.repo.get_payment_by_id(payment_id)
        if not payment:
            logger.error("Payment not found", payment_id=payment_id)
            raise InterimPaymentNotFoundException(payment_id)

        return payment

    async def get_payments(
        self, filters: InterimPaymentFilters
    ) -> Tuple[List[InterimPayment], int]:
        """Get payments with filters and pagination."""
        logger.info("Getting payments with filters", filters=filters.model_dump())

        payments, total_count = await self.repo.get_payments(filters)
        logger.info("Retrieved payments", count=len(payments), total=total_count)

        return payments, total_count

    async def get_allocations(
        self, filters: InterimPaymentAllocationFilters
    ) -> Tuple[List[InterimPaymentAllocation], int]:
        """Get allocations with filters and pagination."""
        logger.info("Getting allocations with filters", filters=filters.model_dump())

        allocations, total_count = await self.repo.get_allocations(filters)
        logger.info("Retrieved allocations", count=len(allocations), total=total_count)

        return allocations, total_count

    # === UI Support Methods ===

    async def get_outstanding_obligations(
        self,
        driver_id: int,
        medallion_id: int,
        lease_id: Optional[int] = None
    ) -> ObligationListResponse:
        """
        Get all outstanding obligations for a driver/medallion.
        Used by the UI allocation screen.
        """
        logger.info(
            "Getting outstanding obligations",
            driver_id=driver_id,
            medallion_id=medallion_id
        )

        # Get driver info
        stmt = select(Driver).where(Driver.id == driver_id)
        result = await self.repo.db.execute(stmt)
        driver = result.scalar_one_or_none()
        
        if not driver:
            raise DriverNotFoundException(driver_id)

        # Get medallion info
        stmt = select(Medallion).where(Medallion.id == medallion_id)
        result = await self.repo.db.execute(stmt)
        medallion = result.scalar_one_or_none()
        
        if not medallion:
            raise MedallionNotFoundException(medallion_id)

        obligations = []
        total_outstanding = Decimal("0.00")

        # TODO: Query Ledger_Balances for all open obligations
        # This is a placeholder implementation
        # In production, you would:
        # 1. Query Ledger_Balances WHERE driver_id = ? AND medallion_id = ?
        # 2. Filter for outstanding_balance > 0
        # 3. Group by category
        # 4. Return structured list
        
        # Placeholder: return sample obligations
        sample_obligations = [
            ObligationItem(
                category=AllocationCategory.LEASE,
                reference_id=f"LEASE-{lease_id}" if lease_id else f"MED-{medallion_id}",
                description="Weekly Lease Payment",
                outstanding_amount=Decimal("275.00"),
                due_date=date.today(),
                age_days=7
            ),
            ObligationItem(
                category=AllocationCategory.REPAIR,
                reference_id="INV-2457",
                description="Engine Repair Invoice",
                outstanding_amount=Decimal("149.00"),
                due_date=date.today(),
                age_days=14
            ),
        ]

        for obligation in sample_obligations:
            total_outstanding += obligation.outstanding_amount
            obligations.append(obligation)

        return ObligationListResponse(
            driver_id=driver_id,
            driver_name=driver.name if hasattr(driver, 'name') else f"Driver {driver_id}",
            medallion_id=medallion_id,
            medallion_number=medallion.medallion_number if hasattr(medallion, 'medallion_number') else f"MED-{medallion_id}",
            lease_id=lease_id,
            obligations=obligations,
            total_outstanding=total_outstanding
        )

    async def generate_receipt(
        self, payment_id: int
    ) -> PaymentReceiptResponse:
        """Generate receipt for a payment."""
        logger.info("Generating receipt", payment_id=payment_id)

        payment = await self.get_payment_by_id(payment_id)

        # Build line items
        line_items = []
        auto_allocated_to_lease = None

        for allocation in payment.allocations:
            line_item = ReceiptLineItem(
                category=allocation.category,
                reference_id=allocation.reference_id,
                description=allocation.description or "",
                allocated_amount=allocation.allocated_amount,
                balance_remaining=allocation.outstanding_after
            )
            line_items.append(line_item)

            # Check if this is auto-allocated to lease
            if (allocation.category == AllocationCategory.LEASE.value and
                "auto-applied" in (allocation.description or "").lower()):
                auto_allocated_to_lease = allocation.allocated_amount

        receipt = PaymentReceiptResponse(
            receipt_number=payment.receipt_number,
            payment_id=payment.payment_id,
            driver_name=payment.driver.name if hasattr(payment.driver, 'name') else f"Driver {payment.driver_id}",
            driver_tlc_license=payment.driver.tlc_license if hasattr(payment.driver, 'tlc_license') else None,
            medallion_number=payment.medallion.medallion_number if hasattr(payment.medallion, 'medallion_number') else f"MED-{payment.medallion_id}",
            lease_id=f"LEASE-{payment.lease_id}" if payment.lease_id else None,
            payment_date=payment.payment_date,
            payment_method=payment.payment_method,
            check_number=payment.check_number,
            total_amount=payment.total_amount,
            line_items=line_items,
            auto_allocated_to_lease=auto_allocated_to_lease,
            issued_at=payment.receipt_issued_at,
            issued_by=None  # TODO: Get username from created_by
        )

        return receipt

    # === Transaction Management ===

    async def void_payment(
        self, payment_id: int, reason: str
    ) -> InterimPayment:
        """
        Void a payment (mark as voided, reverse ledger entries).
        
        NOTE: This should only be allowed for recent payments (same day)
        and requires proper authorization.
        """
        logger.info("Voiding payment", payment_id=payment_id)

        payment = await self.get_payment_by_id(payment_id)

        if payment.status == "Voided":
            raise PaymentVoidException(
                payment.payment_id,
                "Payment is already voided"
            )

        # TODO: Add business rules for voiding
        # - Only same-day voids allowed?
        # - Requires manager approval?
        # - Reverse all ledger postings
        
        payment.status = "Voided"
        payment.notes = f"{payment.notes or ''}\nVOIDED: {reason}"

        await self.repo.update_payment(
            payment,
            InterimPaymentUpdate(status="Voided", notes=payment.notes)
        )

        # TODO: Reverse ledger entries
        # For each allocation:
        # - Create reversing Ledger_Posting
        # - Restore Ledger_Balance

        await self.repo.commit()

        logger.info("Payment voided", payment_id=payment.payment_id)
        return payment
