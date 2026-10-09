"""Healthier options: better-scoring products of the SAME family, safe for this user. Pure ranking over our tables, no AI.

Rules: same category (never compare ghee with cereal), must have a real score (not None), at least +10 points better,
no allergen block, personal fit not worse than 50, and the reason is stated with the actual numbers.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import FoodItem, PackagedProduct, User
from app.services import catalog, openfoodfacts

MIN_GAIN = 10
LIMIT = 3
# (key, reason code, lower is better)
_COMPARE = [("sugar_g", "less_sugar", True), ("sodium_mg", "less_salt", True), ("sat_fat_g", "less_sat_fat", True), ("fiber_g", "more_fibre", False),
            ("protein_g", "more_protein", False)]


def _why(base: dict, alt: dict) -> list[dict]:
    out = []
    for key, code, lower in _COMPARE:
        a, b = base.get(key), alt.get(key)
        if a is None or b is None or a == 0 and b == 0:
            continue
        diff = (a - b) if lower else (b - a)
        rel = diff / a if a else (1.0 if diff > 0 else 0)
        if diff > 0 and rel >= 0.25:
            out.append({"code": code, "pct": round(100 * rel), "rel": rel})
    out.sort(key=lambda x: x["rel"], reverse=True)
    return [{"code": x["code"], "pct": x["pct"]} for x in out[:2]]


def _card(kind: str, ident: str, name: str, brand: str | None, ev: dict, base_score: int, base_per100: dict, trust: str | None) -> dict | None:
    q, pc = ev["quality_score"], ev["personal_compatibility"]
    if q.get("score") is None or q["score"] < base_score + MIN_GAIN:
        return None
    if pc.get("blocked") or (pc.get("overall") is not None and pc["overall"] < 50):
        return None
    return {"type": kind, "id": ident, "name": name, "brand": brand, "score": q["score"], "band": q["band"], "gain": q["score"] - base_score,
            "why": _why(base_per100, ev["nutrition_per_100g"]), "trust": trust}


def for_product(db: Session, user: User, prod: PackagedProduct, client=None) -> dict:
    ctx = catalog.user_context(user)
    base = catalog.evaluate_product(prod, ctx)
    score = base["quality_score"].get("score")
    if prod.category == "packaged":
        return {"status": "unknown_category", "items": []}
    if score is None:
        return {"status": "no_score", "items": []}

    def collect() -> list[dict]:
        found = []
        for other in db.scalars(select(PackagedProduct).where(PackagedProduct.category == prod.category, PackagedProduct.id != prod.id)):
            c = _card("product", other.barcode, other.name, other.brand, catalog.evaluate_product(other, ctx), score,
                      base["nutrition_per_100g"], catalog.trust_level(other))
            if c:
                found.append(c)
        return found

    items = collect()
    if len(items) < LIMIT and get_settings().off_lookup and openfoodfacts.fetch_family(db, prod.category, client):
        items = collect()
    items.sort(key=lambda c: (c["score"], c["trust"] == "verified"), reverse=True)
    return {"status": "ok" if items else "none_better", "items": items[:LIMIT]}


def for_food(db: Session, user: User, food: FoodItem) -> dict:
    ctx = catalog.user_context(user)
    base = catalog.evaluate_food(food, ctx)
    score = base["quality_score"].get("score")
    if score is None:
        return {"status": "no_score", "items": []}
    items = []
    for other in db.scalars(select(FoodItem).where(FoodItem.category == food.category, FoodItem.id != food.id)):
        c = _card("food", other.slug, other.name, None, catalog.evaluate_food(other, ctx), score, base["nutrition_per_100g"], None)
        if c:
            items.append(c)
    items.sort(key=lambda c: c["score"], reverse=True)
    return {"status": "ok" if items else "none_better", "items": items[:LIMIT]}
