from sqlalchemy.orm import Session

from app.utils.logger import get_logger
from app.esign import utils as esign_utils
from app.leases.services import lease_service

logger = get_logger(__name__)


async def driverlease_recipient_completed(db: Session, ctx: dict, payload: dict):
    logger.info("[driverlease] recipient-completed: %s", ctx)
    try:
        summary = lease_service.update_lease_driver_document_signoff_latest(db, ctx=ctx)
        if not summary.get("ok"):
            logger.warning(
                "[driverlease] recipient-completed: no update performed "
                "(envelope_id=%s, recipient_id=%s, reason=%s)",
                ctx.get("envelope_id"),
                ctx.get("recipient_id"),
                summary.get("reason"),
            )
        else:
            logger.info(
                "[driverlease] recipient-completed: updated LDD id=%s for envelope %s (recipient_id=%s)",
                summary.get("lease_driver_document_id"),
                summary.get("envelope_id"),
                summary.get("recipient_id"),
            )
        # No commit/rollback here; upstream handles transaction boundaries.
        return summary
    except Exception as e:
        logger.exception("[driverlease] recipient-completed: error: %s", e)
        return {"ok": False, "error": str(e), "envelope_id": ctx.get("envelope_id")}


async def driverlease_recipient_delivered(db: Session, ctx: dict, payload: dict):
    logger.info("[driverlease] recipient-delivered: %s", ctx)


async def driverlease_recipient_declined(db: Session, ctx: dict, payload: dict):
    logger.info("[driverlease] recipient-declined: %s", ctx)


async def driverlease_envelope_sent(db: Session, ctx: dict, payload: dict):
    logger.info("[driverlease] envelope-sent: %s", ctx)
    rows = esign_utils.update_envelope_status(db, ctx=ctx, status="envelope-sent")
    # Ensure pending UPDATE is pushed to the DB connection without committing
    db.flush()
    if rows == 0:
        logger.warning(
            "[driverlease] envelope-sent: no envelope updated (id=%s, lease_id=%s)",
            ctx.get("envelope_id"),
            ctx.get("lease_id") or ctx.get("object_id"),
        )
    return {
        "ok": rows > 0,
        "updated_rows": rows,
        "envelope_id": ctx.get("envelope_id"),
        "status": "sent",
    }


async def driverlease_envelope_completed(db: Session, ctx: dict, payload: dict):
    logger.info("[driverlease] envelope-completed: %s", ctx)
    rows = esign_utils.update_envelope_status(db, ctx=ctx, status="envelope-completed")
    db.flush()
    if rows == 0:
        logger.warning(
            "[driverlease] envelope-completed: no envelope updated (id=%s, lease_id=%s)",
            ctx.get("envelope_id"),
            ctx.get("lease_id") or ctx.get("object_id"),
        )
    return {
        "ok": rows > 0,
        "updated_rows": rows,
        "envelope_id": ctx.get("envelope_id"),
        "status": "completed",
    }
