# app/repairs/utils.py

"""
Utility functions for Vehicle Repairs module.
Includes payment matrix calculations, schedule generation, and validation.
"""

from datetime import date, timedelta
from typing import List, Dict, Tuple, Optional
import re

from app.utils.logger import get_logger

logger = get_logger(__name__)


def calculate_weekly_installment(repair_amount: float) -> float:
    """
    Calculate weekly installment amount based on the Repair Payment Matrix.

    Payment Matrix Rules:
    - $0 – $200: Paid in full (single installment)
    - $201 – $500: $100 per week
    - $501 – $1,000: $200 per week
    - $1,001 – $3,000: $250 per week
    - > $3,000: $300 per week
    
    Args:
        repair_amount: Total repair cost
        
    Returns:
        Weekly installment amount
        
    Raises:
        ValueError: If repair amount is invalid
    """
    if repair_amount < 0:
        raise ValueError(f"Repair amount cannot be negative: {repair_amount}")
    
    if repair_amount <= 200:
        return repair_amount
    elif repair_amount <= 500:
        return 100.0
    elif repair_amount <= 1000:
        return 200.0
    elif repair_amount <= 3000:
        return 250.0
    else:
        return 300.0
    

def get_payment_period_dates(
    reference_date: date, start_week: str = "Current Payment Period"
) -> Tuple[date, date]:
    """
    Get the start and end dates for a payment period.
    Payment periods run Sunday 00:00 -> Saturday 23:59.

    Args:
        reference_date: The reference date to calculate from
        start_week: "Current Payment Period" or "Next Payment Period"
        
    Returns:
        Tuple of (week_start_date, week_end_date)
    """
    # === Find the Sunday of the current week ===
    days_since_sunday = reference_date.weekday() + 1
    if reference_date.weekday() == 6:
        days_since_sunday = 6

    current_sunday = reference_date - timedelta(days=days_since_sunday)

    if start_week == "Next Payment Period":
        # === Move to next week's Sunday ===
        current_sunday = current_sunday + timedelta(days=7)

    week_start = current_sunday
    week_end = current_sunday + timedelta(days=6)

    return week_start, week_end


def generate_payment_schedule(
    repair_amount: float, start_date: date, start_week: str = "Current Payment Period"
) -> List[Dict]:
    """
    Generate complete payment schedule for a repair invoice.
    
    Args:
        repair_amount: Total repair cost
        start_date: Date when repair was invoiced
        start_week: "Current Payment Period" or "Next Payment Period"
        
    Returns:
        List of installment dictionaries with week dates and amounts
    """
    weekly_installment = calculate_weekly_installment(repair_amount)
    schedule = []

    remaining_balance = repair_amount
    week_start, week_end = get_payment_period_dates(start_date, start_week)
    sequence = 1

    while remaining_balance > 0.01:
        # === Determine payment amount for this installment ===
        if remaining_balance <= weekly_installment:
            # === Final installment - pay remaining balance ===
            payment_amount = round(remaining_balance, 2)
        else:
            payment_amount = weekly_installment

        # === Calculate balances ===
        prior_balance = repair_amount - sum(inst["payment_amount"] for inst in schedule)
        new_balance = prior_balance - payment_amount

        schedule.append({
            "sequence": sequence,
            "week_start_date": week_start,
            "week_end_date": week_end,
            "payment_amount": round(payment_amount, 2),
            "prior_balance": round(prior_balance, 2),
            "balance": round(new_balance, 2)
        })

        remaining_balance = new_balance
        week_start = week_start + timedelta(days=7)
        week_end = week_end + timedelta(days=7)
        sequence += 1

    return schedule


def generate_repair_id(year: int, sequence: int) -> str:
    """
    Generate a unique repair ID.
    Format: VRPR-YYYY-XXX (e.g., VRPR-2025-001)

    Args:
        year: Year of the repair
        sequence: Sequence number for the year
        
    Returns:
        Formatted repair ID
    """
    return f"VRPR-{year}-{sequence:03d}"


def generate_installment_id(repair_id: str, sequence: int) -> str:
    """
    Generate a unique installment ID.
    Format: [RepairID]-[Seq] (e.g., VRPR-2025-012-03)

    Args:
        repair_id: Parent repair ID
        sequence: Installment sequence number
        
    Returns:
        Formatted installment ID
    """
    return f"{repair_id}-{sequence:02d}"


def validate_invoice_date(invoice_date: date) -> bool:
    """
    Validate that invoice date is not in the future.
    
    Args:
        invoice_date: Date to validate
        
    Returns:
        True if valid, False otherwise
    """
    return invoice_date <= date.today()


def validate_repair_amount(amount: float) -> bool:
    """
    Validate that repair amount meets minimum requirements.
    
    Args:
        amount: Amount to validate
        
    Returns:
        True if valid, False otherwise
    """
    return amount >= 1.0


def validate_vin(vin: str) -> bool:
    """
    Basic VIN validation (17 characters, alphanumeric, no I, O, Q).
    
    Args:
        vin: VIN to validate
        
    Returns:
        True if valid format, False otherwise
    """
    if not vin or len(vin) != 17:
        return False
    
    # VINs use all letters except I, O, Q and all digits
    pattern = r'^[A-HJ-NPR-Z0-9]{17}$'
    return bool(re.match(pattern, vin.upper()))


def calculate_balance_after_installments(
    total_amount: float,
    installments_paid: List[float]
) -> float:
    """
    Calculate remaining balance after a series of installment payments.
    
    Args:
        total_amount: Original repair amount
        installments_paid: List of installment amounts already paid
        
    Returns:
        Remaining balance
    """
    total_paid = sum(installments_paid)
    return round(max(0, total_amount - total_paid), 2)


def get_next_payment_date(current_date: date) -> date:
    """
    Get the next Sunday (payment posting date) from a given date.
    
    Args:
        current_date: Reference date
        
    Returns:
        Next Sunday date
    """
    days_until_sunday = (6 - current_date.weekday()) % 7
    if days_until_sunday == 0:
        days_until_sunday = 7
    return current_date + timedelta(days=days_until_sunday)


def is_payment_period_active(week_start: date, week_end: date, check_date: date) -> bool:
    """
    Check if a date falls within a payment period.
    
    Args:
        week_start: Payment period start date
        week_end: Payment period end date
        check_date: Date to check
        
    Returns:
        True if date is within period, False otherwise
    """
    return week_start <= check_date <= week_end


def format_installment_summary(
    installment: Dict,
    invoice_number: str,
    repair_description: Optional[str] = None
) -> str:
    """
    Format an installment for display in DTR or statements.
    
    Args:
        installment: Installment dictionary with payment details
        invoice_number: Invoice number
        repair_description: Optional repair description
        
    Returns:
        Formatted description string
    """
    desc = f"Repair - Invoice {invoice_number}"
    if repair_description:
        # Truncate long descriptions
        short_desc = repair_description[:50] + "..." if len(repair_description) > 50 else repair_description
        desc += f" - {short_desc}"
    return desc


def validate_repair_invoice_file(file_content: bytes, filename: str) -> Tuple[bool, Optional[str]]:
    """
    Validate uploaded repair invoice file.
    
    Args:
        file_content: File content in bytes
        filename: Original filename
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check file size (max 10MB)
    max_size = 10 * 1024 * 1024  # 10MB
    if len(file_content) > max_size:
        return False, "File size exceeds 10MB limit"
    
    # Check file extension
    allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff']
    file_ext = filename.lower()[filename.rfind('.'):] if '.' in filename else ''
    
    if file_ext not in allowed_extensions:
        return False, f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
    
    # Check if file is empty
    if len(file_content) == 0:
        return False, "File is empty"
    
    return True, None


def calculate_payment_matrix_tiers() -> List[Dict]:
    """
    Get the payment matrix tiers for reference/display.
    
    Returns:
        List of tier dictionaries
    """
    return [
        {"min_amount": 0, "max_amount": 200, "installment": "Full Amount", "description": "Paid in full"},
        {"min_amount": 201, "max_amount": 500, "installment": 100, "description": "$100 per week"},
        {"min_amount": 501, "max_amount": 1000, "installment": 200, "description": "$200 per week"},
        {"min_amount": 1001, "max_amount": 3000, "installment": 250, "description": "$250 per week"},
        {"min_amount": 3001, "max_amount": float('inf'), "installment": 300, "description": "$300 per week"},
    ]


def validate_state_transition(current_status: str, new_status: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if a state transition is allowed for repair invoices.
    
    Valid transitions:
    - Draft → Open, Cancelled
    - Open → Closed, Hold
    - Hold → Open, Cancelled (if no postings)
    - Closed → (no transitions)
    - Cancelled → (no transitions)
    
    Args:
        current_status: Current invoice status
        new_status: Desired new status
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_transitions = {
        "Draft": ["Open", "Cancelled"],
        "Open": ["Closed", "Hold"],
        "Hold": ["Open", "Cancelled"],
        "Closed": [],
        "Cancelled": []
    }
    
    if current_status not in valid_transitions:
        return False, f"Invalid current status: {current_status}"
    
    if new_status not in valid_transitions[current_status]:
        return False, f"Cannot transition from {current_status} to {new_status}"
    
    return True, None

