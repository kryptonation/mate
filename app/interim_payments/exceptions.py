# app/interim_payments/exceptions.py

"""
Custom exceptions for Interim Payments module.
"""


class InterimPaymentBaseException(Exception):
    """Base exception for all interim payment errors"""
    pass


class InterimPaymentNotFoundException(InterimPaymentBaseException):
    """Raised when a payment record is not found"""
    def __init__(self, payment_id: int):
        self.payment_id = payment_id
        super().__init__(f"Interim payment with ID {payment_id} not found")


class AllocationNotFoundException(InterimPaymentBaseException):
    """Raised when an allocation record is not found"""
    def __init__(self, allocation_id: int):
        self.allocation_id = allocation_id
        super().__init__(f"Payment allocation with ID {allocation_id} not found")


class InvalidPaymentAmountException(InterimPaymentBaseException):
    """Raised when payment amount is invalid"""
    def __init__(self, amount: float, reason: str = ""):
        self.amount = amount
        super().__init__(f"Invalid payment amount: {amount}. {reason}")


class AllocationExceedsPaymentException(InterimPaymentBaseException):
    """Raised when total allocations exceed payment amount"""
    def __init__(self, payment_amount: float, allocated_amount: float):
        self.payment_amount = payment_amount
        self.allocated_amount = allocated_amount
        super().__init__(
            f"Total allocation ({allocated_amount}) exceeds payment amount ({payment_amount})"
        )


class InsufficientOutstandingBalanceException(InterimPaymentBaseException):
    """Raised when allocated amount exceeds outstanding balance"""
    def __init__(self, category: str, reference_id: str, outstanding: float, allocated: float):
        self.category = category
        self.reference_id = reference_id
        self.outstanding = outstanding
        self.allocated = allocated
        super().__init__(
            f"Allocation ({allocated}) exceeds outstanding balance ({outstanding}) "
            f"for {category} {reference_id}"
        )


class ObligationNotFoundException(InterimPaymentBaseException):
    """Raised when referenced obligation is not found"""
    def __init__(self, category: str, reference_id: str):
        self.category = category
        self.reference_id = reference_id
        super().__init__(f"Obligation not found: {category} - {reference_id}")


class ClosedObligationException(InterimPaymentBaseException):
    """Raised when trying to allocate to a closed obligation"""
    def __init__(self, category: str, reference_id: str):
        self.category = category
        self.reference_id = reference_id
        super().__init__(f"Cannot allocate to closed obligation: {category} - {reference_id}")


class PaymentCreationException(InterimPaymentBaseException):
    """Raised when payment creation fails"""
    def __init__(self, reason: str):
        super().__init__(f"Failed to create interim payment: {reason}")


class PaymentAllocationException(InterimPaymentBaseException):
    """Raised when allocation processing fails"""
    def __init__(self, reason: str):
        super().__init__(f"Failed to allocate payment: {reason}")


class LedgerPostingException(InterimPaymentBaseException):
    """Raised when ledger posting fails"""
    def __init__(self, reason: str):
        super().__init__(f"Failed to post to ledger: {reason}")


class PaymentVoidException(InterimPaymentBaseException):
    """Raised when payment void operation fails"""
    def __init__(self, payment_id: str, reason: str):
        self.payment_id = payment_id
        super().__init__(f"Cannot void payment {payment_id}: {reason}")


class PaymentReversalException(InterimPaymentBaseException):
    """Raised when payment reversal fails"""
    def __init__(self, payment_id: str, reason: str):
        self.payment_id = payment_id
        super().__init__(f"Cannot reverse payment {payment_id}: {reason}")


class InvalidPaymentStatusException(InterimPaymentBaseException):
    """Raised when payment status is invalid for operation"""
    def __init__(self, payment_id: str, current_status: str, required_status: str):
        self.payment_id = payment_id
        self.current_status = current_status
        self.required_status = required_status
        super().__init__(
            f"Payment {payment_id} has status '{current_status}', "
            f"but '{required_status}' is required"
        )


class TaxAllocationException(InterimPaymentBaseException):
    """Raised when attempting to allocate to statutory taxes"""
    def __init__(self):
        super().__init__(
            "Interim payments cannot be applied to statutory taxes "
            "(MTA, TIF, Congestion, CBDT, Airport)"
        )


class DuplicatePaymentException(InterimPaymentBaseException):
    """Raised when a duplicate payment is detected"""
    def __init__(self, driver_id: int, payment_date: str, amount: float):
        self.driver_id = driver_id
        self.payment_date = payment_date
        self.amount = amount
        super().__init__(
            f"Potential duplicate payment detected: "
            f"Driver {driver_id}, Date {payment_date}, Amount {amount}"
        )


class DriverNotFoundException(InterimPaymentBaseException):
    """Raised when driver is not found"""
    def __init__(self, driver_id: int):
        self.driver_id = driver_id
        super().__init__(f"Driver with ID {driver_id} not found")


class MedallionNotFoundException(InterimPaymentBaseException):
    """Raised when medallion is not found"""
    def __init__(self, medallion_id: int):
        self.medallion_id = medallion_id
        super().__init__(f"Medallion with ID {medallion_id} not found")


class LeaseNotFoundException(InterimPaymentBaseException):
    """Raised when lease is not found"""
    def __init__(self, lease_id: int):
        self.lease_id = lease_id
        super().__init__(f"Lease with ID {lease_id} not found")


class InvalidLeaseStateException(InterimPaymentBaseException):
    """Raised when lease is not in valid state for payment"""
    def __init__(self, lease_id: int, state: str):
        self.lease_id = lease_id
        self.state = state
        super().__init__(f"Lease {lease_id} is in invalid state: {state}")