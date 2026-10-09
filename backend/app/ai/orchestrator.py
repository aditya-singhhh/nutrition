"""AI Orchestrator for the basic nutrition chatbot.

Flow (never USER -> LLM -> advice):
  safety screen -> intent routing -> deterministic tools -> deterministic draft from verified facts
  -> LLM rewrites tone only (optional) -> output validation -> user.

If the LLM fails or its output fails validation, the deterministic draft is returned instead.
"""
from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.ai.providers import AIGateway, LLMRequest, ProviderError
from app.domain.barcode import InvalidBarcode, normalize_barcode
from sqlalchemy import select

from app.models import ChatMessage, ChatSession, ModelPrediction, User
from app.safety.engine import screen_user_message, validate_reply
from app.services import catalog
from app.services.catalog import user_context
from app.services.dashboard import targets_for, today_summary
from app.services.recommendations import recommend

logger = logging.getLogger(__name__)

PROMPT_VERSION = "chat-v1"
SYSTEM_PROMPT = (
    "You are a friendly nutrition and wellness companion for Indian users. You are not a doctor and must not "
    "diagnose, change medication, or give emergency advice. Use only the verified facts you are given."
)
DISCLAIMER = "This is nutrition guidance, not medical advice."
METRIC_LABEL = {"sugar_g": "sugar", "carbs_g": "carbohydrate", "fiber_g": "fibre", "sodium_mg": "sodium",
                "sat_fat_g": "saturated fat", "energy_kcal": "energy density", "protein_g": "protein"}

BARCODE_RE = re.compile(r"\b\d{8,13}\b")
RECOMMEND_RE = re.compile(r"what (should|can) i (eat|have)|recommend|suggest|ideas for (a )?(meal|snack)|"
                          r"something (healthy|high[- ]protein)|i'?m hungry|need more protein", re.IGNORECASE)
TODAY_RE = re.compile(r"calories (left|remaining)|what i'?ve eaten|eaten so far|how much have i eaten|"
                      r"my (intake|nutrition) (today|so far)|today'?s (nutrition|summary|intake)|remaining today",
                      re.IGNORECASE)


@dataclass
class Turn:
    reply: str
    intent: str
    tools_used: list[str] = field(default_factory=list)
    safety_level: str = "ok"
    validation: dict = field(default_factory=dict)
    llm_used: bool = False
    prediction_id: int | None = None
    session_id: int | None = None


def _fmt(n: dict, key: str, unit: str) -> str | None:
    v = n.get(key)
    return None if v is None else f"{v:g} {unit}"


def _draft_evaluation(ev: dict) -> str:
    n, port = ev["nutrition_for_portion"], ev["portion"]
    bits = [b for b in (_fmt(n, "energy_kcal", "kcal"), _fmt(n, "protein_g", "g protein"),
                        _fmt(n, "carbs_g", "g carbohydrate"), _fmt(n, "fat_g", "g fat")) if b]
    parts = [f"{ev['name']} ({port['label']}, about {port['grams']:g} g): " + ", ".join(bits) + "."]
    q = ev["quality_score"]
    if q["score"] is not None:
        parts.append(f"General quality score: {q['score']}/100 ({q['band']}). {q['summary']}")
        if q["confidence"] == "low":
            parts.append("Some data is missing, so this score has low confidence.")
    c = ev["personal_compatibility"]
    for a in c["alerts"]:
        parts.append(a["message"])
    if not c["blocked"] and c["overall"] is not None:
        unfav = [d for cond in c["conditions"] for d in cond["details"] if d["verdict"] == "unfavourable"]
        sentence = f"For your health profile, compatibility is {c['overall']}/100 ({c['label']})."
        if unfav:
            d = unfav[0]
            sentence += (f" The main concern is {METRIC_LABEL.get(d['metric'], d['metric'])} "
                         f"({d['value']:g} {d['unit']}): {d['why_it_matters']}.")
        parts.append(sentence)
    elif c["overall"] is None and not c["blocked"]:
        parts.append(c["notes"][0])
    parts.extend(n for n in c["notes"] if n.startswith("No nutrition rules yet"))
    concern = [a for a in ev.get("ingredients", {}).get("additives", [])
               if a["category"] in ("high_concern", "context_dependent", "quantity_dependent")][:3]
    if concern:
        parts.append("Additives worth knowing about: " + "; ".join(
            f"INS {a['ins']} {a['name']} ({a['category'].replace('_', ' ')})" for a in concern) + ".")
    if "warning" in ev["data_quality"]:
        parts.append(ev["data_quality"]["warning"])
    parts.append(DISCLAIMER)
    return " ".join(parts)


def _draft_today(s: dict) -> str:
    t, tg, rem = s["totals"], s["targets"], s["remaining"]
    n_meals = len(s["meals"])
    if n_meals == 0:
        base = "You haven't logged any meals today yet."
    else:
        base = (f"So far today ({n_meals} meal{'s' if n_meals != 1 else ''} logged): {t['energy_kcal']:g} kcal, "
                f"{t['protein_g']:g} g protein, {t['carbs_g']:g} g carbohydrate, {t['fat_g']:g} g fat, "
                f"{t['fiber_g']:g} g fibre.")
    parts = [base]
    if tg.get("available") and rem:
        parts.append(f"Your daily target is about {tg['energy_kcal']:g} kcal and {tg['protein_g']:g} g protein, "
                     f"so roughly {rem['energy_kcal']:g} kcal and {rem['protein_g']:g} g protein remain.")
        for e in s["limits_exceeded"]:
            parts.append(f"You're above the suggested {e['nutrient']} limit ({e['intake']:g} vs {e['limit']:g}).")
    else:
        parts.append("Complete your profile (age, sex, height, weight, activity) to get personalised daily targets.")
    parts.append(DISCLAIMER)
    return " ".join(parts)


def _draft_recs(r: dict) -> str:
    if not r["items"]:
        return ("I couldn't find a suitable suggestion that fits your profile and today's remaining budget. "
                "A dietitian can help build a plan around your needs. " + DISCLAIMER)
    lines = []
    for i in r["items"][:3]:
        n = i["nutrition_for_portion"]
        lines.append(f"{i['food']['name']} ({i['portion']['label']}): {n['energy_kcal']:g} kcal, "
                     f"{n['protein_g']:g} g protein - {i['reasons'][0]}")
    return "Based on today's intake, you could try: " + "; ".join(lines) + ". " + DISCLAIMER


def personal_facts(db: Session, user: User) -> dict:
    """What the assistant may know about this person. No name, email or ids: this goes to an external model."""
    p = user.profile
    facts: dict = {
        "conditions": [c.condition for c in user.conditions], "allergies": [a.allergen for a in user.allergies],
        "diet_preference": p.diet_preference if p else None, "goal": p.goal if p else None,
        "age": p.age if p else None, "sex": p.sex if p else None, "life_stage": getattr(p, "life_stage", None) if p else None,
    }
    t = targets_for(user)
    if t.get("available"):
        facts["daily_targets"] = {k: round(t[k]) for k in ("energy_kcal", "protein_g", "fiber_g", "sugar_g_max", "sat_fat_g_max", "sodium_mg_max") if k in t}
    try:
        s = today_summary(db, user)
        facts["eaten_today"] = {k: round(v) for k, v in s["totals"].items() if k in ("energy_kcal", "protein_g", "fiber_g", "sugar_g", "sodium_mg")}
        facts["meals_logged_today"] = len(s["meals"])
        if s.get("remaining"):
            facts["remaining_today"] = {k: round(v) for k, v in s["remaining"].items() if k in ("energy_kcal", "protein_g", "fiber_g")}
    except Exception:  # never let a summary problem break chat
        logger.exception("could not build today's facts")
    return {k: v for k, v in facts.items() if v not in (None, [], {})}


def _draft_fallback(facts: dict | None = None) -> str:
    if facts:
        bits = []
        if facts.get("goal"):
            bits.append(f"your goal is to {facts['goal']} weight")
        if facts.get("conditions"):
            bits.append("you manage " + ", ".join(c.replace("_", " ") for c in facts["conditions"]))
        if facts.get("diet_preference"):
            bits.append(f"you eat {facts['diet_preference'].replace('_', ' ')}")
        if bits:
            return ("I couldn't reach my answering service just now, so I won't guess. What I know about you: " + "; ".join(bits) +
                    ". Try again in a moment, or ask about a specific dish, a barcode, today's intake, or what to eat next. " + DISCLAIMER)
    return ("I can check a packaged food (send its barcode), look up a dish from our Indian food list, summarise "
            "what you've eaten today, or suggest what to eat next. I don't have verified information to answer "
            "that one, and I'd rather not guess - for medical questions please ask your doctor or dietitian.")


class ChatOrchestrator:
    def __init__(self, gateway: AIGateway):
        self.gateway = gateway

    # ---- tools (deterministic; each returns verified facts) --------------------------------
    def _route(self, db: Session, user: User, message: str) -> tuple[str, list[str], dict, str]:
        """returns (intent, tools_used, facts, draft)"""
        ctx = user_context(user)
        m = BARCODE_RE.search(message)
        if m:
            try:
                code = normalize_barcode(m.group(0))
            except InvalidBarcode:
                return ("barcode_invalid", [], {}, "That barcode doesn't look valid (check the digits and try again).")
            prod = catalog.get_product(db, code)
            if prod is None:
                return ("product_not_found", ["get_product"], {},
                        "I don't have that product yet. You can scan its ingredient label, and I'll analyse it.")
            ev = catalog.evaluate_product(prod, ctx)
            return "evaluate_product", ["get_product", "get_user_profile", "evaluate_food_for_user"], ev, _draft_evaluation(ev)
        if RECOMMEND_RE.search(message):
            r = recommend(db, user)
            return "recommend", ["get_today_nutrition", "recommend_foods"], r, _draft_recs(r)
        if TODAY_RE.search(message):
            s = today_summary(db, user)
            return "today_summary", ["get_today_nutrition"], s, _draft_today(s)
        prod = catalog.find_product_in_text(db, message)
        if prod:
            ev = catalog.evaluate_product(prod, ctx)
            return "evaluate_product", ["search_products", "get_user_profile", "evaluate_food_for_user"], ev, _draft_evaluation(ev)
        food = catalog.find_food_in_text(db, message)
        if food:
            ev = catalog.evaluate_food(food, ctx)
            return "evaluate_food", ["search_food_database", "get_user_profile", "evaluate_food_for_user"], ev, _draft_evaluation(ev)
        return "advice", ["get_user_profile", "get_today_nutrition"], personal_facts(db, user), _draft_fallback(personal_facts(db, user))

    # ---- main entry -----------------------------------------------------------------------
    def handle(self, db: Session, user: User, message: str, session_id: int | None = None) -> Turn:
        session = db.get(ChatSession, session_id) if session_id else None
        if session is None or session.user_id != user.id:
            session = ChatSession(user_id=user.id)
            db.add(session)
            db.flush()
        digest = hashlib.sha256(message.encode()).hexdigest()

        safety = screen_user_message(message)
        if safety.blocks_llm:
            turn = Turn(reply=safety.message or "", intent=f"safety:{safety.category}", safety_level=safety.level)
            model_name, model_version = "static_safety", "1"
        else:
            intent, tools, facts, draft = self._route(db, user, message)
            turn = Turn(reply=draft, intent=intent, tools_used=tools)
            model_name, model_version = "deterministic", "1"
            if intent in ("evaluate_product", "evaluate_food", "recommend", "today_summary", "advice"):
                try:
                    history = tuple((m.role, m.content) for m in reversed(list(db.scalars(
                        select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.id.desc()).limit(6)))))
                    res = self.gateway.llm.generate(LLMRequest(SYSTEM_PROMPT, message, facts, draft, PROMPT_VERSION,
                                                               mode="advise" if intent == "advice" else "rewrite", history=history))
                    ok, problems = validate_reply(res.text, facts)
                    turn.validation = {"passed": ok, "problems": problems}
                    if ok:
                        turn.reply, turn.llm_used = res.text, res.model != "mock"
                        model_name, model_version = res.model, res.version
                    else:
                        logger.warning("LLM reply rejected by validator: %s", problems)
                except ProviderError as e:
                    logger.warning("LLM provider unavailable, using deterministic draft: %s", e)
                    turn.validation = {"passed": None, "problems": ["llm_unavailable"]}

        pred = ModelPrediction(
            user_id=user.id, kind="chat", model_name=model_name, model_version=model_version,
            prompt_version=PROMPT_VERSION, confidence=None, input_type="text", input_digest=digest,
            output={"intent": turn.intent, "tools_used": turn.tools_used, "safety_level": turn.safety_level,
                    "validation": turn.validation, "llm_used": turn.llm_used})
        db.add(pred)
        db.flush()
        db.add(ChatMessage(session_id=session.id, role="user", content=message))
        db.add(ChatMessage(session_id=session.id, role="assistant", content=turn.reply,
                           safety_level=turn.safety_level, prediction_id=pred.id))
        db.commit()
        turn.prediction_id, turn.session_id = pred.id, session.id
        return turn
