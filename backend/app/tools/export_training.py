"""Export scan data for training/evaluation.  Usage (run against the production DATABASE_URL, never commit the output):

    HC_DATABASE_URL=... python -m app.tools.export_training --out export/ [--with-images]

Writes export/scans.jsonl (one record per scan, no email/name, user ids replaced by a salted hash) and, with --with-images,
export/images/<sha256>.jpg for photos the user opted in to share. Photos are never exported without opt-in because they
are never stored without it.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import make_engine, make_session_factory
from app.models import PredictionFeedback, ScanRecord


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--with-images", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "images").mkdir(parents=True, exist_ok=True)
    salt = secrets.token_hex(8)  # new salt each export: ids can't be linked across exports
    factory = make_session_factory(make_engine(get_settings().database_url))
    n = imgs = 0
    with factory() as db, open(out / "scans.jsonl", "w", encoding="utf-8") as f:
        fb = {}
        for row in db.scalars(select(PredictionFeedback)):
            fb.setdefault(row.prediction_id, []).append(row.correction)
        for r in db.scalars(select(ScanRecord).order_by(ScanRecord.id)):
            rec = {"id": r.id, "at": r.created_at.isoformat(), "kind": r.kind, "barcode": r.barcode, "model": r.model_name,
                   "user": hashlib.sha256(f"{salt}:{r.user_id}".encode()).hexdigest()[:12], "extracted": r.extracted,
                   "outcome": r.outcome, "feedback": fb.get(r.prediction_id), "image_sha256": r.image_sha256,
                   "has_image": r.image is not None}
            if a.with_images and r.image:
                (out / "images" / f"{r.image_sha256}.jpg").write_bytes(r.image)
                imgs += 1
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    print(f"exported {n} scans, {imgs} images -> {out}")


if __name__ == "__main__":
    main()
