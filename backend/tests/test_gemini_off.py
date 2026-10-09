import json

import httpx
import pytest

from app.ai import providers
from app.ai.providers import GeminiOCRProvider, GeminiVisionProvider, ProviderError
from app.models import PackagedProduct
from app.services import openfoodfacts as off


def _fake_post(payload_text):
    def post(url, json=None, headers=None, timeout=None):
        assert headers["x-goog-api-key"] == "k"
        body = {"candidates": [{"content": {"parts": [{"text": payload_text}]}}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))
    return post


def test_gemini_vision_filters_unknown_and_bad_values(monkeypatch):
    out = json.dumps({"items": [
        {"slug": "idli", "confidence": 0.9, "grams_min": 80, "grams_max": 120},
        {"slug": "made-up", "confidence": 0.9, "grams_min": 80, "grams_max": 120},
        {"slug": "idli", "confidence": "x", "grams_min": 1, "grams_max": 2},
        {"slug": "idli", "confidence": 2, "grams_min": 90, "grams_max": 60}]})
    monkeypatch.setattr(providers.httpx, "post", _fake_post(out))
    r = GeminiVisionProvider("k", "m").detect_dishes(b"\xff\xd8\xff", [("idli", "Idli")])
    assert [(c.food_slug, c.confidence, c.portion_g_min, c.portion_g_max) for c in r] == [
        ("idli", 0.9, 80, 120), ("idli", 1.0, 60, 90)]


def test_gemini_vision_bad_json(monkeypatch):
    monkeypatch.setattr(providers.httpx, "post", _fake_post("not json"))
    with pytest.raises(ProviderError):
        GeminiVisionProvider("k", "m").detect_dishes(b"x", [("idli", "Idli")])


def test_gemini_ocr(monkeypatch):
    monkeypatch.setattr(providers.httpx, "post", _fake_post("  Wheat flour, sugar  "))
    assert GeminiOCRProvider("k", "m").extract_text(b"x").text == "Wheat flour, sugar"


def test_off_maps_and_stores(db):
    body = {"status": 1, "product": {"product_name": "Choco Bar", "brands": "Acme,Other", "nova_group": 4,
            "nutriments": {"energy-kcal_100g": 500, "proteins_100g": 5, "salt_100g": 1.25, "sugars_100g": 40},
            "allergens_tags": ["en:milk"], "countries_tags": ["en:india"]}}
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    p = off.lookup_and_store(db, "8901234567890", c)
    assert isinstance(p, PackagedProduct) and p.verified is False and p.source == "open_food_facts"
    assert p.nutrients_per_100g["sodium_mg"] == 500.0 and "fat_g" not in p.nutrients_per_100g
    assert p.brand == "Acme" and p.allergens == ["milk"] and p.country == "IN"


def test_off_keeps_partial_entry_with_ingredients(db):
    body = {"status": 1, "product": {"product_name": "Namkeen", "ingredients_text": "gram flour, oil, salt", "nutriments": {}}}
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body)))
    p = off.lookup_and_store(db, "8901234567893", c)
    assert p is not None and p.nutrients_per_100g == {}


def test_off_tries_code_variants(db):
    seen = []

    def handler(r):
        seen.append(r.url.path)
        hit = r.url.path.endswith("/0123456789012.json")
        return httpx.Response(200, json={"status": 1, "product": {"product_name": "X", "nutriments": {"energy-kcal_100g": 10}}}
                              if hit else {"status": 0})
    assert off.lookup_and_store(db, "123456789012", httpx.Client(transport=httpx.MockTransport(handler))) is not None
    assert len(seen) == 2


def test_off_rejects_incomplete_or_missing(db):
    c = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"status": 0})))
    assert off.lookup_and_store(db, "8901234567891", c) is None
    c2 = httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"status": 1, "product": {"nutriments": {}}})))
    assert off.lookup_and_store(db, "8901234567892", c2) is None


def test_smart_scan_routes(ai_client):
    import base64
    from tests.conftest import register
    auth = register(ai_client)
    img = base64.b64encode(b"\xff\xd8\xff" + b"\x00" * 200).decode()
    r = ai_client.post("/api/v1/scan/smart", json={"image_base64": img}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["kind"] == "food" and r.json()["items"]


def test_smart_scan_rejects_non_image(ai_client):
    import base64
    from tests.conftest import register
    auth = register(ai_client)
    r = ai_client.post("/api/v1/scan/smart", json={"image_base64": base64.b64encode(b"x" * 300).decode()}, headers=auth)
    assert r.status_code == 415


def test_smart_scan_not_configured(client, auth):
    import base64
    img = base64.b64encode(b"\xff\xd8\xff" + b"\x00" * 200).decode()
    assert client.post("/api/v1/scan/smart", json={"image_base64": img}, headers=auth).status_code == 503


def test_product_without_nutrients_is_not_scored():
    from app.domain.compat import UserContext
    from app.services.catalog import evaluate_product
    p = PackagedProduct(barcode="1", brand="B", name="N", category="packaged", nutrients_per_100g={},
                        ingredients_text="gram flour, oil, salt", allergens=[], additives=[], country="IN",
                        source="open_food_facts", confidence="crowd_sourced", verified=False)
    r = evaluate_product(p, UserContext(conditions=[], allergies=[], diet_preference=None, goal=None))
    assert r["quality_score"]["score"] is None
