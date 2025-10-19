# app/repairs/exceptions.py

"""
Custom exceptions for the Repairs module.
Follows the exception hierarchy pattern from PVB/EZPass modules.
"""

from typing import Optional
from fastapi import HTTPException, status


class RepairBaseException(Exception):
    """Base exception for all Repair-related errors."""
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class RepairNotFoundException(RepairBaseException):
    """Raised when a repair invoice or installment is not found."""
    def __init__(self, repair_id: Optional[int] = None, installment_id: Optional[int] = None):
        msg = f"Repair with ID {repair_id} not found" if repair_id else \
              f"Installment with ID {installment_id} not found"
        super().__init__(msg, {"repair_id": repair_id, "installment_id": installment_id})


class DuplicateInvoiceException(RepairBaseException):
    """Raised when attempting to create a duplicate invoice."""
    def __init__(self, invoice_number: str, vehicle_id: int, invoice_date: str):
        msg = f"Invoice {invoice_number} already exists for vehicle {vehicle_id} on {invoice_date}"
        super().__init__(
            msg, 
            {"invoice_number": invoice_number, "vehicle_id": vehicle_id, "invoice_date": invoice_date}
        )


class RepairFileValidationException(RepairBaseException):
    """Raised when uploaded repair invoice file fails validation."""
    def __init__(self, message: str, validation_errors: Optional[list] = None):
        super().__init__(message, {"validation_errors": validation_errors or []})


class InvalidRepairAmountException(RepairBaseException):
    """Raised when repair amount is invalid."""
    def __init__(self, amount: float):
        msg = f"Invalid repair amount: {amount}. Amount must be >= $1"
        super().__init__(msg, {"amount": amount})


class InvalidPaymentScheduleException(RepairBaseException):
    """Raised when payment schedule generation fails."""
    def __init__(self, message: str, repair_amount: Optional[float] = None):
        super().__init__(
            message, 
            {"repair_amount": repair_amount}
        )


class RepairImportException(RepairBaseException):
    """Raised when repair invoice import fails."""
    def __init__(self, message: str, failed_rows: Optional[dict] = None):
        super().__init__(message, {"failed_rows": failed_rows or {}})


class RepairPostingException(RepairBaseException):
    """Raised when installment posting to ledger fails."""
    def __init__(self, message: str, installment_id: Optional[int] = None):
        super().__init__(
            message, 
            {"installment_id": installment_id}
        )


class RepairStateException(RepairBaseException):
    """Raised when repair state transition is invalid."""
    def __init__(self, current_state: str, attempted_state: str, reason: str):
        msg = f"Cannot transition from {current_state} to {attempted_state}: {reason}"
        super().__init__(
            msg, 
            {"current_state": current_state, "attempted_state": attempted_state, "reason": reason}
        )


class RepairCancellationException(RepairBaseException):
    """Raised when repair cancellation is not allowed."""
    def __init__(self, repair_id: int, reason: str):
        msg = f"Cannot cancel repair {repair_id}: {reason}"
        super().__init__(msg, {"repair_id": repair_id, "reason": reason})


def convert_to_http_exception(exc: RepairBaseException) -> HTTPException:
    """
    Convert a RepairBaseException to an HTTPException with appropriate status code.
    
    Args:
        exc: The repair exception to convert
        
    Returns:
        HTTPException with appropriate status code and detail
    """
    if isinstance(exc, RepairNotFoundException):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": exc.message, "details": exc.details}
        )
    elif isinstance(exc, DuplicateInvoiceException):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"message": exc.message, "details": exc.details}
        )
    elif isinstance(exc, (RepairFileValidationException, InvalidRepairAmountException, 
                          InvalidPaymentScheduleException)):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": exc.message, "details": exc.details}
        )
    elif isinstance(exc, (RepairImportException, RepairPostingException, 
                          RepairStateException, RepairCancellationException)):
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": exc.message, "details": exc.details}
        )
    else:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"message": str(exc), "details": {}}
        )
    
