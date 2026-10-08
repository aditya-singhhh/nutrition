"""Safety engine: screens user input before any LLM is involved, and validates replies before they are shown.

Non-OK input results are answered with static, reviewed text - the LLM is never asked to improvise on
emergencies, self-harm, eating disorders, dangerous dieting or medication dosing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

EMERGENCY_NUMBER_IN = "112"
TELE_MANAS_IN = "14416"


@dataclass(frozen=True)
class SafetyResult:
    level: str  # ok | emergency | crisis | eating_disorder | dangerous_diet | medication
    category: str | None = None
    message: str | None = None

    @property
    def blocks_llm(self) -> bool:
        return self.level != "ok"


_RX = re.IGNORECASE
EMERGENCY = [re.compile(p, _RX) for p in [
    r"chest (pain|tightness|pressure)", r"(can'?t|cannot|unable to) breathe", r"(difficulty|trouble) breathing",
    r"shortness of breath", r"anaphyla", r"swelling (of|in) (my )?(face|lips|tongue|throat)",
    r"(my )?(face|lips|tongue|throat) (is |are )?swell", r"allergic reaction", r"(passed out|fainted|unconscious)",
    r"seizure", r"stroke", r"vomiting blood|blood in (my )?(vomit|stool)", r"hypoglyc", r"(sugar|glucose) (is |has )?(very |too )?low",
    r"severe (abdominal|stomach) pain",
]]
CRISIS = [re.compile(p, _RX) for p in [
    r"kill myself", r"suicid", r"end my life", r"want to die", r"self[- ]?harm", r"hurt myself",
]]
EATING_DISORDER = [re.compile(p, _RX) for p in [
    r"anorexi", r"bulimi", r"\bpurg(e|ing)\b", r"make myself (throw up|vomit)", r"starve (myself|myself)",
    r"binge and (purge|vomit)", r"stop eating (completely|altogether|entirely)", r"punish myself.*(food|eat)",
]]
MEDICATION = [re.compile(p, _RX) for p in [
    r"(insulin|metformin|glimepiride|statin|amlodipine|telmisartan|levothyroxine)[^.?!]{0,40}\b(dose|dosage|units|mg)\b",
    r"\b(dose|dosage|how (much|many))\b[^.?!]{0,40}\b(insulin|metformin|glimepiride|statin|amlodipine|telmisartan|medicine|medication|tablet)",
    r"\b(stop|skip|reduce|increase|change|adjust)\b[^.?!]{0,25}\b(my )?(insulin|medicine|medication|tablets?|metformin|statin)",
]]
_RATE = re.compile(r"(\d+(?:\.\d+)?)\s*kg\s*(?:in|within|per)\s*(?:a |an |one |the next )?(\d+)?\s*(day|days|week|weeks)", _RX)
_LOW_KCAL = re.compile(r"(?:under|below|less than|only|just|eat)\s*(\d{3,4})\s*(?:kcal|calories|cals?)", _RX)
_FAST = re.compile(r"(?:fast|fasting|without eating)\s*(?:for)?\s*(\d+)\s*days?", _RX)
CRASH_WORDS = re.compile(r"crash diet|water fast|dry fast|starvation diet", _RX)

_MSG = {
    "emergency": (
        "This could be a medical emergency, and I can't assess it safely. Please call emergency services now "
        f"({EMERGENCY_NUMBER_IN} in India) or get to the nearest hospital, and ask someone nearby to stay with you. "
        "If you suspect a severe allergic reaction, don't wait to see whether it passes."
    ),
    "crisis": (
        "I'm really sorry you're feeling this way, and I'm glad you said it. You deserve support right now. "
        f"If you might act on these thoughts, please call {EMERGENCY_NUMBER_IN} or go to the nearest emergency room. "
        f"In India you can also reach Tele-MANAS, a free 24x7 mental-health helpline, on {TELE_MANAS_IN}. "
        "If you can, tell someone you trust how you're feeling so you're not alone with it."
    ),
    "eating_disorder": (
        "I can't help with restricting, purging or compensating for food - that could harm you. What you're "
        "describing deserves care from a doctor or a mental-health professional who understands eating concerns. "
        "I'm happy to keep talking, and I can help you find support or talk about eating in a gentle, balanced way."
    ),
    "dangerous_diet": (
        "I can't help with very rapid weight loss, extreme calorie cuts or prolonged fasting - these carry real "
        "risks. A safer approach is gradual change with guidance from a doctor or registered dietitian. I can "
        "help you plan balanced meals at a sustainable pace instead."
    ),
    "medication": (
        "I can't advise on medicine doses or on starting, stopping or changing any medication - that needs your "
        "doctor or pharmacist, who know your full history. I can help with how meals and timing fit into the "
        "plan they've given you."
    ),
}


def screen_user_message(text: str) -> SafetyResult:
    t = text or ""
    if any(p.search(t) for p in CRISIS):
        return SafetyResult("crisis", "self_harm", _MSG["crisis"])
    if any(p.search(t) for p in EMERGENCY):
        return SafetyResult("emergency", "acute_symptom", _MSG["emergency"])
    if any(p.search(t) for p in EATING_DISORDER):
        return SafetyResult("eating_disorder", "eating_disorder", _MSG["eating_disorder"])
    for m in _RATE.finditer(t):
        kg, n, unit = float(m.group(1)), m.group(2), m.group(3).lower()
        days = (int(n) if n else 1) * (7 if unit.startswith("week") else 1)
        if kg >= 3 and days <= 14:
            return SafetyResult("dangerous_diet", "rapid_weight_loss", _MSG["dangerous_diet"])
    m = _LOW_KCAL.search(t)
    if m and int(m.group(1)) < 1000:
        return SafetyResult("dangerous_diet", "very_low_calorie", _MSG["dangerous_diet"])
    m = _FAST.search(t)
    if (m and int(m.group(1)) >= 3) or CRASH_WORDS.search(t):
        return SafetyResult("dangerous_diet", "prolonged_fast", _MSG["dangerous_diet"])
    if any(p.search(t) for p in MEDICATION):
        return SafetyResult("medication", "medication_advice", _MSG["medication"])
    return SafetyResult("ok")


# ------------------------------------------------------------------ output validation
_DIAGNOSIS = re.compile(
    r"\byou (probably |likely |might |may well )?(have|suffer from|are suffering from|are diagnosed with)\s+"
    r"(diabetes|prediabetes|hypertension|high blood pressure|cancer|anaemia|anemia|kidney disease|fatty liver|a deficiency)",
    _RX,
)
_MED_ADVICE = re.compile(
    r"\b(take|inject|increase|reduce|decrease|stop|skip|double|halve)\b[^.]{0,30}\b(insulin|metformin|medication|medicine|tablets?|statins?)\b",
    _RX,
)
_NUM_UNIT = re.compile(r"(\d+(?:\.\d+)?)\s*(kcal|calories|g\b|grams|mg\b|%)", _RX)


def collect_numbers(obj) -> set[float]:
    out: set[float] = set()
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            out |= collect_numbers(v)
    elif isinstance(obj, (list, tuple, set)):
        for v in obj:
            out |= collect_numbers(v)
    return out


def validate_reply(reply: str, facts: dict) -> tuple[bool, list[str]]:
    """Reject replies that diagnose, give medication advice, or state nutrition numbers not in the facts."""
    problems: list[str] = []
    if _DIAGNOSIS.search(reply):
        problems.append("diagnosis_language")
    if _MED_ADVICE.search(reply):
        problems.append("medication_advice")
    allowed = collect_numbers(facts)
    for m in _NUM_UNIT.finditer(reply):
        val = float(m.group(1))
        if not any(abs(val - a) <= 0.51 for a in allowed):
            problems.append(f"unsupported_number:{m.group(0)}")
    return (not problems), problems
