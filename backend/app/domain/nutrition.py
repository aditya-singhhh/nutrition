"""Deterministic Nutrition Engine. Pure functions, no I/O, no LLM.

Reference data is stored per 100 g. Unknown nutrients stay None - they are never
guessed or defaulted to zero, because "unknown" and "zero" mean different things.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

NUTRIENT_KEYS: tuple[str, ...] = (
    "energy_kcal",
    "protein_g",
    "carbs_g",
    "fat_g",
    "sat_fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
    "potassium_mg",
    "iron_mg",
    "calcium_mg",
    "vitamin_b12_ug",
    "folate_ug",
    "vitamin_d_ug",
)

Nutrients = dict[str, float | None]


def _clean(per100g: Mapping[str, float | None]) -> Nutrients:
    return {k: (None if per100g.get(k) is None else float(per100g[k])) for k in NUTRIENT_KEYS}


def scale_nutrients(per100g: Mapping[str, float | None], grams: float) -> Nutrients:
    """Nutrients for `grams` of a food. None stays None."""
    if grams < 0:
        raise ValueError("grams must be >= 0")
    factor = grams / 100.0
    return {k: (None if v is None else v * factor) for k, v in _clean(per100g).items()}


def scale_range(per100g: Mapping[str, float | None], grams_min: float, grams_max: float) -> dict[str, Nutrients]:
    """Nutrients for an estimated portion range (photo estimates are never a single exact number)."""
    if grams_min > grams_max:
        raise ValueError("grams_min must be <= grams_max")
    return {"min": scale_nutrients(per100g, grams_min), "max": scale_nutrients(per100g, grams_max)}


@dataclass
class NutrientTotals:
    values: dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in NUTRIENT_KEYS})
    # nutrients where at least one contributing item had no data -> total is a lower bound
    incomplete: set[str] = field(default_factory=set)


def sum_nutrients(items: Iterable[Mapping[str, float | None]]) -> NutrientTotals:
    totals = NutrientTotals()
    for item in items:
        for k in NUTRIENT_KEYS:
            v = item.get(k)
            if v is None:
                totals.incomplete.add(k)
            else:
                totals.values[k] += float(v)
    return totals


def atwater_energy(per100g: Mapping[str, float | None]) -> float | None:
    """Energy implied by macros (4/4/9 kcal/g; fibre counted at 2). None if macros are missing."""
    p, c, f = (per100g.get(k) for k in ("protein_g", "carbs_g", "fat_g"))
    if p is None or c is None or f is None:
        return None
    fiber = per100g.get("fiber_g") or 0.0
    # carbs_g is total carbohydrate (includes fibre); fibre supplies ~2 kcal/g rather than 4.
    return 4 * p + 4 * (c - fiber) + 2 * fiber + 9 * f


def energy_is_consistent(per100g: Mapping[str, float | None], tolerance: float = 0.20) -> bool:
    """Data-integrity check: stated energy should be within `tolerance` of the Atwater estimate."""
    stated = per100g.get("energy_kcal")
    implied = atwater_energy(per100g)
    if stated is None or implied is None:
        return False
    if implied == 0:
        return stated <= 5
    return abs(stated - implied) / implied <= tolerance


def round_nutrients(n: Mapping[str, float | None], ndigits: int = 1) -> Nutrients:
    return {k: (None if v is None else round(v, ndigits)) for k, v in n.items()}
