"""Idempotent loaders for reference data. Run: python -m app.seed

Food values in foods.csv are approximate seed values (see SEED_DATA_NOTICE) and are stored as
unverified until reconciled against IFCT 2017 / manufacturer data.
"""
from __future__ import annotations

import csv
import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import DATA_DIR
from app.domain.ingredients import analyze_ingredients
from app.models import FoodItem, PackagedProduct

logger = logging.getLogger(__name__)

SEED_DATA_NOTICE = (
    "Seed values are approximate, compiled for development, and NOT yet verified against IFCT 2017 or "
    "manufacturer labels. Do not present them to real users as verified until reconciled."
)
NUTRIENT_COLS = ["energy_kcal", "protein_g", "carbs_g", "fat_g", "sat_fat_g", "fiber_g", "sugar_g", "sodium_mg"]


def _split(v: str) -> list[str]:
    return [x.strip() for x in v.split(";") if x.strip()]


def seed_foods(db: Session) -> int:
    n = 0
    with open(DATA_DIR / "foods.csv", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            nutrients = {k: float(row[k]) for k in NUTRIENT_COLS}
            obj = db.scalar(select(FoodItem).where(FoodItem.slug == row["slug"]))
            if obj is None:
                obj = FoodItem(slug=row["slug"])
                db.add(obj)
            obj.name = row["name"]
            obj.aliases = _split(row["aliases"])
            obj.region = row["region"] or None
            obj.category = row["category"]
            obj.diet_type = row["diet_type"]
            obj.allergens = _split(row["allergens"])
            obj.nova = None  # home-style dishes: processing level intentionally not guessed
            obj.serving_g = float(row["serving_g"])
            obj.serving_label = row["serving_label"]
            obj.nutrients_per_100g = nutrients
            obj.source = "seed_approximate"
            obj.confidence = "needs_verification"
            obj.verified = False
            obj.country = "IN"
            n += 1
    db.commit()
    return n


def seed_products(db: Session) -> int:
    n = 0
    with open(DATA_DIR / "products_demo.json", encoding="utf-8") as f:
        for row in json.load(f):
            analysis = analyze_ingredients(row["ingredients_text"])
            obj = db.scalar(select(PackagedProduct).where(PackagedProduct.barcode == row["barcode"]))
            if obj is None:
                obj = PackagedProduct(barcode=row["barcode"])
                db.add(obj)
            for k in ("brand", "name", "category", "serving_g", "nutrients_per_100g", "ingredients_text", "country",
                      "source", "confidence", "verified"):
                setattr(obj, k, row[k])
            obj.allergens = analysis.allergens
            obj.additives = [a["ins"] for a in analysis.additives]
            obj.nova = analysis.estimated_nova
            n += 1
    db.commit()
    return n


def seed_all(db: Session) -> dict[str, int]:
    out = {"foods": seed_foods(db), "products": seed_products(db)}
    logger.info("seeded reference data: %s", out)
    return out


if __name__ == "__main__":  # pragma: no cover
    from app.core.config import get_settings
    from app.core.db import make_engine, make_session_factory
    from app.models import Base

    engine = make_engine(get_settings().database_url)
    Base.metadata.create_all(engine)
    with make_session_factory(engine)() as s:
        print(seed_all(s))
