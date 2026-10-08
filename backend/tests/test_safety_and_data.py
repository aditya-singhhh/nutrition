import csv
import json

import pytest

from app.core.config import DATA_DIR
from app.domain.barcode import normalize_barcode
from app.domain.nutrition import energy_is_consistent
from app.safety.engine import screen_user_message, validate_reply

NUTR = ["energy_kcal", "protein_g", "carbs_g", "fat_g", "sat_fat_g", "fiber_g", "sugar_g", "sodium_mg"]


# ---------------------------------------------------------------- input screening
@pytest.mark.parametrize("text,level", [
    ("I have chest pain after eating", "emergency"),
    ("my lips are swelling after eating peanuts", "emergency"),
    ("I think I'm having an allergic reaction", "emergency"),
    ("my sugar is very low and I feel faint", "emergency"),
    ("I want to kill myself", "crisis"),
    ("how can I purge after meals", "eating_disorder"),
    ("I want to starve myself", "eating_disorder"),
    ("help me lose 10 kg in a week", "dangerous_diet"),
    ("lose 5 kg in 2 weeks", "dangerous_diet"),
    ("make a plan to eat 800 calories a day", "dangerous_diet"),
    ("I want to fast for 5 days", "dangerous_diet"),
    ("how many units of insulin should I take", "medication"),
    ("should I stop taking my metformin", "medication"),
])
def test_risky_messages_are_blocked_from_llm(text, level):
    r = screen_user_message(text)
    assert r.level == level and r.blocks_llm and r.message


@pytest.mark.parametrize("text", [
    "Can I eat a banana if I have diabetes?",
    "Is masala dosa good for breakfast?",
    "I'd like a high protein dinner with 30 g protein",
    "I want to lose 2 kg in a month",
    "make a plan with 1500 calories a day",
    "What is the barcode 8900000000012 like?",
])
def test_normal_messages_pass(text):
    assert screen_user_message(text).level == "ok"


def test_crisis_message_has_india_resources_and_no_medical_content():
    m = screen_user_message("I want to end my life").message
    assert "112" in m and "14416" in m


def test_eating_disorder_reply_contains_no_numbers():
    assert not any(ch.isdigit() for ch in screen_user_message("how to purge").message)


# ---------------------------------------------------------------- output validation
FACTS = {"nutrition": {"energy_kcal": 285.0, "protein_g": 6.3}}


def test_validator_accepts_supported_numbers():
    ok, p = validate_reply("It has about 285 kcal and 6.3 g protein.", FACTS)
    assert ok and not p


def test_validator_rejects_invented_numbers():
    ok, p = validate_reply("It has about 500 kcal.", FACTS)
    assert not ok and p[0].startswith("unsupported_number")


@pytest.mark.parametrize("text", ["You probably have diabetes.", "You may want to reduce your insulin.",
                                  "Skip your medication tonight."])
def test_validator_rejects_diagnosis_and_medication_advice(text):
    ok, p = validate_reply(text, FACTS)
    assert not ok


# ---------------------------------------------------------------- seed data integrity
def _foods():
    return list(csv.DictReader(open(DATA_DIR / "foods.csv", encoding="utf-8")))


def test_food_seed_size_and_uniqueness():
    rows = _foods()
    assert 50 <= len(rows) <= 100
    assert len({r["slug"] for r in rows}) == len(rows)
    assert all(r["slug"] == r["slug"].lower() and " " not in r["slug"] for r in rows)


def test_food_seed_numbers_are_internally_consistent():
    for r in _foods():
        n = {k: float(r[k]) for k in NUTR}
        assert energy_is_consistent(n, 0.15), f"{r['slug']}: stated kcal vs macros"
        assert n["sugar_g"] <= n["carbs_g"] and n["sat_fat_g"] <= n["fat_g"] and n["fiber_g"] <= n["carbs_g"], r["slug"]
        assert all(v >= 0 for v in n.values())
        assert float(r["serving_g"]) > 0
        assert r["diet_type"] in {"vegan", "vegetarian", "eggetarian", "non_vegetarian"}


def test_diet_type_matches_allergens():
    for r in _foods():
        al = set(a for a in r["allergens"].split(";") if a)
        if r["diet_type"] == "vegan":
            assert not ({"milk", "egg", "fish"} & al), r["slug"]
        if r["diet_type"] in ("vegetarian",):
            assert not ({"egg", "fish"} & al), r["slug"]


def test_demo_products_have_valid_barcodes_and_are_flagged_unverified():
    for p in json.load(open(DATA_DIR / "products_demo.json")):
        assert normalize_barcode(p["barcode"]) == p["barcode"]
        assert p["verified"] is False and p["source"] == "demo_fixture"


def test_additive_reference_data_quality():
    d = json.load(open(DATA_DIR / "additives.json", encoding="utf-8"))
    cats = set(d["categories"])
    codes = [a["ins"] for a in d["additives"]]
    assert len(codes) == len(set(codes))
    for a in d["additives"]:
        assert a["category"] in cats and a["evidence_source"] and a["explanation"] and a["names"]


def test_guideline_rules_all_cite_a_source():
    g = json.load(open(DATA_DIR / "guidelines.json"))
    for spec in [*g["conditions"].values(), *g["goals"].values()]:
        assert abs(sum(r["weight"] for r in spec["rules"]) - 1.0) < 1e-9
        assert all(r["source"] and r["reason"] for r in spec["rules"])
