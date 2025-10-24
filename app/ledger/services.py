# app/ledger/services.py

"""
Service layer for Centralized Ledger Module.
Implements all business logic for ledger operations.
"""

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Tuple
import uuid
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.logger import get_logger
from app.ledger.repository import LedgerRepository
from app.ledger.models import LedgerPosting, LedgerBalance
from app.ledger.schemas import (
    LedgerPostingCreate, LedgerPostingResponse, LedgerBalanceCreate,
    LedgerBalanceResponse, LedgerBalanceResponse, LedgerCategory,
    LedgerEntryType, LedgerStatus, BalanceStatus, PostingFilterParams,
    BalanceFilterParams, DriverLedgerSummary, ReconciliationResult,
    ReversalRequest, ReversalResponse,
)
from app.ledger.exceptions import (
    LedgerNotFoundException, InvalidLedgerEntryException,
    DuplicatePostingException, NegativeBalanceException,
    ImmutablePostingException, PostingVoidedException,
)

logger = get_logger(__name__)


# === Payment Hierarchy for Earnings Allocation ===

PAYMENT_HIERARCHY = [
    LedgerCategory.TAXES,
    LedgerCategory.EZPASS,
    LedgerCategory.LEASE,
    LedgerCategory.PVB,
    LedgerCategory.TLC,
    LedgerCategory.REPAIR,
    LedgerCategory.LOAN,
    LedgerCategory.MISC
]


class LedgerService:
    """
    Business logic for Centralized Ledger operations.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LedgerRepository(db)

    # === Core Posting Operations ===

    async def create_obligation_posting(
        self, category: LedgerCategory, reference_id: str,
        reference_type: str, amount: Decimal, driver_id: Optional[int] = None,
        vehicle_id: Optional[int] = None, vin: Optional[str] = None,
        plate: Optional[str] = None, medallion_id: Optional[int] = None,
        lease_id: Optional[int] = None, transaction_date: Optional[date] = None,
        description: Optional[str] = None, created_by: Optional[int] = None
    ) -> Tuple[LedgerPosting, LedgerBalance]:
        """
        Create a new obligation (DEBIT) posting and corresponding balance.
        
        This is called when:
        - Repair invoice created
        - Driver loan issued
        - EZPass toll imported
        - PVB/TLC violation imported
        - Lease fee scheduled
        - Tax/fee charged
        - Misc charge added
        
        Returns: (LedgerPosting, LedgerBalance)
        """
        logger.info(
            f"Creating obligation posting",
            category=category.value,
            reference_id=reference_id,
            amount=str(amount)
        )

        # === Validate inputs ===
        if amount <= 0:
            raise InvalidLedgerEntryException("Amount must be positive")
        
        if category == LedgerCategory.EARNINGS:
            raise InvalidLedgerEntryException("Cannot create obligation with Earnings category")

        # === Check for duplicate ===
        existing_balance = await self.repo.get_balance_by_reference(reference_id, reference_type)
        if existing_balance:
            raise DuplicatePostingException(f"Balance already exists for {reference_id} of type {reference_type}")
        
        try:
            # === Generate unique IDs ===
            posting_id = self._generate_posting_id()
            balance_id = self._generate_balance_id(category.value)

            # === Create DEBIT posting ===
            posting = LedgerPosting(
                posting_id=posting_id,
                category=category.value,
                entry_type=LedgerEntryType.DEBIT.value,
                amount=amount,
                driver_id=driver_id,
                vehicle_id=vehicle_id,
                vin=vin,
                plate=plate,
                medallion_id=medallion_id,
                lease_id=lease_id,
                reference_id=reference_id,
                reference_type=reference_type,
                status=LedgerStatus.POSTED.value,
                posted_on=datetime.now(timezone.utc),
                transaction_date=transaction_date or date.today(),
                description=description,
                created_by=created_by,
                modified_by=created_by
            )

            posting = await self.repo.create_posting(posting)

            # === Create corresponding balance ===
            balance = LedgerBalance(
                balance_id=balance_id,
                    category=category.value,
                    driver_id=driver_id,
                    vehicle_id=vehicle_id,
                    vin=vin,
                    plate=plate,
                    medallion_id=medallion_id,
                    lease_id=lease_id,
                    reference_id=reference_id,
                    reference_type=reference_type,
                    original_amount=amount,
                    prior_balance=Decimal("0.00"),
                    payment=Decimal("0.00"),
                    balance=amount,
                    status=BalanceStatus.OPEN.value,
                    obligation_date=transaction_date or date.today(),
                    updated_on=datetime.now(timezone.utc),
                    description=description,
                    created_by=created_by,
                    modified_by=created_by
            )

            balance = await self.repo.create_balance(balance)

            await self.repo.commit()

            logger.info(
                f"Created obligation posting and balance",
                posting_id=posting_id,
                balance_id=balance_id
            )

            return posting, balance
        except Exception as e:
            await self.repo.rollback()
            logger.error(f"Failed to create obligation posting: {str(e)}")
            raise

    async def apply_payment_to_balance(
        self, balance_id: str, payment_amount: Decimal, payment_source: str,
        payment_source_id: str, created_by: Optional[int] = None
    ) -> Tuple[LedgerPosting, LedgerBalance]:
        """
        Apply a payment (CREDIT) to an existing balance.
        
        This is called when:
        - Interim payment allocated
        - Weekly CURB earnings applied
        - Deposit applied
        
        Returns: (LedgerPosting, Updated LedgerBalance)
        """
        logger.info(
            f"Applying payment to balance",
            balance_id=balance_id,
            amount=str(payment_amount),
            source=payment_source
        )

        # === Validate inputs ===
        if payment_amount <= 0:
            raise InvalidLedgerEntryException("Payment amount must be positive")
        
        # === Get balance ===
        balance = await self.repo.get_balance_by_balance_id(balance_id)
        if not balance:
            raise LedgerNotFoundException(balance_id=balance_id)

        if balance.status == BalanceStatus.CLOSED.value:
            raise InvalidLedgerEntryException(f"Balance is already closed: {balance_id}")

        # === Check for over-payment ===
        if payment_amount > balance.balance:
            raise InvalidLedgerEntryException(
                f"Payment amount ({payment_amount}) exceeds outstanding balance ({balance.balance})"
            )
        
        try:
            # === Generate Posting ID ===
            posting_id = self._generate_posting_id()

            # Create CREDIT posting
            posting = LedgerPosting(
                posting_id=posting_id,
                category=balance.category,
                entry_type=LedgerEntryType.CREDIT.value,
                amount=payment_amount,
                driver_id=balance.driver_id,
                vehicle_id=balance.vehicle_id,
                vin=balance.vin,
                plate=balance.plate,
                medallion_id=balance.medallion_id,
                lease_id=balance.lease_id,
                reference_id=balance.reference_id,
                reference_type=f"{payment_source}-{payment_source_id}",
                status=LedgerStatus.POSTED.value,
                posted_on=datetime.utcnow(),
                transaction_date=date.today(),
                description=f"Payment from {payment_source}",
                created_by=created_by,
                modified_by=created_by
            )
            
            posting = await self.repo.create_posting(posting)
            
            # Update balance
            new_balance = balance.balance - payment_amount
            balance.payment += payment_amount
            balance.balance = new_balance
            
            # Update payment references
            payment_refs = []
            if balance.applied_payment_refs:
                try:
                    payment_refs = json.loads(balance.applied_payment_refs)
                except:
                    payment_refs = []
            
            payment_refs.append({
                "source": payment_source,
                "source_id": payment_source_id,
                "amount": str(payment_amount),
                "posted_at": datetime.utcnow().isoformat()
            })
            balance.applied_payment_refs = json.dumps(payment_refs)
            
            # Close balance if fully paid
            if new_balance <= Decimal("0.01"):  # Account for rounding
                balance = await self.repo.close_balance(balance)
            else:
                balance = await self.repo.update_balance(balance)
            
            await self.repo.commit()
            
            logger.info(
                f"Applied payment to balance",
                posting_id=posting_id,
                balance_id=balance_id,
                new_balance=str(new_balance)
            )
            
            return posting, balance
            
        except Exception as e:
            await self.repo.rollback()
            logger.error(f"Failed to apply payment: {str(e)}")
            raise
    
    async def apply_earnings_to_obligations(
        self,
        driver_id: int,
        earnings_amount: Decimal,
        earnings_batch_id: str,
        transaction_date: Optional[date] = None,
        created_by: Optional[int] = None
    ) -> Dict:
        """
        Apply CURB earnings to driver's obligations following payment hierarchy.
        
        Payment Hierarchy (strictest to most flexible):
        1. Taxes
        2. EZPass
        3. Lease
        4. PVB
        5. TLC
        6. Repairs
        7. Loans
        8. Miscellaneous
        
        Within each category: oldest obligations first (FIFO)
        
        Returns: Dict with allocation details and net earnings
        """
        logger.info(
            f"Applying earnings to obligations",
            driver_id=driver_id,
            earnings=str(earnings_amount),
            batch_id=earnings_batch_id
        )
        
        if earnings_amount <= 0:
            raise InvalidLedgerEntryException("Earnings amount must be positive")
        
        try:
            remaining_earnings = earnings_amount
            allocations = []
            
            # Apply earnings following hierarchy
            for category in PAYMENT_HIERARCHY:
                if remaining_earnings <= Decimal("0.01"):
                    break
                
                # Get open balances for this category (oldest first)
                balances = await self.repo.get_open_balances_by_driver(driver_id, category.value)
                
                for balance in balances:
                    if remaining_earnings <= Decimal("0.01"):
                        break
                    
                    # Determine payment amount
                    payment_amount = min(remaining_earnings, balance.balance)
                    
                    # Apply payment
                    posting, updated_balance = await self.apply_payment_to_balance(
                        balance_id=balance.balance_id,
                        payment_amount=payment_amount,
                        payment_source="CURB_EARNINGS",
                        payment_source_id=earnings_batch_id,
                        created_by=created_by
                    )
                    
                    allocations.append({
                        "category": category.value,
                        "reference_id": balance.reference_id,
                        "reference_type": balance.reference_type,
                        "amount_applied": str(payment_amount),
                        "balance_before": str(balance.balance + payment_amount),
                        "balance_after": str(updated_balance.balance),
                        "posting_id": posting.posting_id,
                        "balance_id": updated_balance.balance_id
                    })
                    
                    remaining_earnings -= payment_amount
                    
                    logger.debug(
                        f"Applied {payment_amount} to {category.value} {balance.reference_id}"
                    )
            
            await self.repo.commit()
            
            net_earnings = remaining_earnings
            total_allocated = earnings_amount - net_earnings
            
            logger.info(
                f"Earnings allocation complete",
                driver_id=driver_id,
                total_earnings=str(earnings_amount),
                total_allocated=str(total_allocated),
                net_earnings=str(net_earnings),
                allocations_count=len(allocations)
            )
            
            return {
                "success": True,
                "driver_id": driver_id,
                "earnings_batch_id": earnings_batch_id,
                "total_earnings": earnings_amount,
                "total_allocated": total_allocated,
                "net_earnings": net_earnings,
                "allocations": allocations
            }
            
        except Exception as e:
            await self.repo.rollback()
            logger.error(f"Failed to apply earnings: {str(e)}")
            raise
    
    # === Reversal Operations ===
    
    async def void_posting(
        self, request: ReversalRequest, created_by: Optional[int] = None
    ) -> ReversalResponse:
        """
        Void a posting by creating a reversal entry.
        
        Voids both the posting and its associated balance update.
        """
        logger.info(f"Voiding posting: {request.posting_id}")
        
        # Get original posting
        posting = await self.repo.get_posting_by_posting_id(request.posting_id)
        if not posting:
            raise LedgerNotFoundException(posting_id=request.posting_id)
        
        if posting.status == LedgerStatus.VOIDED.value:
            raise PostingVoidedException(request.posting_id)
        
        try:
            # Generate reversal posting ID
            reversal_id = self._generate_posting_id(prefix="REV")
            
            # Create reversal posting (opposite entry type, same amount)
            reversal_entry_type = (
                LedgerEntryType.CREDIT.value if posting.entry_type == LedgerEntryType.DEBIT.value
                else LedgerEntryType.DEBIT.value
            )
            
            reversal = LedgerPosting(
                posting_id=reversal_id,
                category=posting.category,
                entry_type=reversal_entry_type,
                amount=posting.amount,
                driver_id=posting.driver_id,
                vehicle_id=posting.vehicle_id,
                vin=posting.vin,
                plate=posting.plate,
                medallion_id=posting.medallion_id,
                lease_id=posting.lease_id,
                reference_id=posting.reference_id,
                reference_type=f"REVERSAL-{posting.reference_type}",
                status=LedgerStatus.POSTED.value,
                posted_on=datetime.utcnow(),
                transaction_date=date.today(),
                description=f"Reversal of {request.posting_id}: {request.reason}",
                created_by=created_by,
                modified_by=created_by
            )
            
            reversal = await self.repo.create_posting(reversal)
            
            # Mark original posting as voided
            posting = await self.repo.void_posting(posting, reversal_id)
            
            # Update associated balance (if exists)
            balance = await self.repo.get_balance_by_reference(
                posting.reference_id, posting.reference_type
            )
            
            if balance:
                if posting.entry_type == LedgerEntryType.DEBIT.value:
                    # Voiding a debit (obligation) - reduce balance
                    balance.balance -= posting.amount
                    if balance.balance <= Decimal("0.01"):
                        balance = await self.repo.close_balance(balance)
                    else:
                        balance = await self.repo.update_balance(balance)
                else:
                    # Voiding a credit (payment) - increase balance
                    balance.balance += posting.amount
                    balance.payment -= posting.amount
                    balance.status = BalanceStatus.OPEN.value
                    balance = await self.repo.update_balance(balance)
            
            await self.repo.commit()
            
            logger.info(f"Posting voided successfully: {request.posting_id}")
            
            return ReversalResponse(
                success=True,
                message=f"Posting {request.posting_id} voided successfully",
                original_posting_id=request.posting_id,
                reversal_posting_id=reversal_id,
                voided_at=datetime.utcnow()
            )
            
        except Exception as e:
            await self.repo.rollback()
            logger.error(f"Failed to void posting: {str(e)}")
            raise
    
    # === Query Operations ===
    
    async def get_driver_ledger_summary(
        self, driver_id: int, as_of_date: Optional[date] = None
    ) -> DriverLedgerSummary:
        """Get comprehensive summary of driver's ledger position"""
        logger.debug(f"Getting ledger summary for driver {driver_id}")
        
        # Get balance summary
        balance_summary = await self.repo.get_driver_balance_summary(driver_id, as_of_date)
        
        # Get total earnings (sum of CREDIT postings with category=Earnings)
        conditions_date = []
        if as_of_date:
            conditions_date.append(LedgerPosting.transaction_date <= as_of_date)
        
        from sqlalchemy import select, func, and_
        
        earnings_stmt = select(func.sum(LedgerPosting.amount)).where(
            and_(
                LedgerPosting.driver_id == driver_id,
                LedgerPosting.category == LedgerCategory.EARNINGS.value,
                LedgerPosting.entry_type == LedgerEntryType.CREDIT.value,
                LedgerPosting.status == LedgerStatus.POSTED.value,
                *conditions_date
            )
        )
        
        result = await self.db.execute(earnings_stmt)
        total_earnings = result.scalar() or Decimal("0.00")
        
        # Calculate totals
        total_obligations = sum([
            balance_summary.get("Lease", Decimal("0.00")),
            balance_summary.get("Repair", Decimal("0.00")),
            balance_summary.get("Loan", Decimal("0.00")),
            balance_summary.get("EZPass", Decimal("0.00")),
            balance_summary.get("PVB", Decimal("0.00")),
            balance_summary.get("TLC", Decimal("0.00")),
            balance_summary.get("Taxes", Decimal("0.00")),
            balance_summary.get("Misc", Decimal("0.00")),
        ])
        
        net_position = total_earnings - total_obligations
        
        # Get driver info (placeholder - you'll need to query Driver model)
        driver_name = f"Driver {driver_id}"  # TODO: Query from Driver model
        tlc_license = None  # TODO: Query from Driver model
        
        return DriverLedgerSummary(
            driver_id=driver_id,
            driver_name=driver_name,
            tlc_license=tlc_license,
            total_earnings=total_earnings,
            lease_due=balance_summary.get("Lease", Decimal("0.00")),
            repairs_due=balance_summary.get("Repair", Decimal("0.00")),
            loans_due=balance_summary.get("Loan", Decimal("0.00")),
            ezpass_due=balance_summary.get("EZPass", Decimal("0.00")),
            pvb_due=balance_summary.get("PVB", Decimal("0.00")),
            tlc_due=balance_summary.get("TLC", Decimal("0.00")),
            taxes_due=balance_summary.get("Taxes", Decimal("0.00")),
            misc_due=balance_summary.get("Misc", Decimal("0.00")),
            total_obligations=total_obligations,
            net_position=net_position,
            as_of_date=as_of_date or date.today(),
            open_balances_count=balance_summary.get("open_count", 0)
        )
    
    async def get_outstanding_balance(
        self, reference_id: str, reference_type: Optional[str] = None
    ) -> Optional[Decimal]:
        """Get outstanding balance for a specific obligation"""
        balance = await self.repo.get_balance_by_reference(reference_id, reference_type)
        
        if not balance:
            return None
        
        return balance.balance if balance.status == BalanceStatus.OPEN.value else Decimal("0.00")
    
    # === Helper Methods ===
    
    def _generate_posting_id(self, prefix: str = "POST") -> str:
        """Generate unique posting ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_suffix = str(uuid.uuid4().hex)[:6].upper()
        return f"{prefix}-{timestamp}-{unique_suffix}"
    
    def _generate_balance_id(self, category: str) -> str:
        """Generate unique balance ID"""
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        unique_suffix = str(uuid.uuid4().hex)[:6].upper()
        category_prefix = category[:3].upper()
        return f"BAL-{category_prefix}-{timestamp}-{unique_suffix}"



    
