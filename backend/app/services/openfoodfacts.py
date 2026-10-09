"""Open Food Facts lookup for barcodes we don't have. Public, crowd-sourced data: always stored as UNVERIFIED."""
from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from app.models import PackagedProduct

logger = logging.getLogger(__name__)

_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
_FIELDS = "product_name,brands,nutriments,ingredients_text,allergens_tags,nova_group,serving_quantity,countries_tags"


def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f >= 0 else None


def map_nutrients(n: dict) -> dict:
    """OFF per-100g -> our keys. Missing stays missing (None is not 0)."""
    out: dict[str, float] = {}
    kcal = _num(n.get("energy-kcal_100g"))
    if kcal is None and _num(n.get("energy_100g")) is not None:  # kJ -> kcal
        kcal = round(_num(n.get("energy_100g")) / 4.184, 1)
    pairs = {"energy_kcal": kcal, "protein_g": _num(n.get("proteins_100g")), "carbs_g": _num(n.get("carbohydrates_100g")),
             "fat_g": _num(n.get("fat_100g")), "sat_fat_g": _num(n.get("saturated-fat_100g")),
             "fiber_g": _num(n.get("fiber_100g")), "sugar_g": _num(n.get("sugars_100g"))}
    na = _num(n.get("sodium_100g"))
    if na is None and _num(n.get("salt_100g")) is not None:
        na = _num(n.get("salt_100g")) / 2.5
    if na is not None:
        pairs["sodium_mg"] = round(na * 1000, 1)
    out.update({k: v for k, v in pairs.items() if v is not None})
    return out


def fetch_product(code: str, client: httpx.Client | None = None) -> dict | None:
    try:
        r = (client or httpx).get(_URL.format(code=code), params={"fields": _FIELDS}, timeout=8.0,
                                  headers={"User-Agent": "HealthCompanion/0.1 (nutrition app)"})
        if r.status_code != 200:
            return None
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.info("OFF lookup failed: %s", type(e).__name__)
        return None
    if data.get("status") != 1 or not isinstance(data.get("product"), dict):
        return None
    return data["product"]


def lookup_and_store(db: Session, code: str, client: httpx.Client | None = None) -> PackagedProduct | None:
    p = fetch_product(code, client)
    if p is None:
        return None
    nutrients = map_nutrients(p.get("nutriments") or {})
    if "energy_kcal" not in nutrients:  # too incomplete to score; user should scan the label instead
        return None
    nova = p.get("nova_group")
    countries = p.get("countries_tags") or []
    prod = PackagedProduct(
        barcode=code, brand=(p.get("brands") or "Unknown").split(",")[0].strip()[:80] or "Unknown",
        name=(p.get("product_name") or "Unnamed product").strip()[:160], category="packaged",
        serving_g=_num(p.get("serving_quantity")), nutrients_per_100g=nutrients,
        ingredients_text=p.get("ingredients_text") or None,
        allergens=[t.split(":")[-1] for t in (p.get("allergens_tags") or [])], additives=[],
        nova=nova if nova in (1, 2, 3, 4) else None, country="IN" if "en:india" in countries else "XX",
        source="open_food_facts", confidence="crowd_sourced", verified=False)
    db.add(prod)
    db.commit()
    return prod
