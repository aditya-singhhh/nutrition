import pytest

from app.domain.barcode import InvalidBarcode, normalize_barcode
from app.domain.compat import FoodView, UserContext, evaluate_personal
from app.domain.ingredients import analyze_ingredients
from app.domain.nutrition import (atwater_energy, energy_is_consistent, scale_nutrients, scale_range, sum_nutrients)
from app.domain.scoring import band_score, load_scoring_config, score_food
from app.domain.targets import ProfileInput, compute_targets

FOOD = {"energy_kcal": 200.0, "protein_g": 10.0, "carbs_g": 20.0, "fat_g": 8.0, "fiber_g": 4.0, "sodium_mg": None}


# ---------------------------------------------------------------- nutrition engine
def test_scale_is_linear_and_deterministic():
    assert scale_nutrients(FOOD, 100)["energy_kcal"] == 200.0
    assert scale_nutrients(FOOD, 250)["protein_g"] == 25.0
    assert scale_nutrients(FOOD, 0)["energy_kcal"] == 0.0


def test_unknown_stays_unknown_not_zero():
    assert scale_nutrients(FOOD, 100)["sodium_mg"] is None
    assert scale_nutrients(FOOD, 100)["iron_mg"] is None


def test_negative_grams_rejected():
    with pytest.raises(ValueError):
        scale_nutrients(FOOD, -1)


def test_sum_tracks_incomplete():
    t = sum_nutrients([scale_nutrients(FOOD, 100), scale_nutrients(FOOD, 50)])
    assert t.values["energy_kcal"] == 300.0
    assert "sodium_mg" in t.incomplete and "energy_kcal" not in t.incomplete


def test_range_min_max():
    r = scale_range(FOOD, 100, 200)
    assert r["min"]["energy_kcal"] == 200.0 and r["max"]["energy_kcal"] == 400.0
    with pytest.raises(ValueError):
        scale_range(FOOD, 200, 100)


def test_atwater_consistency():
    assert atwater_energy({"protein_g": 10, "carbs_g": 20, "fat_g": 8, "fiber_g": 0}) == 4 * 10 + 4 * 20 + 72
    assert energy_is_consistent({"energy_kcal": 190, "protein_g": 10, "carbs_g": 20, "fat_g": 8, "fiber_g": 0})
    assert not energy_is_consistent({"energy_kcal": 500, "protein_g": 10, "carbs_g": 20, "fat_g": 8})
    assert not energy_is_consistent({"energy_kcal": 100})  # missing macros -> cannot confirm


# ---------------------------------------------------------------- barcode
def test_barcode_formats():
    assert normalize_barcode("8900000000012") == "8900000000012"
    assert normalize_barcode("036000291452") == "0036000291452"  # UPC-A -> EAN-13
    assert normalize_barcode("96385074") == "96385074"  # EAN-8
    assert normalize_barcode("890 0000-000012") == "8900000000012"


@pytest.mark.parametrize("bad", ["8900000000013", "abc", "12345", "", "89000000000123456"])
def test_barcode_invalid(bad):
    with pytest.raises(InvalidBarcode):
        normalize_barcode(bad)


# ---------------------------------------------------------------- ingredients
def test_ins_codes_and_functions():
    a = analyze_ingredients("Wheat flour, Emulsifier (INS 322), Preservative (INS 211), Colour (E102)")
    codes = {x["ins"] for x in a.additives}
    assert {"322", "211", "102"} <= codes
    lec = next(x for x in a.additives if x["ins"] == "322")
    assert lec["function"] == "emulsifier" and lec["category"] == "generally_recognized"
    assert all(x["evidence_source"] for x in a.additives)


def test_bare_numbers_after_function_word_and_names():
    a = analyze_ingredients("Water, Acidity Regulator (330, 331), Sodium Benzoate")
    assert {x["ins"] for x in a.additives} >= {"330", "331", "211"}


def test_ins_sub_variant_and_unknown_codes():
    a = analyze_ingredients("Raising agent (INS 500(ii)), Preservative (INS 282)")
    assert "500" in {x["ins"] for x in a.additives}
    assert "282" in a.unrecognised_codes  # unknown codes are reported, never guessed


def test_additives_not_all_alarming():
    a = analyze_ingredients("Water, Citric Acid, Tartrazine, Potassium Bromate")
    cats = {x["ins"]: x["category"] for x in a.additives}
    assert cats["330"] == "generally_recognized"
    assert cats["102"] == "context_dependent"
    assert cats["924a"] == "high_concern"


def test_allergens_english_and_false_positives():
    a = analyze_ingredients("Wheat flour, Milk solids, Soy lecithin, Peanut butter, Coconut milk")
    assert set(a.allergens) >= {"gluten", "milk", "soy", "peanut"}
    only_pb = analyze_ingredients("Peanut butter, Cocoa butter, Coconut milk")
    assert "milk" not in only_pb.allergens


def test_allergens_hindi():
    a = analyze_ingredients("सामग्री: गेहूं का आटा, चीनी, दूध, काजू")
    assert set(a.allergens) >= {"gluten", "milk", "tree_nuts"}


def test_may_contain_and_contains_statements():
    a = analyze_ingredients("Sugar, Wheat Flour, Salt. Contains Wheat. May contain traces of Peanut.")
    assert "peanut" in a.may_contain and "peanut" not in a.allergens
    assert "gluten" in a.allergens
    assert [i["raw"] for i in a.ingredients] == ["Sugar", "Wheat Flour", "Salt"]


def test_percent_nested_commas_and_flags():
    a = analyze_ingredients("Ingredients: Sugar, Refined wheat flour (maida) 45%, Edible oil (palm, hydrogenated), Salt")
    assert len(a.ingredients) == 4  # commas inside brackets don't split
    assert a.ingredients[1]["percent"] == 45.0
    codes = {f["code"] for f in a.flags}
    assert {"sugar_among_first_three", "hydrogenated_fat"} <= codes


def test_nova_estimates():
    assert analyze_ingredients("Rolled oats 100%").estimated_nova == 1
    assert analyze_ingredients("Flour, water, salt").estimated_nova == 3
    assert analyze_ingredients("Flour, colour (INS 102), flavour").estimated_nova == 4
    assert analyze_ingredients("").estimated_nova is None


# ---------------------------------------------------------------- scoring
def test_band_score_both_directions():
    assert band_score(5, good=5, bad=22.5) == 100
    assert band_score(22.5, good=5, bad=22.5) == 0
    assert band_score(30, good=5, bad=22.5) == 0
    assert 0 < band_score(10, good=5, bad=22.5) < 100
    assert band_score(6, good=6, bad=0.5) == 100  # higher-is-better


def test_weights_sum_to_one():
    assert abs(sum(load_scoring_config()["weights"].values()) - 1.0) < 1e-9


CHIPS = {"energy_kcal": 540, "protein_g": 6.5, "carbs_g": 52, "fat_g": 34, "sat_fat_g": 14, "fiber_g": 4,
         "sugar_g": 1, "sodium_mg": 640}
OATS = {"energy_kcal": 375, "protein_g": 12.5, "carbs_g": 63, "fat_g": 7, "sat_fat_g": 1.3, "fiber_g": 10,
        "sugar_g": 1, "sodium_mg": 6}


def test_score_orders_foods_sensibly_and_explains():
    chips, oats = score_food(CHIPS), score_food(OATS)
    assert oats["score"] > chips["score"]
    assert abs(sum(c["points"] for c in oats["components"]) - oats["score"]) <= 1  # points add up to the score
    assert all(c["source"] and c["explanation"] for c in oats["components"])


def test_missing_data_excluded_not_zeroed():
    r = score_food({"sugar_g": 5})
    assert r["score"] == 100 and r["confidence"] == "low"
    assert {e["key"] for e in r["excluded"]} >= {"sodium", "fiber"}
    assert score_food({})["score"] is None


def test_fruit_sugar_not_penalised_in_general_score():
    banana = {"energy_kcal": 89, "protein_g": 1.1, "carbs_g": 22.8, "fat_g": 0.3, "sat_fat_g": 0.1, "fiber_g": 2.6,
              "sugar_g": 12.2, "sodium_mg": 1}
    r = score_food(banana, category="fruit")
    assert "sugar" in {e["key"] for e in r["excluded"]}
    assert r["score"] >= 70


def test_additive_penalties_and_weight_override():
    base = score_food(OATS, nova=4, additives=[], ingredients_known=True)
    bad = score_food(OATS, nova=4, ingredients_known=True,
                     additives=[{"ins": "924a", "name": "Potassium bromate", "category": "high_concern"}])
    assert bad["score"] < base["score"]
    shifted = score_food(CHIPS, weights_override={"sodium": 0.6})
    assert shifted["score"] < score_food(CHIPS)["score"]


# ---------------------------------------------------------------- personal compatibility
def test_allergen_blocks():
    r = evaluate_personal(FoodView("x", OATS, allergens=["milk"]), UserContext(allergies=["milk"]))
    assert r["blocked"] and r["overall"] == 0 and r["alerts"][0]["severity"] == "block"


def test_trace_allergen_warns_but_does_not_block():
    r = evaluate_personal(FoodView("x", OATS, may_contain=["peanut"]), UserContext(allergies=["peanut"]))
    assert not r["blocked"] and r["alerts"][0]["type"] == "allergen_trace"


def test_conditions_change_the_answer_and_are_explained():
    cola = {"energy_kcal": 42, "protein_g": 0, "carbs_g": 10.6, "fat_g": 0, "sat_fat_g": 0, "fiber_g": 0,
            "sugar_g": 10.6, "sodium_mg": 8}
    diab = evaluate_personal(FoodView("cola", cola), UserContext(conditions=["diabetes"]))
    plain = evaluate_personal(FoodView("cola", cola), UserContext())
    assert plain["overall"] is None
    assert diab["overall"] < 50
    d = diab["conditions"][0]["details"]
    assert all(x["source"] and x["why_it_matters"] for x in d)
    noodles_sodium = {"sodium_mg": 1750, "sat_fat_g": 8}
    htn = evaluate_personal(FoodView("n", noodles_sodium), UserContext(conditions=["hypertension"]))
    assert htn["overall"] <= 10


def test_most_restrictive_condition_decides_and_unsupported_noted():
    r = evaluate_personal(FoodView("x", OATS), UserContext(conditions=["diabetes", "hyperuricemia"]))
    assert r["unsupported_conditions"] == ["hyperuricemia"]
    assert any("doctor or dietitian" in n for n in r["notes"])


def test_diet_preference_conflict():
    r = evaluate_personal(FoodView("x", OATS, diet_type="non_vegetarian"), UserContext(diet_preference="vegetarian"))
    assert any(a["type"] == "diet_preference" for a in r["alerts"])
    r2 = evaluate_personal(FoodView("x", OATS, allergens=["egg"]), UserContext(diet_preference="vegetarian"))
    assert any(a["type"] == "diet_preference" for a in r2["alerts"])


# ---------------------------------------------------------------- targets
def test_targets_known_values():
    t = compute_targets(ProfileInput(30, "male", 175, 75, "moderate", "maintain"))
    assert t["bmr_kcal"] == 1699 and t["energy_kcal"] == 2633 and t["protein_g"] == 62
    assert t["sodium_mg_max"] == 2000
    lose = compute_targets(ProfileInput(30, "male", 175, 75, "moderate", "lose"))
    assert lose["energy_kcal"] == 2238


def test_targets_safety_floor_and_gating():
    t = compute_targets(ProfileInput(25, "female", 150, 40, "sedentary", "lose"))
    assert t["energy_kcal"] == 1200 and t["safety_floor_applied"]
    assert compute_targets(ProfileInput(15, "male", 170, 55, "light", "maintain"))["reason"] == "paediatric_review_required"
    inc = compute_targets(ProfileInput(None, "male", None, 70, "light", None))
    assert not inc["available"] and set(inc["missing_fields"]) == {"age", "height_cm"}


def test_allergen_plurals_and_generic_nuts_are_detected():
    assert "peanut" in analyze_ingredients("Roasted peanuts 90%, salt").allergens
    assert "egg" in analyze_ingredients("Wheat flour, eggs").allergens
    assert "shellfish" in analyze_ingredients("Prawns, salt").allergens
    assert "tree_nuts" in analyze_ingredients("Mixed nuts, sugar").allergens


def test_database_url_gets_driver_prefix():
    from app.core.config import Settings
    assert Settings(database_url="postgres://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"
    assert Settings(database_url="postgresql://u:p@h/db").database_url == "postgresql+psycopg://u:p@h/db"
    assert Settings(database_url="sqlite:///x.db").database_url == "sqlite:///x.db"
