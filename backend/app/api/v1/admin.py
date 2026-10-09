"""Product review queue: turns crowd data into 'checked by us'. Admin-only (HC_ADMIN_EMAILS)."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.models import PackagedProduct, ScanRecord, User
from app.services.audit import audit
from app.services.catalog import trust_level

router = APIRouter()


class ReviewIn(BaseModel):
    verified: bool = True
    note: str | None = None


@router.get("/admin/products/queue", tags=["admin"])
def queue(limit: int = 30, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Unverified products, most-scanned first. Items several users' scans agree on are marked so they can be approved quickly."""
    scans = dict(db.execute(select(ScanRecord.barcode, func.count()).where(ScanRecord.barcode.is_not(None)).group_by(ScanRecord.barcode)).all())
    rows = list(db.scalars(select(PackagedProduct).where(PackagedProduct.verified.is_(False))))
    items = [{"barcode": p.barcode, "name": p.name, "brand": p.brand, "category": p.category, "source": p.source,
              "scans": scans.get(p.barcode, 0), "confirmations": p.confirmations or 0, "trust": trust_level(p),
              "nutrients_per_100g": p.nutrients_per_100g, "serving_g": p.serving_g,
              "has_ingredients": bool(p.ingredients_text)} for p in rows]
    items.sort(key=lambda i: (i["confirmations"], i["scans"]), reverse=True)
    return {"count": len(items), "items": items[:max(1, min(limit, 100))]}


@router.post("/admin/products/{barcode}/review", tags=["admin"])
def review(barcode: str, body: ReviewIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    p = db.scalar(select(PackagedProduct).where(PackagedProduct.barcode == barcode))
    if p is None:
        raise HTTPException(404, "product not found")
    p.verified = body.verified
    p.last_verified = datetime.now(timezone.utc) if body.verified else None
    p.confidence = "reviewed" if body.verified else p.confidence
    db.commit()
    audit(db, admin.id, "review_product", "product", p.id)
    return {"barcode": p.barcode, "verified": p.verified, "trust": trust_level(p)}
