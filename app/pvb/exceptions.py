# app/pvb/exceptions.py

"""
Custom exceptions for PVB (Parking Violations Bureau) module.
"""

from fastapi import HTTPException, status


class PVBBaseException(Exception):
    """Base exception for PVB module"""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class PVBViolationNotFoundException(PVBBaseException):
    """Raised when a PVB violation is not found"""
    def __init__(self, violation_id: int):
        super().__init__(
            message=f"PVB violation with ID {violation_id} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )


class PVBLogNotFoundException(PVBBaseException):
    """Raised when a PVB log is not found"""
    def __init__(self, log_id: int):
        super().__init__(
            message=f"PVB log with ID {log_id} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )


class PVBFileValidationException(PVBBaseException):
    """Raised when PVB file validation fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"File validation failed: {message}",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class PVBImportException(PVBBaseException):
    """Raised when PVB data import fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Import failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class PVBAssociationException(PVBBaseException):
    """Raised when PVB association fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Association failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class PVBPostingException(PVBBaseException):
    """Raised when posting PVB violations fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Posting failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class PVBExportException(PVBBaseException):
    """Raised when exporting PVB data fails"""
    def __init__(self, message: str):
        super().__init__(
            message=f"Export failed: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class PVBUpdateException(PVBBaseException):
    """Raised when updating PVB violation fails"""
    def __init__(self, violation_id: int, message: str):
        super().__init__(
            message=f"Failed to update violation {violation_id}: {message}",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class PVBDateParseException(PVBBaseException):
    """Raised when date parsing fails"""
    def __init__(self, date_str: str, formats_tried: list):
        super().__init__(
            message=f"Failed to parse date '{date_str}'. Tried formats: {formats_tried}",
            status_code=status.HTTP_400_BAD_REQUEST
        )


class PVBDuplicateSummonsException(PVBBaseException):
    """Raised when a duplicate summons number is detected"""
    def __init__(self, summons_number: str):
        super().__init__(
            message=f"PVB violation with summons number '{summons_number}' already exists",
            status_code=status.HTTP_409_CONFLICT
        )


def convert_to_http_exception(exc: PVBBaseException) -> HTTPException:
    """Convert custom exception to HTTPException"""
    return HTTPException(
        status_code=exc.status_code,
        detail=exc.message
    )

