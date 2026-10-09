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


def _variants(code: str) -> list[str]:
    """Same product can be indexed as EAN-13, UPC-A (12) or without leading zeros."""
    out = [code]
    for v in (code.zfill(13), code.lstrip("0"), code[1:] if len(code) == 13 and code[0] == "0" else ""):
        if v and v not in out:
            out.append(v)
    return out


def lookup_and_store(db: Session, code: str, client: httpx.Client | None = None) -> PackagedProduct | None:
    p = None
    for v in _variants(code):
        p = fetch_product(v, client)
        if p is not None:
            break
    if p is None:
        return None
    nutrients = map_nutrients(p.get("nutriments") or {})
    # Keep partial entries (name + ingredients, or some nutrients): unknown values stay unknown, never 0.
    if not nutrients and not (p.get("ingredients_text") or "").strip():
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
