"""Sanity set: common Indian foods with typical label values (per 100 g, rounded). These guard against absurd results
(e.g. ghee scoring 100). The expected bands are deliberately loose common-sense limits, NOT clinical truth - the real
thresholds still need dietitian review (scoring_config.json: NEEDS_CLINICAL_REVIEW)."""
import pytest

from app.domain.scoring import score_food

def N(kcal, p, c, f, sat, fib, sug, na):
    return {"energy_kcal": kcal, "protein_g": p, "carbs_g": c, "fat_g": f, "sat_fat_g": sat, "fiber_g": fib,
            "sugar_g": sug, "sodium_mg": na}

# name, nutrients, category, nova, (min, max)
CASES = [
    ("ghee",              N(900, 0, 0, 100, 62, 0, 0, 0),        "fat_oil",  2, (20, 62)),
    ("butter (salted)",   N(720, 0.8, 0.5, 80, 50, 0, 0.5, 600), "fat_oil",  2, (15, 60)),
    ("cola",              N(42, 0, 10.6, 0, 0, 0, 10.6, 5),      "beverage", 4, (0, 55)),
    ("instant noodles",   N(440, 9, 61, 17, 8, 2.5, 2.5, 1750),  "noodles",  4, (0, 40)),
    ("glucose biscuit",   N(450, 6.5, 77, 12.5, 6, 1.5, 24, 330), "biscuit", 4, (0, 45)),
    ("namkeen / chips",   N(540, 7, 50, 34, 14, 3, 2, 800),      "snack",    4, (0, 40)),
    ("rolled oats",       N(380, 13, 66, 7, 1.3, 10, 1, 5),      "cereal",   1, (70, 100)),
    ("plain curd",        N(60, 3.5, 4.7, 3.3, 2.1, 0, 4.7, 46), "dairy",    1, (45, 100)),
    ("dal (cooked)",      N(120, 7, 18, 2, 0.4, 5, 1, 250),      "pulse",    1, (55, 100)),
    ("banana",            N(89, 1.1, 22.8, 0.3, 0.1, 2.6, 12, 1), "fruit",   1, (70, 100)),
    ("almonds",           N(580, 21, 22, 50, 3.8, 12, 4, 1),     "nuts",     1, (45, 100)),
    ("white bread",       N(265, 9, 49, 3.2, 0.7, 2.7, 5, 490),  "bread",    3, (25, 70)),
]


@pytest.mark.parametrize("name,nutrients,category,nova,bounds", CASES, ids=[c[0] for c in CASES])
def test_common_foods_land_in_sensible_bands(name, nutrients, category, nova, bounds):
    r = score_food(nutrients, category=category, nova=nova, ingredients_known=True, verified=True)
    lo, hi = bounds
    assert r["score"] is not None and lo <= r["score"] <= hi, f"{name} scored {r['score']} ({r['band']}), expected {lo}-{hi}"


def test_ordering_oats_beat_biscuit_beat_noodles_roughly():
    s = {n: score_food(d, category=c, nova=nv, ingredients_known=True)["score"] for n, d, c, nv, _ in CASES}
    assert s["rolled oats"] > s["glucose biscuit"] and s["rolled oats"] > s["instant noodles"] and s["banana"] > s["cola"]


@pytest.mark.parametrize("partial", [
    {}, {"energy_kcal": 900, "fat_g": 100}, {"energy_kcal": 900, "fat_g": 100, "sugar_g": 0, "sodium_mg": 0, "protein_g": 0},
])
def test_incomplete_data_never_gets_a_number(partial):
    r = score_food(partial, category="packaged", nova=2, ingredients_known=True)
    assert r["score"] is None and "sat_fat" in r["missing_required"]


def test_ghee_ingredients_only_cannot_score_100():
    r = score_food({}, category="packaged", ingredients_known=True)  # label said only "cow milk fat"
    assert r["score"] is None
    assert r["score_range"] is None or r["score_range"]["min"] < 100
