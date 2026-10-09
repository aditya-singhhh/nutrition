from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.db_migrate import ensure_columns
from tests.conftest import FULL_PROFILE


def v1(p):
    return "/api/v1" + p


def test_ensure_columns_adds_to_old_table():
    e = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with e.begin() as c:
        c.execute(text("CREATE TABLE user_profiles (id INTEGER PRIMARY KEY, user_id INTEGER)"))
    assert set(ensure_columns(e)) == {"user_profiles.display_name", "user_profiles.target_weight_kg", "user_profiles.life_stage", "user_profiles.training_opt_in"}
    assert {c["name"] for c in inspect(e).get_columns("user_profiles")} >= {"display_name", "life_stage"}
    assert ensure_columns(e) == []  # idempotent


def test_profile_new_fields_roundtrip(client, auth):
    r = client.put(v1("/users/me/profile"), headers=auth, json={**FULL_PROFILE, "display_name": "  Aditya ",
                   "target_weight_kg": 70, "region": "south_indian"})
    assert r.status_code == 200, r.text
    p = client.get(v1("/users/me"), headers=auth).json()["profile"]
    assert p["display_name"] == "Aditya" and p["target_weight_kg"] == 70 and p["region"] == "south_indian"
    assert p["life_stage"] is None


def test_pregnancy_blocks_targets_and_can_be_cleared(client, auth):
    client.put(v1("/users/me/profile"), headers=auth, json={**FULL_PROFILE, "sex": "female"})
    assert client.get(v1("/users/me/targets"), headers=auth).json()["available"] is True
    client.put(v1("/users/me/profile"), headers=auth, json={"life_stage": "pregnant"})
    t = client.get(v1("/users/me/targets"), headers=auth).json()
    assert t["available"] is False and t["reason"] == "life_stage_review_required"
    client.put(v1("/users/me/profile"), headers=auth, json={"life_stage": "none"})
    assert client.get(v1("/users/me/targets"), headers=auth).json()["available"] is True


def test_bad_values_rejected(client, auth):
    assert client.put(v1("/users/me/profile"), headers=auth, json={"life_stage": "other"}).status_code == 422
    assert client.put(v1("/users/me/profile"), headers=auth, json={"target_weight_kg": 2}).status_code == 422
