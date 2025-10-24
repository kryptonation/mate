# app/ledger/exceptions.py

"""
Custom exceptions for Centralized Ledger module.
"""

from fastapi import HTTPException, status


class LedgerBaseException(HTTPException):
    """Base exception for all ledger errors"""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR):
        super().__init__(status_code=status_code, detail=message)


class LedgerNotFoundException(LedgerBaseException):
    """Ledger entry not found"""
    def __init__(self, posting_id: str = None, balance_id: str = None):
        if posting_id:
            message = f"Ledger posting not found: {posting_id}"
        elif balance_id:
            message = f"Ledger balance not found: {balance_id}"
        else:
            message = "Ledger entry not found"
        super().__init__(message, status.HTTP_404_NOT_FOUND)


class InvalidLedgerEntryException(LedgerBaseException):
    """Invalid ledger entry"""
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class DuplicatePostingException(LedgerBaseException):
    """Duplicate posting detected"""
    def __init__(self, posting_id: str):
        message = f"Posting already exists: {posting_id}"
        super().__init__(message, status.HTTP_409_CONFLICT)


class NegativeBalanceException(LedgerBaseException):
    """Balance cannot go negative"""
    def __init__(self, balance_id: str, amount: float):
        message = f"Operation would result in negative balance for {balance_id}: {amount}"
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class ImmutablePostingException(LedgerBaseException):
    """Cannot edit posted entry"""
    def __init__(self, posting_id: str):
        message = f"Cannot modify posted entry: {posting_id}. Use reversal instead."
        super().__init__(message, status.HTTP_403_FORBIDDEN)


class PostingVoidedException(LedgerBaseException):
    """Posting already voided"""
    def __init__(self, posting_id: str):
        message = f"Posting already voided: {posting_id}"
        super().__init__(message, status.HTTP_400_BAD_REQUEST)


class ReconciliationException(LedgerBaseException):
    """Reconciliation failed"""
    def __init__(self, message: str):
        super().__init__(message, status.HTTP_500_INTERNAL_SERVER_ERROR)