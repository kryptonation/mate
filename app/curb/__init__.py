# app/curb/__init__.py

"""
CURB (Taxi Fleet) Module

This module handles CURB taxi meter trip data processing including:
- Fetching trips from CURB SOAP API
- Importing trips into database
- Reconciling trips locally (dev/uat) or on server (production)
- Posting trips to ledgers with lease associations

Architecture:
- Models: SQLAlchemy 2.x ORM models with async support
- Repository: Data access layer with async database operations
- Services: Business logic layer with dependency injection
- Router: FastAPI endpoints with async handlers
- Tasks: Celery tasks for automated processing
- SOAP Client: Async HTTP client for CURB API
- Utils: XML parsing and data transformation utilities
"""

from app.curb.tasks import (
    fetch_and_import_curb_trips,
    reconcile_curb_trips,
    post_curb_trips,
    process_curb_trips_full,
    manual_fetch_curb_trips,
)

__all__ = [
    'fetch_and_import_curb_trips',
    'reconcile_curb_trips',
    'post_curb_trips',
    'process_curb_trips_full',
    'manual_fetch_curb_trips',
]