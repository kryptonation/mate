# app/ezpass/exceptions.py

"""
Custom exceptions for EZPass module.
"""

from fastapi import HTTPException, status


class EZPassBaseException(Exception):
    """Base exception for EZPass module"""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class EZPassTransactionNotFoundException(EZPassBaseException):
    """Raised when an EZPass transaction is not found"""
    def __init__(self, transaction_id: int):
        super().__init__(
            message=f"EZPass transaction with ID {transaction_id} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )


class EZPassLogNotFoundException(EZPassBaseException):
    """Raised when an EZPass log is not found"""
    def __init__(self, log_id: int):
        super().__init__(
            message=f"EZPass log with ID {log_id} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )


class EZPassFileValidationException(EZPassBaseException):
    """Raised when EZPass file validation fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"File validation failed: {message}",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class EZPassImportException(EZPassBaseException):
    """Raised when EZPass data import fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Import failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class EZPassAssociationException(EZPassBaseException):
    """Raised when EZPass association fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Association failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class EZPassPostingException(EZPassBaseException):
    """Raised when posting EZPass transactions to ledger fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Posting to ledger failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class EZPassExportException(EZPassBaseException):
    """Raised when exporting EZPass data fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Export failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class EZPassUpdateException(EZPassBaseException):
    """Raised when updating EZPass transaction fails"""
    def __init__(self, transaction_id: int, message: str):
        super().__init__(
            message=f"Failed to update transaction {transaction_id}: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def convert_to_http_exception(exc: EZPassBaseException) -> HTTPException:
    """Convert custom exception to HTTPException"""
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.message
    )