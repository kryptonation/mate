# app/driver_loans/exceptions.py

"""
Custom exceptions for Driver Loans module.
"""


class DriverLoanBaseException(Exception):
    """Base exception for Driver Loans module."""
    pass


class DriverLoanNotFoundException(DriverLoanBaseException):
    """Exception raised when a loan is not found."""
    
    def __init__(self, loan_id: int):
        self.loan_id = loan_id
        super().__init__(f"Driver loan with ID {loan_id} not found")


class DriverLoanInstallmentNotFoundException(DriverLoanBaseException):
    """Exception raised when a loan installment is not found."""
    
    def __init__(self, installment_id: int):
        self.installment_id = installment_id
        super().__init__(f"Driver loan installment with ID {installment_id} not found")


class DriverLoanCreationException(DriverLoanBaseException):
    """Exception raised when loan creation fails."""
    pass


class DriverLoanScheduleException(DriverLoanBaseException):
    """Exception raised when payment schedule generation fails."""
    pass


class DriverLoanPostingException(DriverLoanBaseException):
    """Exception raised when loan posting to ledger fails."""
    pass


class DriverLoanStatusException(DriverLoanBaseException):
    """Exception raised for invalid loan status transitions."""
    pass


class DriverLoanValidationException(DriverLoanBaseException):
    """Exception raised when loan validation fails."""
    pass


class DriverLoanCalculationException(DriverLoanBaseException):
    """Exception raised when loan calculations fail."""
    pass


class DriverLoanUpdateException(DriverLoanBaseException):
    """Exception raised when loan update fails."""
    pass


class DriverLoanPermissionException(DriverLoanBaseException):
    """Exception raised when user lacks permission for loan operations."""
    pass


class DriverLoanDuplicateException(DriverLoanBaseException):
    """Exception raised when attempting to create duplicate loan."""
    pass


class DriverLoanBalanceException(DriverLoanBaseException):
    """Exception raised for loan balance issues."""
    pass