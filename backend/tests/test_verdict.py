from app.services import catalog
from app.services.verdict import household, verdict


def _r(band, score, share, overall=None, blocked=False):
    return {"quality_score": {"band": band, "score": score},
            "personal_compatibility": {"overall": overall, "blocked": blocked},
            "daily_share": {"items": [{"key": k, "pct": v} for k, v in share.items()]}}


def test_household_measures():
    h = household({"sugar_g": 10, "sodium_mg": 800, "fat_g": 15})
    assert h == {"sugar_tsp": 2.5, "salt_tsp": 0.4, "fat_tsp": 3.0}
    assert household(None) is None
    assert household({"sugar_g": None}) is None  # unknown stays unknown, not 0


def test_verdict_bands():
    assert verdict(_r("excellent", 85, {"sugar_g": 5}))["code"] == "everyday"
    assert verdict(_r("moderate", 50, {"sat_fat_g": 30}))["code"] == "sometimes"
    assert verdict(_r("limit", 20, {"sugar_g": 60}))["code"] == "rarely"


def test_small_portion_of_moderate_food_is_small_ok():
    assert verdict(_r("moderate", 54, {"sat_fat_g": 10, "sugar_g": 0, "sodium_mg": 0}))["code"] == "small_ok"


def test_no_score_and_allergen():
    assert verdict(_r(None, None, {}))["code"] == "unknown"
    assert verdict(_r("good", 70, {}, blocked=True))["code"] == "avoid"


def test_personal_can_only_make_it_stricter():
    v = verdict(_r("good", 70, {"sugar_g": 30}, overall=30))
    assert v["code"] == "sometimes" and any(r["code"] == "not_ideal_for_you" for r in v["reasons"])
    assert verdict(_r("limit", 20, {"sugar_g": 60}, overall=95))["code"] == "rarely"


def test_values_agree():
    a = {"energy_kcal": 500, "fat_g": 20, "sugar_g": 10}
    assert catalog.values_agree(a, {"energy_kcal": 520, "fat_g": 21, "sugar_g": 10.4})
    assert not catalog.values_agree(a, {"energy_kcal": 700, "fat_g": 21, "sugar_g": 10})
    assert not catalog.values_agree(a, {"energy_kcal": 500, "fat_g": 20})  # too few shared
