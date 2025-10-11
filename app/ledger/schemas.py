### app/ledger/schemas.py

# Standard library imports
from enum import Enum as PyEnum


class LedgerSourceType(str, PyEnum):
    """Ledger source type"""
    EZPASS = "EZPASS"
    PVB = "PVB"
    CURB = "CURB"
    LEASE = "LEASE"
    FEE = "FEE"
    MANUAL_FEE = "MANUAL_FEE"
    CURB_CARD_TXN = "CURB_CARD_TXN"
    DTR = "DTR"
    OTHERS = "OTHERS"


class DTRStatus(str, PyEnum):
    """Daily Receipt Status"""
    DRAFT = "DRAFT"
    FINALIZED = "FINALIZED"
    PAID = "PAID"
    VOIDED = "VOIDED"