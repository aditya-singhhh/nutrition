"""Catalog lookups + evaluation (quality score, personal compatibility, per-serving nutrition)."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.compat import FoodView, UserContext, evaluate_personal
from app.domain.ingredients import analyze_ingredients
from app.domain.nutrition import round_nutrients, scale_nutrients
from app.domain.scoring import score_food
from app.models import FoodItem, PackagedProduct, User

_UNVERIFIED_WARNING = (
    "This data is not verified ({source}). Treat the numbers as approximate."
)


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9ऀ-ॿ ]+", " ", s.lower()).strip()


def user_context(user: User) -> UserContext:
    p = user.profile
    return UserContext(
        conditions=[c.condition for c in user.conditions],
        allergies=[a.allergen for a in user.allergies],
        diet_preference=p.diet_preference if p else None,
        goal=p.goal if p else None,
    )


def trust_level(obj) -> str:
    """verified (checked by us) > community_confirmed (2+ independent label scans agree) > from_scan (one user's scan) > community (open database)."""
    if obj.verified:
        return "verified"
    if obj.source == "user_label_scan":
        return "community_confirmed" if (getattr(obj, "confirmations", 0) or 0) >= 2 else "from_scan"
    return "community"


def data_quality(obj) -> dict:
    dq = {"source": obj.source, "confidence": obj.confidence, "verified": obj.verified, "trust": trust_level(obj)}
    if not obj.verified:
        dq["warning"] = _UNVERIFIED_WARNING.format(source=obj.source)
    return dq


def food_summary(f: FoodItem) -> dict:
    return {"id": f.id, "slug": f.slug, "name": f.name, "category": f.category, "region": f.region,
            "diet_type": f.diet_type, "allergens": f.allergens,
            "serving": {"grams": f.serving_g, "label": f.serving_label}}


def search_foods(db: Session, query: str, limit: int = 10) -> list[FoodItem]:
    q = _norm(query)
    if not q:
        return []
    scored: list[tuple[int, FoodItem]] = []
    for f in db.scalars(select(FoodItem)):
        names = [_norm(f.name), *[_norm(a) for a in f.aliases]]
        best = 0
        for n in names:
            if q == n:
                best = max(best, 100)
            elif n.startswith(q):
                best = max(best, 80)
            elif q in n:
                best = max(best, 60)
            elif set(q.split()) & set(n.split()):
                best = max(best, 30)
        if best:
            scored.append((best, f))
    scored.sort(key=lambda t: (-t[0], t[1].name))
    return [f for _, f in scored[:limit]]


def find_food_in_text(db: Session, text: str) -> FoodItem | None:
    """Longest food name/alias that appears as a whole phrase in free text."""
    t = f" {_norm(text)} "
    best: tuple[int, FoodItem] | None = None
    for f in db.scalars(select(FoodItem)):
        for n in [_norm(f.name), *[_norm(a) for a in f.aliases]]:
            if n and f" {n} " in t and (best is None or len(n) > best[0]):
                best = (len(n), f)
    return best[1] if best else None


def get_food(db: Session, food_id: int) -> FoodItem | None:
    return db.get(FoodItem, food_id)


def get_food_by_slug(db: Session, slug: str) -> FoodItem | None:
    return db.scalar(select(FoodItem).where(FoodItem.slug == slug))


def get_product(db: Session, barcode: str) -> PackagedProduct | None:
    return db.scalar(select(PackagedProduct).where(PackagedProduct.barcode == barcode))


def find_product_in_text(db: Session, text: str) -> PackagedProduct | None:
    t = f" {_norm(text)} "
    for p in db.scalars(select(PackagedProduct)):
        if f" {_norm(p.name)} " in t:
            return p
    return None


def nutrition_for(per100g: dict, grams: float) -> dict:
    return round_nutrients(scale_nutrients(per100g, grams))


def evaluate_food(food: FoodItem, ctx: UserContext, grams: float | None = None) -> dict:
    g = grams if grams is not None else food.serving_g
    score = score_food(food.nutrients_per_100g, category=food.category, nova=food.nova, verified=food.verified)
    compat = evaluate_personal(
        FoodView(food.name, food.nutrients_per_100g, allergens=list(food.allergens), diet_type=food.diet_type), ctx)
    return {
        "type": "food", "id": food.id, "slug": food.slug, "name": food.name, "category": food.category,
        "portion": {"grams": g, "label": food.serving_label if grams is None else f"{g:g} g"},
        "nutrition_for_portion": nutrition_for(food.nutrients_per_100g, g),
        "nutrition_per_100g": round_nutrients(food.nutrients_per_100g),
        "quality_score": score, "personal_compatibility": compat, "data_quality": data_quality(food),
    }


def evaluate_product(prod: PackagedProduct, ctx: UserContext, grams: float | None = None) -> dict:
    g = grams if grams is not None else (prod.serving_g or 100.0)
    analysis = analyze_ingredients(prod.ingredients_text or "")
    known = bool(analysis.ingredients)
    nova = prod.nova if prod.nova is not None else analysis.estimated_nova
    score = score_food(prod.nutrients_per_100g, category=prod.category, nova=nova, additives=analysis.additives,
                       ingredient_flags=analysis.flags, ingredients_known=known, verified=prod.verified)
    if not any(v is not None for v in prod.nutrients_per_100g.values()):
        # Ingredients only: a score from ingredient quality alone would look far more certain than it is.
        score = {**score, "score": None, "band": None, "confidence": "none",
                 "summary": "No nutrition values on record for this product, so we can't score it. Scan its nutrition label to add them."}
    compat = evaluate_personal(
        FoodView(prod.name, prod.nutrients_per_100g, allergens=sorted(set(analysis.allergens) | set(prod.allergens)),
                 may_contain=analysis.may_contain), ctx)
    return {
        "type": "product", "barcode": prod.barcode, "brand": prod.brand, "name": prod.name, "category": prod.category,
        "portion": {"grams": g, "label": "1 serving" if grams is None and prod.serving_g else f"{g:g} g"},
        "nutrition_for_portion": nutrition_for(prod.nutrients_per_100g, g),
        "nutrition_per_100g": round_nutrients(prod.nutrients_per_100g),
        "ingredients": analysis.to_dict(),
        "quality_score": score, "personal_compatibility": compat, "data_quality": data_quality(prod),
    }


_AGREE_KEYS = ("energy_kcal", "protein_g", "carbs_g", "sugar_g", "fat_g", "sat_fat_g", "sodium_mg")


def values_agree(a: dict, b: dict, tol: float = 0.10) -> bool:
    """True when at least 3 nutrients are present in both and every shared one is within `tol` (or 0.5 absolute for tiny values)."""
    shared = [k for k in _AGREE_KEYS if a.get(k) is not None and b.get(k) is not None]
    if len(shared) < 3:
        return False
    return all(abs(a[k] - b[k]) <= max(tol * max(abs(a[k]), abs(b[k])), 0.5) for k in shared)


def confirm_from_label(db: Session, prod: PackagedProduct, per100: dict, user) -> bool:
    """A user-scanned product gains trust when DIFFERENT users' label scans agree with it. Each user counts once; a
    disagreeing scan changes nothing (it is kept in the scan log for review)."""
    from app.models import ScanRecord
    if prod.source != "user_label_scan" or prod.verified:
        return False
    if not values_agree(prod.nutrients_per_100g, per100):
        return False
    already = db.scalar(select(ScanRecord.id).where(ScanRecord.user_id == user.id, ScanRecord.barcode == prod.barcode,
                                                    ScanRecord.kind == "label").limit(1))
    if already:
        return False
    prod.confirmations = (prod.confirmations or 0) + 1
    db.commit()
    return True
