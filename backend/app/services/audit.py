from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(db: Session, user_id: int | None, action: str, resource: str | None = None,
          resource_id: str | int | None = None) -> None:
    """Record who did what. Never pass health values or free text here."""
    db.add(AuditLog(user_id=user_id, action=action, resource=resource,
                    resource_id=None if resource_id is None else str(resource_id)))
    db.commit()
