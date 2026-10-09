"""Scan log for future training and auditing.

Always stored: what was scanned (kind, barcode), what the reader extracted, and what we showed. The PHOTO is stored only
if the user switched on 'help improve recognition' in Profile, and only up to MAX_IMAGE_BYTES. Rows are deleted with the
account. Logging must never break a scan, so failures are swallowed (and logged).
"""
from __future__ import annotations

import hashlib
import logging

from sqlalchemy.orm import Session

from app.models import ScanRecord, User

logger = logging.getLogger(__name__)
MAX_IMAGE_BYTES = 1_500_000


def record_scan(db: Session, user: User, kind: str, *, barcode: str | None = None, model: str | None = None,
                image: bytes | None = None, prediction_id: int | None = None, extracted: dict | None = None,
                outcome: dict | None = None) -> None:
    try:
        keep = bool(image) and bool(user.profile and user.profile.training_opt_in) and len(image) <= MAX_IMAGE_BYTES
        db.add(ScanRecord(user_id=user.id, kind=kind, barcode=barcode, model_name=model, prediction_id=prediction_id,
                          extracted=extracted or {}, outcome=outcome or {}, image=image if keep else None,
                          image_sha256=hashlib.sha256(image).hexdigest() if image else None))
        db.commit()
    except Exception:  # noqa: BLE001 - never fail the user's scan because logging failed
        db.rollback()
        logger.exception("scan log failed")
