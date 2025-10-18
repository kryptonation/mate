# app/driver_loans/services.py

"""
Business logic layer for Driver Loans operations.
Implements loan creation, payment schedule generation, interest calculation,
and posting logic according to the Loan Repayment Matrix.
"""

from datetime import datetime, timezone, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple, Optional, Dict, Any

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_async_db
from app.driver_loans.repository import DriverLoanRepository
from app.driver_loans.schemas import (
    DriverLoanCreate, DriverLoanUpdate, DriverLoanFilters,
    DriverLoanInstallmentCreate, DriverLoanInstallmentUpdate, DriverLoanInstallmentFilters,
    DriverLoanLogCreate, PaymentScheduleRequest, PaymentScheduleResponse,
    LoanCreationResult, LoanPostingResult, StartWeekOption, LoanStatus,
    InstallmentStatus,
)
from app.driver_loans.models import DriverLoan, DriverLoanInstallment
from app.driver_loans.exceptions import (
    DriverLoanNotFoundException, DriverLoanCreationException,
    DriverLoanPostingException, DriverLoanStatusException,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

def get_loan_repository(db: AsyncSession = Depends(get_async_db)) -> DriverLoanRepository:
    """Dependency to get DriverLoanRepository instance."""
    return DriverLoanRepository(db)


class LoanRepaymentMatrix:
    """
    Implements the loan repayment matrix rules for determining
    weekly principal installments based on loan amount.
    """

    @staticmethod
    def get_weekly_principal(loan_amount: Decimal) -> Decimal:
        """
        Get weekly principal installment based on loan amount.

        Matrix Rules:
        - $0 – $200: Paid in full (single installment)
        - $201 – $500: $100 per week
        - $501 – $1,000: $200 per week
        - $1,001 – $3,000: $250 per week
        - > $3,000: $300 per week
        """
        if loan_amount <= 200:
            return loan_amount
        elif loan_amount <= 500:
            return Decimal("100.00")
        elif loan_amount <= 1000:
            return Decimal("200.00")
        elif loan_amount <= 3000:
            return Decimal("250.00")
        else:
            return Decimal("300.00")
        
    @staticmethod
    def calculate_number_of_installments(loan_amount: Decimal) -> int:
        """
        Calculate the number of installments needed.
        """
        weekly_principal = LoanRepaymentMatrix.get_weekly_principal(loan_amount)

        if loan_amount <= 200:
            return 1
        
        # === Calculate full installments ===
        full_installments = int(loan_amount / weekly_principal)

        # === Check if there's a remainder requiring an additional installment ===
        remainder = loan_amount % weekly_principal
        if remainder > 0:
            full_installments += 1
        
        return full_installments
    

class InterestCalculator:
    """
    Handles interest calculation for driver loans using simple daily interest.
    """

    @staticmethod
    def calculate_interest(
        outstanding_principal: Decimal,
        annual_rate: Decimal,
        accrual_days: int,
    ) -> Decimal:
        """
        Calculate interest using simple daily interest formula.

        Formula:
        Interest = Outstanding Principal * (Annual Rate / 100) * (Accrual Days / 365)

        Args:
            outstanding_principal: Loan balance before the installment
            annual_rate: Annual interest rate as percentage (e.g., 10 = 10%)
            accrual_days: Number of days to accrue interest
        
        Returns:
            Calculated interest amount rounded to 2 decimal places
        """
        if annual_rate == 0 or accrual_days == 0:
            return Decimal("0.00")
        
        # === Convert percentage to Decimal ===
        rate_decimal = annual_rate / Decimal("100.00")

        # === Calculate interest ===
        interest = outstanding_principal * rate_decimal * (Decimal(accrual_days) / Decimal("365"))

        # === Round to 2 decimal places ===
        return interest.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    
    @staticmethod
    def calculate_accrual_days(start_date: date, end_date: date) -> int:
        """Calculate the number of days between two dates (inclusive)."""
        return (end_date - start_date).days + 1
    

class DriverLoanService:
    """
    Business logic layer for Driver Loans operations.
    Implements loan lifecycle management, payment scheduling, and posting.
    """

    def __init__(self, repo: DriverLoanRepository = Depends(get_loan_repository)):
        self.repo = repo
        logger.debug("DriverLoanService initialized.")

    # === Loan Creation and Management ===

    async def create_loan_with_schedule(
        self,
        loan_data: DriverLoanCreate,
    ) -> LoanCreationResult:
        """
        Create a new driver loan with automatic payment schedule generation.
        """
        try:
            logger.info(
                "Creating loan with schedule",
                driver_id=loan_data.driver_id,
                amount=str(loan_data.loan_amount),
            )

            # === Generate unique loan ID ===
            year = loan_data.loan_date.year
            next_number = await self.repo.get_next_loan_number(year)
            loan_id = f"DLN{year}-{next_number:03d}"

            # === Calculate start week based on option ===
            start_week = self._calculate_start_week(
                loan_data.loan_date,
                loan_data.start_week_option,
            )

            # === Create loan record ===
            loan = await self.repo.create_loan(loan_data, loan_id, start_week)

            # === Generate payment schedule ===
            installments = await self._generate_payment_schedule(loan)

            # === Create installment records ===
            await self.repo.create_installments(installments)

            # === Update loan status to Open ===
            await self.repo.update_loan(
                loan, DriverLoanUpdate(status=LoanStatus.OPEN)
            )

            # === Create log entry ===
            await self.repo.create_log(
                DriverLoanLogCreate(
                    log_date=datetime.now(timezone.utc),
                    log_type="Create",
                    loan_id=loan.id,
                    records_impacted=len(installments),
                    status="Success",
                    details=f"Loan created with {len(installments)} installments"
                )
            )

            # === Commit transaction ===
            await self.repo.commit()

            # === Refresh loan to get updated relationships ===
            loan = await self.repo.get_loan_by_id(loan.id)

            logger.info(
                "Loan created successfully",
                loan_id=loan_id,
                installments=len(installments)
            )

            return LoanCreationResult(
                success=True,
                loan_id=loan_id,
                message=f"Loan created successfully with {len(installments)} installments.",
                loan=loan,
                schedule=loan.installments,
            )
        
        except Exception as e:
            await self.repo.rollback()
            logger.error("Failed to create loan", error=str(e))
            raise DriverLoanCreationException(f"Failed to create loan: {str(e)}") from e
        
    async def get_loan_by_id(self, loan_id: int) -> DriverLoan:
        """Get a loan by ID."""
        logger.info("Getting loan by ID", loan_id=loan_id)

        loan = await self.repo.get_loan_by_id(loan_id)
        if not loan:
            logger.error("Loan not found", loan_id=loan_id)
            raise DriverLoanNotFoundException(loan_id)
        
        return loan
    
    async def get_loans(
        self, filters: DriverLoanFilters,
    ) -> Tuple[List[DriverLoan], int]:
        """Get loans with filters and pagination."""
        logger.debug("Getting loans with filters")
        return await self.repo.get_loans(filters)
    
    async def update_loan_status(
        self, loan_id: int, new_status: LoanStatus, reason: Optional[str] = None,
    ) -> DriverLoan:
        """Update loan status with validation."""
        logger.info("Updating loan status", loan_id=loan_id, new_status=new_status)

        loan = await self.repo.get_loan_by_id(loan_id)
        if not loan:
            raise DriverLoanNotFoundException(loan_id)
        
        # === Validate status transition ===
        if not self._validate_status_transition(loan.status, new_status):
            raise DriverLoanStatusException(
                f"Invalid status transition from {loan.status} to {new_status}"
            )
        
        # === Update status ===
        loan = await self.repo.update_loan(
            loan, DriverLoanUpdate(status=new_status),
        )

        # === Create log entry ===
        await self.repo.create_log(
            DriverLoanLogCreate(
                log_date=datetime.now(timezone.utc),
                log_type="Status Change",
                loan_id=loan.id,
                status="Success",
                details=f"Status changed from {loan.status} to {new_status}. {reason or ''}",
            )
        )

        await self.repo.commit()
        return loan
    
    # === Payment schedule generation ===

    async def generate_payment_schedule_preview(
        self, request: PaymentScheduleRequest,
    ) -> PaymentScheduleResponse:
        """
        Generate a payment schedule preview without creating records.
        Used for showing the schedule to users before confirmation.
        """
        logger.debug("Generating payment schedule preview")

        # === Calculate start week ===
        start_week = self._calculate_start_week(
            request.loan_date,
            request.start_week_option,
        )

        # === Generate schedule ===
        schedule = self._calculate_payment_schedule(
            request.loan_amount,
            request.interest_rate,
            request.loan_date,
            start_week,
        )

        # === Calculate totals ===
        total_interest = sum(inst["interest_amount"] for inst in schedule)
        total_amount = request.loan_amount + total_interest
        weekly_payment = LoanRepaymentMatrix.get_weekly_principal(request.loan_amount)

        return PaymentScheduleResponse(
            loan_amount=request.loan_amount,
            interest_rate=request.interest_rate,
            total_amount=total_amount,
            number_of_installments=len(schedule),
            weekly_payment=weekly_payment,
            installments=schedule,
        )
    
    async def _generate_payment_schedule(
        self, loan: DriverLoan,
    ) -> List[DriverLoanInstallmentCreate]:
        """Gernerate payment schedule for a loan."""
        logger.debug("Generating payment schedule for loan", loan_id=loan.loan_id)

        schedule_data = self._calculate_payment_schedule(
            loan.loan_amount,
            loan.interest_rate,
            loan.loan_date,
            loan.start_week,
        )

        installments = []
        for idx, data in enumerate(schedule_data, start=1):
            installment = DriverLoanInstallmentCreate(
                loan_id=loan.id,
                installment_id=f"{loan.loan_id}-{idx:02d}",
                installment_number=idx,
                week_start_date=data["week_start_date"],
                week_end_date=data["week_end_date"],
                principal_amount=data["principal_amount"],
                interest_amount=data["interest_amount"],
                total_due=data["total_due"],
                outstanding_principal=data["outstanding_principal"],
                remaining_balance=data["remaining_balance"],
                prior_balance=Decimal("0.00")
            )
            installments.append(installment)

        return installments
    
    def _calculate_payment_schedule(
        self, loan_amount: Decimal, interest_rate: Decimal, loan_date: date,
        start_week: date,
    ) -> List[Dict[str, Any]]:
        """
        Calculate the complete payment schedule with interest.

        Returns list of dictionaires with installment details.
        """
        schedule = []
        outstanding_principal = loan_amount
        weekly_principal = LoanRepaymentMatrix.get_weekly_principal(loan_amount)

        # === Calculate first Sunday (week start) ===
        current_week_start = start_week
        last_calculation_date = loan_date

        while outstanding_principal > 0:
            # === Calculate week end (Saturday) ===
            current_week_end = current_week_start + timedelta(days=6)

            # === Determine principal amount for this installment ===
            if outstanding_principal <= weekly_principal:
                # === Final installment ===
                principal_amount = outstanding_principal
            else:
                principal_amount = weekly_principal

            # === Calculate accrual days ===
            # === For first intallment: from loan date to week end ===
            # === For subsequent: full week (7 days) ===
            if len(schedule) == 0:
                # === First installment: from loan date to first Sunday ===
                accrual_days = (current_week_end - loan_date).days + 1
            else:
                # === Subsequent installments: full week ===
                accrual_days = 7

            # === Calculate interest ===
            interest_amount = InterestCalculator.calculate_interest(
                outstanding_principal,
                interest_rate,
                accrual_days,
            )

            # === Calculate total due ===
            total_due = principal_amount + interest_amount

            # === Calculate remaining balance after this installment ===
            remaining_balance = outstanding_principal - principal_amount

            # === Add to schedule ===
            schedule.append({
                "week_start_date": current_week_start,
                "week_end_date": current_week_end,
                "principal_amount": principal_amount,
                "interest_amount": interest_amount,
                "total_due": total_due,
                "outstanding_principal": outstanding_principal,
                "remaining_balance": remaining_balance,
                "accrual_days": accrual_days,
            })

            # === Update for next iteration ===
            outstanding_principal = remaining_balance
            current_week_start = current_week_start + timedelta(days=7)
            last_calculation_date = current_week_end

        return schedule
    
    def _calculate_start_week(
        self, loan_date: date, start_week_option: StartWeekOption
    ) -> date:
        """
        Calculate the Sunday when repayment starts based on the option.
        """
        # === Find the next Sunday from loan date ===
        days_until_sunday = (6 - loan_date.weekday()) % 7
        if days_until_sunday == 0 and loan_date.weekday() == 6:
            # === If loan date is Sunday, next Sunday is in 7 days ===
            days_until_sunday = 7

        next_sunday = loan_date + timedelta(days=days_until_sunday)

        if start_week_option == StartWeekOption.CURRENT:
            return next_sunday
        else: # Next
            return next_sunday + timedelta(days=7)
        
    def _validate_status_transition(
        self, current_status: str, new_status: LoanStatus
    ) -> bool:
        """Validate if status transition is allowed."""
        allowed_transitions = {
            "Draft": ["Open", "Cancelled"],
            "Open": ["Hold", "Closed"],
            "Hold": ["Open", "Closed"],
            "Closed": [],
            "Cancelled": [],
        }

        return new_status in allowed_transitions.get(current_status, [])
    
    # === Installment Operations ===

    async def get_installments(
        self, filters: DriverLoanInstallmentFilters,
    ) -> Tuple[List[DriverLoanInstallment], int]:
        """Get installments with filters and pagination."""
        logger.debug("Getting installments with filters")
        return await self.repo.get_installments(filters)
    
    async def process_due_installments(
        self, as_of_date: Optional[date] = None,
    ) -> LoanPostingResult:
        """
        Process all due installments for posting to ledger.
        This would typically be called by a scheduled task every Sunday at 5:00 AM.
        """
        if not as_of_date:
            as_of_date = date.today()

        logger.info("Processing due installments", as_of_date=str(as_of_date))

        try:
            # === Mark scheduled installments as due ===
            marked_count = await self.repo.mark_installments_due(as_of_date)

            # === Get all due installments ===
            due_installments = await self.repo.get_due_installments(as_of_date)

            posted_count = 0
            failed_count = 0
            details = []

            for installment in due_installments:
                try:
                    # === Post to ledger (Simplified) ===
                    # TODO: Implement integration with ledger service
                    await self._post_installment_to_ledger(installment)

                    # === Update installment status ===
                    await self.repo.update_installment(
                        installment,
                        DriverLoanInstallmentUpdate(
                            status=InstallmentStatus.POSTED,
                            posting_date=datetime.now(timezone.utc),
                            ledger_posting_ref=f"LED-{installment.installment_id}"
                        )
                    )

                    # === Update loan balances ===
                    await self.repo.update_loan_balances(
                        installment.loan_id,
                        installment.principal_amount,
                        installment.interest_amount,
                    )

                    posted_count += 1
                    details.append({
                        "installment_id": installment.installment_id,
                        "status": "Posted",
                        "amount": str(installment.total_due),
                    })

                except Exception as e:
                    failed_count += 1
                    details.append({
                        "installment_id": installment.installment_id,
                        "status": "Failed",
                        "error": str(e),
                    })
                    logger.error(
                        "Failed to post installment", installment_id=installment.installment_id, error=str(e)
                    )

            # === Check for loans that should be closed ===
            await self._check_and_close_completed_loans()

            # === Create log entry ===
            await self.repo.create_log(
                DriverLoanLogCreate(
                    log_date=datetime.now(timezone.utc),
                    log_type="Post",
                    records_impacted=posted_count + failed_count,
                    status="Success" if failed_count == 0 else "Partial",
                    details=f"Posted {posted_count}, Failed {failed_count}"
                )
            )

            await self.repo.commit()

            return LoanPostingResult(
                success=True,
                total_processed=len(due_installments),
                posted_count=posted_count,
                failed_count=failed_count,
                message=f"Successfully posted {posted_count} installments",
                details=details,
            )
        
        except Exception as e:
            await self.repo.rollback()
            logger.error("Failed to process due installments", error=str(e))
            raise DriverLoanPostingException(f"Failed to process installments: {str(e)}") from e
        
    async def _post_installment_to_ledger(
        self, installment: DriverLoanInstallment
    ) -> None:
        """
        Post an installment to the ledger system.
        This is a simplified version - actual implementation would integrate with ledger service.
        """
        logger.debug(
            "Posting installment to ledger",
            installment_id=installment.installment_id,
        )
        # TODO: Implement actual ledger posting logic
        # In actual implementation, this would:
        # 1. Create ledger entry for principal
        # 2. Create ledger entry for interest (if applicable)
        # 3. Link to driver's DTR
        # 4. Update ledger balances
        
        # Placeholder for ledger integration
        pass

    async def _check_and_close_completed_loans(self) -> None:
        """Check for loans with all installments paid and close them."""
        # TODO: Implement logic to check and close loans
        # This would check for loans where:
        # 1. All installments are in "Posted" or "Paid" status
        # 2. Outstanding balance is 0
        # Then update loan status to "Closed"
        pass

    
    


