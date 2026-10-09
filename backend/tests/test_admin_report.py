from app.core.config import get_settings
from app.models import PackagedProduct
from tests.conftest import FULL_PROFILE, make_client, register

V = "/api/v1"


def _add_product(c, code="8901000000099"):
    with c.app.state.session_factory() as db:
        db.add(PackagedProduct(barcode=code, brand="B", name="Scanned biscuit", category="biscuit", serving_g=30,
                               nutrients_per_100g={"energy_kcal": 480, "sugar_g": 20}, ingredients_text="wheat", allergens=[], additives=[],
                               nova=3, country="IN", source="user_label_scan", confidence="ai_read_label", verified=False, confirmations=2))
        db.commit()


def test_admin_only_queue_and_review(monkeypatch):
    c = make_client()
    h = register(c)
    _add_product(c)
    assert c.get(f"{V}/admin/products/queue", headers=h).status_code == 403
    assert c.get(f"{V}/users/me", headers=h).json()["is_admin"] is False
    monkeypatch.setattr(get_settings(), "admin_emails", "user@example.com")
    assert c.get(f"{V}/users/me", headers=h).json()["is_admin"] is True
    q = c.get(f"{V}/admin/products/queue", headers=h).json()
    mine = [i for i in q["items"] if i["barcode"] == "8901000000099"]
    assert mine and mine[0]["trust"] == "community_confirmed" and q["items"][0]["barcode"] == "8901000000099"  # confirmed ones first
    r = c.post(f"{V}/admin/products/8901000000099/review", headers=h, json={"verified": True}).json()
    assert r["verified"] is True and r["trust"] == "verified"
    assert all(i["barcode"] != "8901000000099" for i in c.get(f"{V}/admin/products/queue", headers=h).json()["items"])
    assert c.post(f"{V}/admin/products/000/review", headers=h, json={}).status_code == 404


def test_report_summarises_logged_days_and_handles_empty():
    c = make_client()
    h = register(c)
    c.put(f"{V}/users/me/profile", headers=h, json={**FULL_PROFILE, "conditions": ["diabetes"]})
    empty = c.get(f"{V}/users/me/report?days=7", headers=h).json()
    assert empty["days_logged"] == 0 and "No meals were logged" in empty["text"]
    c.post(f"{V}/meals", headers=h, json={"items": [{"food_slug": "roti", "servings": 2}, {"food_slug": "idli", "grams": 80}]})
    r = c.get(f"{V}/users/me/report?days=7", headers=h).json()
    assert r["days_logged"] == 1 and r["meals"] == 1 and r["average_per_logged_day"]["energy_kcal"] > 0
    assert "diabetes" in r["text"] and "not medical advice" in r["text"] and r["top_carb_items"]
    assert c.get(f"{V}/users/me/report?days=999", headers=h).json()["days"] == 30
