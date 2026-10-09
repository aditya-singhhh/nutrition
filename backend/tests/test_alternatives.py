import httpx

from app.models import PackagedProduct, User
from app.services import alternatives, openfoodfacts as off


def _p(db, code, name, per100, category="biscuit", allergens=None, nova=3):
    p = PackagedProduct(barcode=code, brand="B", name=name, category=category, serving_g=30, nutrients_per_100g=per100,
                        ingredients_text="wheat flour, sugar", allergens=allergens or [], additives=[], nova=nova, country="IN",
                        source="open_food_facts", confidence="crowd_sourced", verified=False)
    db.add(p)
    db.commit()
    return p


BAD = {"energy_kcal": 480, "protein_g": 6, "carbs_g": 70, "sugar_g": 30, "fat_g": 20, "sat_fat_g": 10, "fiber_g": 1, "sodium_mg": 500}
GOOD = {"energy_kcal": 380, "protein_g": 12, "carbs_g": 60, "sugar_g": 6, "fat_g": 8, "sat_fat_g": 1.5, "fiber_g": 8, "sodium_mg": 150}


def _user(db):
    u = User(email="a@b.c", password_hash="x", consent_version="v1")
    db.add(u)
    db.commit()
    return u


def test_family_of():
    assert off.family_of(["en:snacks", "en:biscuits-and-cakes"]) == "biscuit"
    assert off.family_of(["en:ghee"]) == "ghee"
    assert off.family_of(["en:something-else"]) == "packaged"
    assert off.family_of(None) == "packaged"


def test_alternatives_are_same_family_better_and_safe(db):
    u = _user(db)
    base = _p(db, "8901000000001", "Sweet biscuit", BAD)
    _p(db, "8901000000002", "Oat biscuit", GOOD)
    _p(db, "8901000000003", "Other biscuit", BAD)                       # not better
    _p(db, "8901000000004", "Cereal", GOOD, category="cereal")          # other family
    r = alternatives.for_product(db, u, base)
    assert r["status"] == "ok"
    assert [i["id"] for i in r["items"]] == ["8901000000002"]
    it = r["items"][0]
    assert it["gain"] >= 10 and it["trust"] == "community"
    assert {w["code"] for w in it["why"]} <= {"less_sugar", "less_salt", "less_sat_fat", "more_fibre", "more_protein"} and it["why"]


def test_unknown_family_gives_no_comparison(db):
    u = _user(db)
    base = _p(db, "8901000000011", "Mystery", BAD, category="packaged")
    _p(db, "8901000000012", "Other", GOOD, category="packaged")
    assert alternatives.for_product(db, u, base) == {"status": "unknown_category", "items": []}


def test_product_without_score_gets_none(db):
    u = _user(db)
    base = _p(db, "8901000000021", "Ghee", {"energy_kcal": 900}, category="ghee")
    assert alternatives.for_product(db, u, base)["status"] == "no_score"


def test_fetch_family_adds_only_complete_indian_products(db):
    prods = [
        {"code": "8901000000031", "product_name": "Oat biscuit", "brands": "X", "nutriments": {
            "energy-kcal_100g": 380, "sugars_100g": 6, "sodium_100g": 0.15, "saturated-fat_100g": 1.5, "fat_100g": 8, "proteins_100g": 12, "carbohydrates_100g": 60}},
        {"code": "8901000000032", "product_name": "Partial", "brands": "X", "nutriments": {"energy-kcal_100g": 380}},
    ]
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"products": prods})))
    assert off.fetch_family(db, "biscuit", c) == 1
    assert off.fetch_family(db, "biscuit", c) == 0   # no duplicates
    assert off.fetch_family(db, "nonsense", c) == 0


def test_fetch_failure_adds_nothing(db):
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    assert off.fetch_family(db, "biscuit", c) == 0
