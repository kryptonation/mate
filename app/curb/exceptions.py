# app/curb/exceptions.py

"""
Custom exceptions for CURB (Taxi Fleet) module.
"""

from fastapi import HTTPException, status


class CURBBaseException(Exception):
    """Base exception for CURB module"""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class CURBTripNotFoundException(CURBBaseException):
    """Raised when a CURB trip is not found"""
    def __init__(self, trip_id: int):
        super().__init__(
            message=f"CURB trip with ID {trip_id} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )


class CURBImportLogNotFoundException(CURBBaseException):
    """Raised when a CURB import log is not found"""
    def __init__(self, log_id: int):
        super().__init__(
            message=f"CURB import log with ID {log_id} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )


class CURBFileValidationException(CURBBaseException):
    """Raised when CURB file validation fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"File validation failed: {message}",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class CURBImportException(CURBBaseException):
    """Raised when CURB data import fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Import failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class CURBReconciliationException(CURBBaseException):
    """Raised when CURB trip reconciliation fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Reconciliation failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class CURBAssociationException(CURBBaseException):
    """Raised when CURB trip association fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Association failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class CURBPostingException(CURBBaseException):
    """Raised when posting CURB trips to ledger fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Posting to ledger failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class CURBExportException(CURBBaseException):
    """Raised when exporting CURB data fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Export failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class CURBUpdateException(CURBBaseException):
    """Raised when updating CURB trip fails"""
    def __init__(self, trip_id: int, message: str):
        super().__init__(
            message=f"Failed to update trip {trip_id}: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class CURBSOAPException(CURBBaseException):
    """Raised when SOAP API call fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"SOAP API call failed: {message}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


class CURBXMLParseException(CURBBaseException):
    """Raised when XML parsing fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"XML parsing failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class CURBDuplicateTripException(CURBBaseException):
    """Raised when a duplicate trip is detected"""
    def __init__(self, record_id: str, period: str):
        super().__init__(
            message=f"CURB trip with record_id '{record_id}' and period '{period}' already exists",
            status_code=status.HTTP_409_CONFLICT
        )


def convert_to_http_exception(exc: CURBBaseException) -> HTTPException:
    """Convert custom exception to HTTPException"""
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.message
    )