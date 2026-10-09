from sqlalchemy import select

from app.ai.providers import AIGateway, LLMProvider, LLMResult, ProviderError
from app.models import ModelPrediction, PredictionFeedback
from tests.conftest import FULL_PROFILE, PNG, PW, make_client, register

CHIPS, NOODLES, BISCUIT, OATS, PBUTTER = ("8900000000043", "8900000000029", "8900000000012", "8900000000067",
                                          "8900000000074")


def v1(path):
    return "/api/v1" + path


# ---------------------------------------------------------------- auth & account
def test_register_requires_consent_and_strong_password(client):
    base = {"email": "a@b.com", "password": PW, "consent_health_data": True, "accepted_terms": True}
    assert client.post(v1("/auth/register"), json={**base, "consent_health_data": False}).status_code == 422
    assert client.post(v1("/auth/register"), json={**base, "password": "short"}).status_code == 422


def test_duplicate_login_and_protected_routes(client):
    register(client, "dup@example.com")
    r = client.post(v1("/auth/register"), json={"email": "DUP@example.com", "password": PW,
                                                "consent_health_data": True, "accepted_terms": True})
    assert r.status_code == 409
    assert client.post(v1("/auth/login"), json={"email": "dup@example.com", "password": PW}).status_code == 200
    bad = client.post(v1("/auth/login"), json={"email": "dup@example.com", "password": "wrong-password"})
    nobody = client.post(v1("/auth/login"), json={"email": "nobody@example.com", "password": PW})
    assert bad.status_code == nobody.status_code == 401 and bad.json() == nobody.json()
    assert client.get(v1("/users/me")).status_code == 401
    assert client.get(v1("/users/me"), headers={"Authorization": "Bearer junk"}).status_code == 401


def test_password_not_exposed(client, auth):
    me = client.get(v1("/users/me"), headers=auth).json()
    assert "password" not in str(me).lower()


def test_profile_validation_and_targets(client, auth):
    assert client.get(v1("/users/me/targets"), headers=auth).json()["reason"] == "incomplete_profile"
    bad = client.put(v1("/users/me/profile"), headers=auth, json={"conditions": ["made_up"]})
    assert bad.status_code == 422
    assert client.put(v1("/users/me/profile"), headers=auth, json={"height_cm": 5}).status_code == 422
    r = client.put(v1("/users/me/profile"), headers=auth,
                   json={**FULL_PROFILE, "conditions": ["hypertension", "diabetes"], "allergies": ["peanut"]})
    assert r.status_code == 200 and r.json()["conditions"] == ["diabetes", "hypertension"]
    t = client.get(v1("/users/me/targets"), headers=auth).json()
    assert t["available"] and t["energy_kcal"] == 2633


def test_delete_account_erases_data(client, auth):
    client.put(v1("/users/me/profile"), headers=auth, json=FULL_PROFILE)
    client.post(v1("/meals"), headers=auth, json={"items": [{"food_slug": "roti", "servings": 2}]})
    client.post(v1("/chat"), headers=auth, json={"message": "hello"})
    assert client.delete(v1("/users/me"), headers=auth).status_code == 204
    assert client.get(v1("/users/me"), headers=auth).status_code == 401
    with client.app.state.session_factory() as db:
        assert db.scalar(select(ModelPrediction.id)) is None


# ---------------------------------------------------------------- products / foods
def test_product_lookup_and_errors(client, auth):
    r = client.get(v1(f"/products/{BISCUIT}"), headers=auth)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Demo Glucose Biscuits"
    assert body["data_quality"]["verified"] is False and "warning" in body["data_quality"]
    assert {a["ins"] for a in body["ingredients"]["additives"]} >= {"322", "500"}
    assert {"milk", "gluten", "soy"} <= set(body["ingredients"]["allergens"])
    assert body["quality_score"]["score"] is not None
    assert client.get(v1("/products/8900000000013"), headers=auth).status_code == 422
    assert client.get(v1("/products/5449000000996"), headers=auth).status_code == 404  # valid code, unknown product
    r404 = client.post(v1("/scan/barcode"), headers=auth, json={"barcode": "5449000000996"})
    assert r404.status_code == 404 and r404.json()["detail"]["code"] == "product_not_found"


def test_scan_barcode_personalised(client, auth):
    client.put(v1("/users/me/profile"), headers=auth,
               json={"conditions": ["hypertension"], "allergies": ["peanut"]})
    noodles = client.post(v1("/scan/barcode"), headers=auth, json={"barcode": NOODLES}).json()
    assert noodles["personal_compatibility"]["overall"] <= 15
    pb = client.post(v1("/scan/barcode"), headers=auth, json={"barcode": PBUTTER}).json()
    assert pb["personal_compatibility"]["blocked"] and pb["personal_compatibility"]["overall"] == 0
    chips = client.post(v1("/scan/barcode"), headers=auth, json={"barcode": CHIPS}).json()
    assert any(a["type"] == "allergen_trace" for a in chips["personal_compatibility"]["alerts"]) is False  # milk, not peanut


def test_quality_ordering_in_catalog(client, auth):
    s = {c: client.get(v1(f"/products/{c}"), headers=auth).json()["quality_score"]["score"]
         for c in (OATS, CHIPS, NOODLES)}
    assert s[OATS] > s[CHIPS] and s[OATS] > s[NOODLES]


def test_food_search_and_analyze_scales_by_grams(client, auth):
    items = client.get(v1("/foods"), headers=auth, params={"q": "dosa"}).json()["items"]
    assert {i["slug"] for i in items} >= {"plain-dosa", "masala-dosa"}
    assert client.get(v1(f"/foods/{items[0]['id']}"), headers=auth).status_code == 200
    r = client.post(v1("/food/analyze"), headers=auth, json={"food_slug": "roti", "grams": 80}).json()
    assert r["nutrition_for_portion"]["energy_kcal"] == 232.0 and r["portion"]["grams"] == 80
    two = client.post(v1("/food/analyze"), headers=auth, json={"food_slug": "roti", "servings": 2}).json()
    assert two["portion"]["grams"] == 80
    assert client.post(v1("/food/analyze"), headers=auth, json={"food_slug": "roti", "barcode": OATS}).status_code == 422
    assert client.post(v1("/food/analyze"), headers=auth, json={"food_slug": "nope"}).status_code == 404


def test_label_text_scan(client, auth):
    client.put(v1("/users/me/profile"), headers=auth, json={"allergies": ["milk"]})
    r = client.post(v1("/scan/label-text"), headers=auth, json={
        "text": "Ingredients: Sugar, Milk solids, Colour (INS 102), Preservative (INS 211)"}).json()
    assert r["score_is_partial"] and r["quality_score"]["score"] is None  # ingredients alone never earn a score
    assert r["personal_compatibility"]["blocked"]
    assert {a["ins"] for a in r["ingredients"]["additives"]} == {"102", "211"}


# ---------------------------------------------------------------- meals & dashboard
def test_meal_logging_and_daily_dashboard(client, auth):
    client.put(v1("/users/me/profile"), headers=auth, json=FULL_PROFILE)
    r = client.post(v1("/meals"), headers=auth, json={
        "meal_type": "lunch", "items": [{"food_slug": "roti", "servings": 2}, {"food_slug": "dal-tadka", "servings": 1}]})
    assert r.status_code == 201
    assert r.json()["totals"]["energy_kcal"] == 397.0  # 232 + 165
    today = client.get(v1("/nutrition/today"), headers=auth).json()
    assert today["totals"]["energy_kcal"] == 397.0 and len(today["meals"]) == 1
    assert today["remaining"]["energy_kcal"] == 2633 - 397
    assert today["targets"]["available"] and today["limits_exceeded"] == []
    assert client.get(v1("/nutrition/today"), headers=auth, params={"date": "2020-01-01"}).json()["meals"] == []


def test_meal_validation_and_ownership(client, auth):
    other = register(client, "other@example.com")
    mid = client.post(v1("/meals"), headers=auth, json={"items": [{"food_slug": "idli", "grams": 80}]}).json()["id"]
    assert client.delete(v1(f"/meals/{mid}"), headers=other).status_code == 404  # not yours
    assert client.post(v1("/meals"), headers=auth, json={"items": []}).status_code == 422
    assert client.post(v1("/meals"), headers=auth, json={"items": [{"food_slug": "idli"}]}).status_code == 422
    assert client.post(v1("/meals"), headers=auth, json={"items": [{"food_slug": "idli", "grams": -5}]}).status_code == 422
    assert client.post(v1("/meals"), headers=auth, json={"items": [{"food_slug": "zzz", "grams": 5}]}).status_code == 404
    assert client.delete(v1(f"/meals/{mid}"), headers=auth).status_code == 204


def test_dashboard_flags_sodium_over_limit(client, auth):
    client.put(v1("/users/me/profile"), headers=auth, json=FULL_PROFILE)
    client.post(v1("/meals"), headers=auth, json={"items": [{"barcode": NOODLES, "servings": 2}]})
    today = client.get(v1("/nutrition/today"), headers=auth).json()
    assert [e["nutrient"] for e in today["limits_exceeded"]] == ["sodium"]


# ---------------------------------------------------------------- photo / OCR / feedback flywheel
def test_food_photo_not_configured_returns_503(client, auth):
    r = client.post(v1("/scan/food-photo"), headers=auth, files={"image": ("a.png", PNG, "image/png")})
    assert r.status_code == 503


def test_food_photo_flow_with_correction(ai_client):
    c = ai_client
    h = register(c)
    assert c.post(v1("/scan/food-photo"), headers=h, files={"image": ("a.txt", b"not an image", "image/png")}).status_code == 415
    r = c.post(v1("/scan/food-photo"), headers=h, files={"image": ("a.png", PNG, "image/png")}).json()
    by_slug = {i["food"]["slug"]: i for i in r["items"]}
    assert set(by_slug) == {"masala-dosa", "sambar"} and r["unrecognised"] == ["made-up-dish"]
    dosa = by_slug["masala-dosa"]
    assert dosa["portion_g_range"] == [120, 180] and not dosa["needs_confirmation"]
    assert dosa["nutrition_range"]["min"]["energy_kcal"] < dosa["nutrition_range"]["max"]["energy_kcal"]
    assert by_slug["sambar"]["needs_confirmation"]
    pid = r["prediction_id"]
    fb = c.post(v1(f"/predictions/{pid}/feedback"), headers=h, json={
        "prediction_correct": False, "corrected_items": [{"food_slug": "plain-dosa", "grams": 100}]})
    assert fb.status_code == 201
    assert c.post(v1(f"/predictions/{pid}/feedback"), headers=h,
                  json={"prediction_correct": False, "corrected_items": [{"food_slug": "nope"}]}).status_code == 422
    other = register(c, "o@example.com")
    assert c.post(v1(f"/predictions/{pid}/feedback"), headers=other, json={"prediction_correct": True}).status_code == 404
    with c.app.state.session_factory() as db:
        p = db.scalar(select(ModelPrediction).where(ModelPrediction.id == pid))
        assert p.kind == "food_photo" and p.model_name == "mock" and p.model_version and p.input_digest
        assert db.scalar(select(PredictionFeedback)).correction["corrected_items"][0]["food_slug"] == "plain-dosa"
    m = c.post(v1("/meals"), headers=h, json={"source": "photo", "items": [
        {"food_slug": "plain-dosa", "grams": 100, "prediction_id": pid}]})
    assert m.status_code == 201


def test_label_ocr_scan(ai_client):
    h = register(ai_client)
    r = ai_client.post(v1("/scan/label"), headers=h, files={"image": ("l.png", PNG, "image/png")}).json()
    assert {a["ins"] for a in r["ingredients"]["additives"]} == {"322", "102"}
    assert r["ingredients"]["may_contain"] == ["peanut"] and r["extracted_text"] and r["prediction_id"]


# ---------------------------------------------------------------- recommendations
def test_recommendations_respect_constraints(client, auth):
    client.put(v1("/users/me/profile"), headers=auth, json={**FULL_PROFILE, "allergies": ["milk"],
                                                            "conditions": ["diabetes"]})
    rec = client.get(v1("/recommendations"), headers=auth).json()
    assert rec["items"], "expected at least one suggestion"
    foods = {i["food"]["slug"] for i in rec["items"]}
    with client.app.state.session_factory() as db:
        from app.models import FoodItem
        for f in db.scalars(select(FoodItem).where(FoodItem.slug.in_(foods))):
            assert "milk" not in f.allergens and f.diet_type in ("vegan", "vegetarian")
    assert all(i["personal_compatibility"] is None or i["personal_compatibility"] >= 50 for i in rec["items"])
    assert all(i["reasons"] for i in rec["items"])


# ---------------------------------------------------------------- chat
def chat(client, h, msg):
    r = client.post(v1("/chat"), headers=h, json={"message": msg})
    assert r.status_code == 200, r.text
    return r.json()


def test_chat_product_question_uses_tools_and_personalises(client, auth):
    client.put(v1("/users/me/profile"), headers=auth, json={**FULL_PROFILE, "conditions": ["diabetes"]})
    r = chat(client, auth, f"Can I eat this biscuit? barcode {BISCUIT}")
    assert r["intent"] == "evaluate_product" and "evaluate_food_for_user" in r["tools_used"]
    assert "Demo Glucose Biscuits" in r["reply"] and "not medical advice" in r["reply"]
    assert "unverified" in r["reply"].lower() or "not verified" in r["reply"].lower()


def test_chat_dish_today_and_recommend(client, auth):
    client.put(v1("/users/me/profile"), headers=auth, json=FULL_PROFILE)
    assert chat(client, auth, "Is masala dosa ok for me?")["intent"] == "evaluate_food"
    assert chat(client, auth, "what should I eat for a snack?")["intent"] == "recommend"
    client.post(v1("/meals"), headers=auth, json={"items": [{"food_slug": "idli", "servings": 3}]})
    t = chat(client, auth, "how much have I eaten so far today?")
    assert t["intent"] == "today_summary" and "3 meals" not in t["reply"] and "1 meal logged" in t["reply"]


def test_chat_safety_short_circuits(client, auth):
    for msg, level in [("I have severe chest pain", "emergency"), ("how much insulin should I take?", "medication"),
                       ("I want to lose 8 kg in a week", "dangerous_diet")]:
        r = chat(client, auth, msg)
        assert r["safety_level"] == level and r["tools_used"] == []
    with client.app.state.session_factory() as db:
        kinds = {p.model_name for p in db.scalars(select(ModelPrediction))}
        assert kinds == {"static_safety"}  # the LLM was never consulted


def test_chat_does_not_improvise_outside_verified_scope(client, auth):
    r = chat(client, auth, "Which supplement cures my thyroid problem?")
    assert r["intent"] == "unsupported" and "doctor or dietitian" in r["reply"]


def test_chat_unknown_product_and_bad_barcode(client, auth):
    assert chat(client, auth, "scan 5449000000996 please")["intent"] == "product_not_found"
    assert chat(client, auth, "is 1234567890123 ok?")["intent"] == "barcode_invalid"


class _Fixed:
    name = "fixed"

    def __init__(self, text=None, error=None):
        self.text, self.error = text, error

    def generate(self, req):
        if self.error:
            raise self.error
        return LLMResult(self.text if self.text is not None else req.draft, "fixed-model", "v9")


def _llm_client(llm: LLMProvider):
    c = make_client(AIGateway(llm=llm))
    return c, register(c)


def test_llm_hallucinated_numbers_are_rejected_and_draft_used():
    c, h = _llm_client(_Fixed("Masala dosa has 900 kcal and will cure diabetes."))
    r = chat(c, h, "masala dosa?")
    assert "900" not in r["reply"] and "285" in r["reply"]


def test_llm_diagnosis_language_is_rejected():
    c, h = _llm_client(_Fixed("You probably have diabetes, so skip the dosa."))
    assert "probably have" not in chat(c, h, "masala dosa?")["reply"]


def test_llm_failure_falls_back_to_deterministic_draft():
    c, h = _llm_client(_Fixed(error=ProviderError("boom")))
    assert "Masala Dosa" in chat(c, h, "masala dosa?")["reply"]


def test_llm_valid_rewrite_is_used_and_traced():
    c, h = _llm_client(_Fixed("Good choice! Masala Dosa is around 285 kcal for one."))
    r = chat(c, h, "masala dosa?")
    assert r["reply"].startswith("Good choice")
    with c.app.state.session_factory() as db:
        p = db.get(ModelPrediction, r["prediction_id"])
        assert p.model_name == "fixed-model" and p.model_version == "v9" and p.prompt_version == "chat-v1"
        assert p.output["llm_used"] is True and p.input_digest and len(p.input_digest) == 64


def test_chat_input_limits(client, auth):
    assert client.post(v1("/chat"), headers=auth, json={"message": ""}).status_code == 422
    assert client.post(v1("/chat"), headers=auth, json={"message": "x" * 1001}).status_code == 422
