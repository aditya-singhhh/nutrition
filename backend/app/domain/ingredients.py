"""Ingredient-list parsing and additive/allergen analysis (rule + reference-data based, no LLM).

Handles English, Hindi (Devanagari) and common Hinglish label terms, and INS / E numbers.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache

from app.core.config import DATA_DIR

INS_RE = re.compile(r"\b(?:INS|E)\s*[-.]?\s*(\d{3,4}\s?[a-z]?)(?:\s*\(\s*[ivx]+\s*\))?", re.IGNORECASE)
# bare numbers inside parentheses after a function word, e.g. "Acidity Regulator (330, 331)"
FUNCTION_WORDS = (
    "colour", "color", "preservative", "emulsifier", "acidity regulator", "antioxidant",
    "stabiliser", "stabilizer", "thickener", "flavour enhancer", "flavor enhancer", "sweetener",
    "raising agent", "anticaking", "anti-caking", "humectant", "flour treatment",
)
BARE_CODES_RE = re.compile(r"\(\s*((?:\d{3,4}[a-z]?(?:\s*\(\s*[ivx]+\s*\))?\s*[,&]?\s*)+)\)", re.IGNORECASE)

ALLERGEN_TERMS: dict[str, list[str]] = {
    "milk": ["milk", "butter", "ghee", "cream", "whey", "casein", "lactose", "curd", "paneer", "khoya", "dahi",
             "doodh", "milk solids", "दूध", "घी", "दही", "पनीर", "मक्खन"],
    "gluten": ["wheat", "atta", "maida", "semolina", "suji", "sooji", "rava", "gluten", "barley", "rye",
               "malt", "गेहूं", "गेहूँ", "आटा", "मैदा", "सूजी", "जौ"],
    "soy": ["soy", "soya", "soybean", "सोया"],
    "peanut": ["peanut", "groundnut", "moongphali", "मूंगफली"],
    "tree_nuts": ["almond", "cashew", "walnut", "pistachio", "hazelnut", "badam", "kaju", "pista", "काजू", "बादाम",
                  "पिस्ता", "अखरोट", "nuts", "tree nut"],
    "egg": ["egg", "albumen", "ovalbumin", "अंडा", "अंडे"],
    "fish": ["fish", "anchovy", "मछली"],
    "shellfish": ["prawn", "shrimp", "crab", "lobster"],
    "sesame": ["sesame", "til", "तिल"],
    "mustard": ["mustard", "sarson", "सरसों"],
}

SUGAR_TERMS = ["sugar", "sucrose", "glucose", "fructose", "dextrose", "maltodextrin", "invert sugar", "corn syrup",
               "glucose syrup", "liquid glucose", "high fructose", "honey", "jaggery", "molasses", "cane syrup",
               "चीनी", "शक्कर"]
REFINED_FLOUR_TERMS = ["maida", "refined wheat flour", "refined flour", "मैदा"]
HYDROGENATED_TERMS = ["hydrogenated", "vanaspati", "margarine", "shortening", "वनस्पति"]
ULTRA_PROCESSED_MARKERS = ["flavour", "flavor", "maltodextrin", "hydrolysed", "hydrolyzed", "isolate",
                           "high fructose", "modified starch", "nature identical", "artificial"]


@lru_cache
def load_additives() -> dict:
    with open(DATA_DIR / "additives.json", encoding="utf-8") as f:
        data = json.load(f)
    by_code = {a["ins"].lower(): a for a in data["additives"]}
    return {"version": data["version"], "by_code": by_code, "all": data["additives"]}


def lookup_additive(code: str) -> dict | None:
    code = re.sub(r"\s+", "", code.lower())
    by_code = load_additives()["by_code"]
    if code in by_code:
        return by_code[code]
    base = re.sub(r"\(.*?\)", "", code)  # 160a(i) -> 160a
    if base in by_code:
        return by_code[base]
    # 150 or 322 with sub-letters: try stripping a trailing letter (e.g. 322i -> 322)
    stripped = re.sub(r"[a-z]$", "", base)
    return by_code.get(stripped)


def _kw_in(text: str, kw: str) -> bool:
    if kw.isascii():
        # optional plural: "peanuts", "eggs", "prawns" must match too (a missed allergen is the costly error)
        return re.search(rf"\b{re.escape(kw)}(?:s|es)?\b", text) is not None
    return kw in text  # Devanagari: \b is unreliable around combining marks


NON_DAIRY_MILK_PHRASES = re.compile(
    r"\b(coconut|almond|soy|soya|oat|rice|cashew) milk\b|\b(cocoa|cacao|peanut|shea|nut|almond) butter\b|\bcream of tartar\b"
)


def detect_allergens(text: str) -> set[str]:
    low = text.lower()
    out: set[str] = set()
    for a, kws in ALLERGEN_TERMS.items():
        hay = NON_DAIRY_MILK_PHRASES.sub(" ", low) if a == "milk" else low
        if any(_kw_in(hay, k) for k in kws):
            out.add(a)
    return out


def _split_top_level(text: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip(" .\n\t") for p in parts if p.strip(" .\n\t")]


def _extract_may_contain(text: str) -> tuple[str, str]:
    m = re.search(r"(may contain|manufactured in a facility|produced in a facility|हो सकते हैं)[^.]*\.?", text,
                  flags=re.IGNORECASE)
    if not m:
        return text, ""
    return (text[: m.start()] + text[m.end():]).strip(), m.group(0)


def _extract_additive_codes(segment: str) -> list[str]:
    codes: list[str] = []
    for m in INS_RE.finditer(segment):
        codes.append(m.group(1).replace(" ", "").lower())
    low = segment.lower()
    if any(w in low for w in FUNCTION_WORDS):
        for m in BARE_CODES_RE.finditer(segment):
            for c in re.findall(r"\d{3,4}[a-z]?", m.group(1), flags=re.IGNORECASE):
                codes.append(c.lower())
    return codes


@dataclass
class IngredientAnalysis:
    ingredients: list[dict] = field(default_factory=list)
    additives: list[dict] = field(default_factory=list)
    allergens: list[str] = field(default_factory=list)
    may_contain: list[str] = field(default_factory=list)
    flags: list[dict] = field(default_factory=list)
    estimated_nova: int | None = None
    unrecognised_codes: list[str] = field(default_factory=list)
    reference_version: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def analyze_ingredients(text: str) -> IngredientAnalysis:
    ref = load_additives()
    result = IngredientAnalysis(reference_version=ref["version"])
    if not text or not text.strip():
        return result

    body = re.sub(r"^\s*(ingredients?|सामग्री)\s*[:\-]?\s*", "", text.strip(), flags=re.IGNORECASE)
    body = re.sub(r"\s+", " ", body)
    body, may_contain_text = _extract_may_contain(body)
    contains_m = re.search(r"\bcontains?\b\s*:?[^.]*\.?\s*$", body, flags=re.IGNORECASE)
    declared_text = ""
    if contains_m and not re.search(r"\bcontains?\b\s*\d", contains_m.group(0), flags=re.IGNORECASE):
        declared_text = contains_m.group(0)
        body = body[: contains_m.start()].strip()

    seen_codes: dict[str, dict] = {}
    for pos, seg in enumerate(_split_top_level(body), start=1):
        pct = re.search(r"(\d+(?:\.\d+)?)\s*%", seg)
        codes = _extract_additive_codes(seg)
        # additive by name (e.g. "Emulsifier (Soy Lecithin)", "Sodium Benzoate")
        low = seg.lower()
        for a in ref["all"]:
            if any(re.search(rf"\b{re.escape(n)}\b", low) for n in a["names"]):
                codes.append(a["ins"].lower())
        ing_codes = []
        for c in dict.fromkeys(codes):
            info = lookup_additive(c)
            if info is None:
                if c not in result.unrecognised_codes:
                    result.unrecognised_codes.append(c)
                continue
            ing_codes.append(info["ins"])
            seen_codes.setdefault(info["ins"].lower(), info)
        result.ingredients.append(
            {"position": pos, "raw": seg, "percent": float(pct.group(1)) if pct else None, "additives": ing_codes}
        )

    result.additives = [
        {"ins": a["ins"], "name": a["name"], "function": a["function"], "category": a["category"],
         "explanation": a["explanation"], "evidence_source": a["evidence_source"]}
        for a in seen_codes.values()
    ]

    allergens = detect_allergens(body) | detect_allergens(declared_text)
    for a in seen_codes.values():
        if a.get("allergen"):
            allergens.add(a["allergen"])
    result.allergens = sorted(allergens)
    result.may_contain = sorted(detect_allergens(may_contain_text) - allergens)

    low_body = body.lower()
    first_three = " , ".join(i["raw"] for i in result.ingredients[:3]).lower()
    if any(_kw_in(first_three, t) for t in SUGAR_TERMS):
        result.flags.append({"code": "sugar_among_first_three", "explanation":
                             "A sugar source is among the first three ingredients, so it makes up a large share by weight."})
    if result.ingredients and any(_kw_in(result.ingredients[0]["raw"].lower(), t) for t in REFINED_FLOUR_TERMS):
        result.flags.append({"code": "refined_flour_first", "explanation":
                             "Refined wheat flour (maida) is the main ingredient."})
    if any(_kw_in(low_body, t) for t in HYDROGENATED_TERMS):
        result.flags.append({"code": "hydrogenated_fat", "explanation":
                             "Contains hydrogenated fat / vanaspati / margarine, which can be a source of trans fat."})

    # NOVA estimate: markers of industrial formulation -> group 4; otherwise group 3 for multi-ingredient foods.
    cosmetic_functions = {"colour", "emulsifier", "flavour enhancer", "sweetener", "thickener", "emulsifier/stabiliser",
                          "modified starch"}
    is_up = any(a["function"] in cosmetic_functions for a in result.additives) or any(
        _kw_in(low_body, m) for m in ULTRA_PROCESSED_MARKERS
    )
    if not result.ingredients:
        result.estimated_nova = None
    elif is_up:
        result.estimated_nova = 4
    elif len(result.ingredients) <= 1:
        result.estimated_nova = 1
    else:
        result.estimated_nova = 3
    return result
