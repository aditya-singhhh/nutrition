import base64
import json

import httpx
import pytest

from app.ai import providers
from app.ai.providers import AIGateway, GeminiVisionProvider
from app.domain.label import parse_label_nutrition
from app.models import PackagedProduct, ScanRecord
from tests.conftest import FULL_PROFILE, make_client, register

JPEG = base64.b64encode(b"\xff\xd8\xff" + b"\x00" * 300).decode()

GHEE = {"serving_g": 5, "per_100g": {"energy_kcal": 900, "protein_g": 0, "carbs_g": 0, "sugar_g": 0, "fat_g": 100,
                                       "sat_fat_g": 62, "fiber_g": 0, "sodium_mg": 0},
        "per_serving": {"energy_kcal": 45, "fat_g": 5, "sat_fat_g": 3.1}}


@pytest.fixture(autouse=True)
def _no_discovery(monkeypatch):
    monkeypatch.setattr(providers.httpx, "get", lambda *a, **k: httpx.Response(403, json={}, request=httpx.Request("GET", "x")))


def _client(monkeypatch, payload):
    def post(url, json=None, headers=None, timeout=None):
        body = {"candidates": [{"content": {"parts": [{"text": __import__("json").dumps(payload)}]}}]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))
    monkeypatch.setattr(providers.httpx, "post", post)
    c = make_client(AIGateway(vision=GeminiVisionProvider("k", "m")))
    return c, register(c)


# ---------------------------------------------------------------- pure parsing / validation
def test_per_100g_table_used_as_is():
    r = parse_label_nutrition(GHEE)
    assert r.basis == "per_100g" and r.per_100g["sat_fat_g"] == 62 and r.per_serving["energy_kcal"] == 45


def test_per_serving_only_is_scaled_to_100g():
    r = parse_label_nutrition({"serving_g": 25, "per_serving": {"energy_kcal": 112, "protein_g": 1.5, "carbs_g": 19, "fat_g": 3,
                                                                  "sugar_g": 6, "sat_fat_g": 1.5, "sodium_mg": 80}})
    assert r.basis == "scaled_from_serving" and r.per_100g["energy_kcal"] == 448 and r.per_100g["sodium_mg"] == 320
    assert any("scaled" in w for w in r.warnings)


def test_per_serving_without_serving_size_is_refused():
    r = parse_label_nutrition({"per_serving": {"energy_kcal": 112, "protein_g": 1.5, "carbs_g": 19, "fat_g": 3}})
    assert r.basis == "none" and r.per_100g == {}


def test_salt_converted_to_sodium():
    r = parse_label_nutrition({"per_100g": {"energy_kcal": 100, "protein_g": 5, "carbs_g": 10, "fat_g": 3, "salt_g": 1.25}})
    assert r.per_100g["sodium_mg"] == 500.0


def test_nonsense_numbers_are_rejected():
    assert parse_label_nutrition({"per_100g": {"energy_kcal": 100, "protein_g": 80, "carbs_g": 60, "fat_g": 40}}).basis == "none"
    r = parse_label_nutrition({"per_100g": {"energy_kcal": 400, "protein_g": 5, "carbs_g": 50, "fat_g": 5, "sat_fat_g": 9, "sugar_g": 60}})
    assert "sat_fat_g" not in r.per_100g and "sugar_g" not in r.per_100g and len(r.warnings) >= 2


def test_energy_mismatch_warns_but_keeps():
    r = parse_label_nutrition({"per_100g": {"energy_kcal": 900, "protein_g": 5, "carbs_g": 50, "fat_g": 5}})
    assert r.basis == "per_100g" and any("doesn't match" in w for w in r.warnings)


# ---------------------------------------------------------------- endpoint
def test_ghee_label_scored_from_table_not_100(monkeypatch):
    c, auth = _client(monkeypatch, {"kind": "label", "label_text": "Cow milk fat", "product_name": "Cow Ghee", "nutrition": GHEE})
    r = c.post("/api/v1/scan/smart", json={"image_base64": JPEG}, headers=auth)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["kind"] == "label" and j["quality_score"]["score"] is not None and j["quality_score"]["score"] < 60
    assert j["nutrition_per_100g"]["sat_fat_g"] == 62 and j["nutrition_for_portion"]["fat_g"] == 5


def test_ingredients_only_label_gets_no_score(monkeypatch):
    c, auth = _client(monkeypatch, {"kind": "label", "label_text": "Cow milk fat", "nutrition": None})
    j = c.post("/api/v1/scan/smart", json={"image_base64": JPEG}, headers=auth).json()
    assert j["quality_score"]["score"] is None


def test_unknown_barcode_then_label_creates_product_for_next_time(monkeypatch):
    c, auth = _client(monkeypatch, {"kind": "label", "label_text": "Cow milk fat", "product_name": "Cow Ghee", "nutrition": GHEE})
    code = "8901234567890"
    assert c.post("/api/v1/scan/barcode", json={"barcode": code}, headers=auth).status_code == 404
    j = c.post("/api/v1/scan/smart", json={"image_base64": JPEG, "barcode": code}, headers=auth).json()
    assert j["kind"] == "product" and j["created_from_label"] and j["barcode"] == code
    again = c.post("/api/v1/scan/barcode", json={"barcode": code}, headers=auth)
    assert again.status_code == 200 and again.json()["data_quality"]["verified"] is False


# ---------------------------------------------------------------- saving scans
def _rows(c):
    with c.app.state.session_factory() as db:
        return db.query(ScanRecord).all()


def test_scans_are_logged_without_photo_by_default(monkeypatch):
    c, auth = _client(monkeypatch, {"kind": "label", "label_text": "x", "nutrition": GHEE})
    c.post("/api/v1/scan/barcode", json={"barcode": "8901234567890"}, headers=auth)
    c.post("/api/v1/scan/smart", json={"image_base64": JPEG}, headers=auth)
    rows = _rows(c)
    assert {r.kind for r in rows} == {"barcode", "label"}
    assert all(r.image is None for r in rows) and any(r.image_sha256 for r in rows)


def test_photo_kept_only_after_opt_in_and_deleted_with_account(monkeypatch):
    c, auth = _client(monkeypatch, {"kind": "label", "label_text": "x", "nutrition": GHEE})
    assert c.put("/api/v1/users/me/profile", headers=auth, json={"training_opt_in": True}).json()["profile"]["training_opt_in"] is True
    c.post("/api/v1/scan/smart", json={"image_base64": JPEG}, headers=auth)
    assert [r.image is not None for r in _rows(c)] == [True]
    assert c.delete("/api/v1/users/me", headers=auth).status_code == 204
    assert _rows(c) == []
