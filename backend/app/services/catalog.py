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


def data_quality(obj) -> dict:
    dq = {"source": obj.source, "confidence": obj.confidence, "verified": obj.verified}
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
