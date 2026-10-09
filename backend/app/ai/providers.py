"""AI Gateway: provider interfaces + adapters. Business logic depends only on these Protocols.

Privacy rule: callers pass the minimum necessary context (no name/email/ids) to any external provider.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    pass


class ProviderNotConfigured(ProviderError):
    pass


# ---------------------------------------------------------------- LLM
@dataclass
class LLMRequest:
    system: str
    user_message: str
    facts: dict  # verified numbers/rules produced by deterministic tools
    draft: str  # deterministic draft answer built from the facts
    prompt_version: str


@dataclass
class LLMResult:
    text: str
    model: str
    version: str


class LLMProvider(Protocol):
    name: str

    def generate(self, req: LLMRequest) -> LLMResult: ...


class MockLLMProvider:
    """Deterministic: returns the draft unchanged. Default for dev/test and the safe fallback."""

    name = "mock"

    def generate(self, req: LLMRequest) -> LLMResult:
        return LLMResult(text=req.draft, model="mock", version="1")


class AnthropicLLMProvider:
    """Rewrites the deterministic draft in a friendlier tone. Model id comes from config, not code.

    NOTE: not exercised by the automated tests (needs a real key); treat as untested until smoke-tested.
    """

    name = "anthropic"
    _URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str, timeout: float = 20.0):
        if not api_key or not model:
            raise ProviderNotConfigured("HC_LLM_API_KEY and HC_LLM_MODEL are required for the anthropic provider")
        self._key, self._model, self._timeout = api_key, model, timeout

    def generate(self, req: LLMRequest) -> LLMResult:
        prompt = (
            f"{req.system}\n\nUSER QUESTION:\n{req.user_message}\n\nVERIFIED FACTS (JSON):\n{req.facts}\n\n"
            f"DRAFT ANSWER:\n{req.draft}\n\nRewrite the draft in a warm, concise tone. Do not add any numbers, "
            "medical claims, diagnoses or medication advice that are not in the draft."
        )
        try:
            r = httpx.post(
                self._URL,
                headers={"x-api-key": self._key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": self._model, "max_tokens": 500, "messages": [{"role": "user", "content": prompt}]},
                timeout=self._timeout,
            )
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
        except (httpx.HTTPError, ValueError) as e:
            raise ProviderError(f"LLM call failed: {type(e).__name__}") from e
        if not text.strip():
            raise ProviderError("LLM returned empty text")
        return LLMResult(text=text.strip(), model=self._model, version="api")


# ---------------------------------------------------------------- Vision
@dataclass
class DishCandidate:
    food_slug: str
    confidence: float  # 0..1
    portion_g_min: float
    portion_g_max: float


class VisionProvider(Protocol):
    name: str
    version: str

    def detect_dishes(self, image: bytes, known: list[tuple[str, str]] | None = None) -> list[DishCandidate]: ...

    def smart(self, image: bytes, known: list[tuple[str, str]] | None = None) -> SmartScan: ...


@dataclass
class DishGuess:
    """A dish the model saw that is not (by id) in our food list; the caller may fuzzy-match the name."""
    name: str
    confidence: float
    portion_g_min: float
    portion_g_max: float


@dataclass
class SmartScan:
    kind: str  # food | label | product | none
    dishes: list = field(default_factory=list)  # list[DishCandidate] when kind == food
    unmatched: list = field(default_factory=list)  # list[DishGuess]
    label_text: str = ""  # when kind == label
    barcode: str = ""  # digits read from a visible barcode number, when kind == product


class NullVisionProvider:
    name, version = "null", "0"

    def detect_dishes(self, image: bytes, known: list[tuple[str, str]] | None = None) -> list[DishCandidate]:
        raise ProviderNotConfigured("No food-recognition model is configured (set HC_GEMINI_API_KEY on the server)")

    def smart(self, image: bytes, known: list[tuple[str, str]] | None = None) -> SmartScan:
        raise ProviderNotConfigured("No food-recognition model is configured (set HC_GEMINI_API_KEY on the server)")


class MockVisionProvider:
    name, version = "mock", "1"

    def __init__(self, candidates: list[DishCandidate] | None = None):
        self.candidates = candidates or []

    def detect_dishes(self, image: bytes, known: list[tuple[str, str]] | None = None) -> list[DishCandidate]:
        return list(self.candidates)

    def smart(self, image: bytes, known: list[tuple[str, str]] | None = None) -> SmartScan:
        return SmartScan("food", list(self.candidates)) if self.candidates else SmartScan("none")


# ---------------------------------------------------------------- OCR
@dataclass
class OCRResult:
    text: str
    confidence: float | None = None


class OCRProvider(Protocol):
    name: str
    version: str

    def extract_text(self, image: bytes, languages: tuple[str, ...] = ("en", "hi")) -> OCRResult: ...


class NullOCRProvider:
    name, version = "null", "0"

    def extract_text(self, image: bytes, languages: tuple[str, ...] = ("en", "hi")) -> OCRResult:
        raise ProviderNotConfigured("No OCR engine is configured (HC_OCR_PROVIDER)")


class MockOCRProvider:
    name, version = "mock", "1"

    def __init__(self, text: str = ""):
        self.text = text

    def extract_text(self, image: bytes, languages: tuple[str, ...] = ("en", "hi")) -> OCRResult:
        return OCRResult(text=self.text, confidence=0.9)


# ---------------------------------------------------------------- Gemini (vision + OCR)
def _mime(image: bytes) -> str:
    if image[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if image[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image[:4] == b"RIFF" and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _red_png(size: int = 16) -> bytes:
    import struct
    import zlib

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\xff\x00\x00" * size for _ in range(size))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


_FALLBACK_MODELS = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest", "gemini-flash-lite-latest",
                    "gemini-2.0-flash", "gemini-1.5-flash")
_API = "https://generativelanguage.googleapis.com/v1beta"
_ROUTES = {
    "ai-studio": _API + "/models/{m}:generateContent",
    "vertex-express": "https://aiplatform.googleapis.com/v1/publishers/google/models/{m}:generateContent",
}
_SKIP = ("image", "tts", "live", "audio", "native", "thinking", "embedding", "robotics", "computer", "learn")


class _GeminiClient:
    """Calls Gemini. Asks Google which models this key can use (ListModels), tries those and some fallbacks, retries
    short outages (503), falls back to the Vertex 'express' endpoint, and remembers the combination that worked."""

    def __init__(self, api_key: str, model: str, timeout: float = 45.0):
        if not api_key:
            raise ProviderNotConfigured("HC_GEMINI_API_KEY is required for the gemini provider")
        self._key, self._timeout, self._configured = api_key, timeout, model
        self._routes = list(_ROUTES)  # AI Studio first; Vertex express only if that fails
        self.working: tuple[str, str] | None = None  # (route, model)
        self.available: list[str] = []
        self._discovered = False
        self.last_error = ""

    def _discover(self) -> None:
        self._discovered = True
        try:
            r = httpx.get(f"{_API}/models", params={"pageSize": 200}, headers={"x-goog-api-key": self._key}, timeout=15.0)
            r.raise_for_status()
            names = []
            for m in r.json().get("models", []):
                n = str(m.get("name", "")).removeprefix("models/")
                if "generateContent" in m.get("supportedGenerationMethods", []) and "flash" in n and not any(x in n for x in _SKIP):
                    names.append(n)
            self.available = sorted(names, key=lambda n: (("preview" in n) or ("exp" in n), "lite" in n, n))
        except (httpx.HTTPError, ValueError):
            self.available = []

    def _candidates(self) -> list[str]:
        return [m for m in dict.fromkeys([self._configured, *self.available, *_FALLBACK_MODELS]) if m]

    def _attempts(self):
        if self.working:
            yield self.working
            return
        if not self._discovered:
            self._discover()
        for r in self._routes:
            for m in self._candidates():
                yield r, m

    def generate(self, prompt: str, image: bytes | None, *, json_out: bool) -> str:
        import base64
        import time

        parts: list = [{"text": prompt}]
        if image is not None:
            parts.append({"inline_data": {"mime_type": _mime(image), "data": base64.b64encode(image).decode()}})
        body: dict = {"contents": [{"role": "user", "parts": parts}], "generationConfig": {"temperature": 0}}
        if json_out:
            body["generationConfig"]["responseMimeType"] = "application/json"
        errors: list[str] = []
        for route, model in self._attempts():
            for attempt in (1, 2):  # one retry for short outages
                try:
                    r = httpx.post(_ROUTES[route].format(m=model), json=body, headers={"x-goog-api-key": self._key},
                                   timeout=self._timeout)
                    r.raise_for_status()
                    out = "".join(p.get("text", "") for p in r.json()["candidates"][0]["content"]["parts"])
                    self.working, self.last_error = (route, model), ""
                    return out
                except httpx.HTTPStatusError as e:  # status code only: never log the key or the image
                    code = e.response.status_code
                    if code in (500, 502, 503, 504) and attempt == 1:
                        time.sleep(1.5)
                        continue
                    errors.append(f"{route}/{model}: HTTP {code}")
                    if code == 429 or (self.working and code != 404):
                        self.last_error = "; ".join(errors[-6:])
                        raise ProviderError(f"Gemini call failed ({self.last_error})") from e
                    break  # try the next model
                except httpx.HTTPError as e:  # network trouble: other models won't help
                    errors.append(f"{route}/{model}: {type(e).__name__}")
                    self.last_error = "; ".join(errors[-6:])
                    raise ProviderError(f"Gemini call failed ({self.last_error})") from e
                except (KeyError, IndexError, ValueError):
                    errors.append(f"{route}/{model}: unexpected response")
                    break
        self.working = None
        self.last_error = "; ".join(errors[-6:])
        raise ProviderError(f"Gemini call failed ({self.last_error})")

    def probe(self, with_image: bool = False) -> dict:
        try:
            if with_image:
                answer = self.generate("What is the main colour of this image? Answer with one word.", _red_png(), json_out=False)
                base = {"image_ok": True, "model_said": answer.strip()[:40]}
            else:
                self.generate("Reply with the single word: ok", None, json_out=False)
                base = {}
            return {"ok": True, **base, **({"route": self.working[0], "model": self.working[1]} if self.working else {})}
        except ProviderError as e:
            return {"ok": False, "error": str(e), "models_google_offers_this_key": self.available,
                    "tried_models": self._candidates(), "key_prefix_is_AQ": self._key.startswith("AQ.")}


class GeminiVisionProvider:
    """Names dishes from a photo. The model may ONLY pick from our known food list and gives no nutrition numbers;
    all nutrients are computed from the verified food table by the caller."""

    name = "gemini"

    def __init__(self, api_key: str, model: str, client: _GeminiClient | None = None):
        self._c = client or _GeminiClient(api_key, model)
        self.version = model

    def detect_dishes(self, image: bytes, known: list[tuple[str, str]] | None = None) -> list[DishCandidate]:
        import json

        known = known or []
        allowed = {slug for slug, _ in known}
        menu = "\n".join(f"{slug} = {name}" for slug, name in known)
        prompt = (
            "You identify food in a photo for an Indian nutrition app. Choose ONLY from this list of food ids:\n"
            f"{menu}\n\n"
            'Return JSON: {"items":[{"slug":"<id from the list>","confidence":0..1,"grams_min":number,"grams_max":number}]}. '
            "One entry per distinct dish visible. Give a realistic edible-weight range in grams for the portion shown. "
            "If a dish is not in the list, leave it out. If there is no food, return {\"items\":[]}. "
            "Do not return calories or any other nutrition values."
        )
        raw = self._c.generate(prompt, image, json_out=True)
        try:
            items = json.loads(raw).get("items", [])
        except (ValueError, AttributeError) as e:
            raise ProviderError("Gemini returned unreadable output") from e
        return self._parse_items(items, allowed)

    def smart(self, image: bytes, known: list[tuple[str, str]] | None = None) -> SmartScan:
        """One call: decide whether the photo shows food, a packaged-food label or a barcode, and extract accordingly."""
        import json
        import re

        known = known or []
        allowed = {slug for slug, _ in known}
        menu = "\n".join(f"{slug} = {name}" for slug, name in known)
        prompt = (
            "You are the scanner of an Indian nutrition app. Decide what the photo shows.\n"
            '- Prepared food or a meal: kind "food". For each distinct dish give "name" (plain English dish name) and, if it '
            "matches one of these ids, its \"slug\":\n"
            f"{menu}\n"
            '- A packaged product whose barcode NUMBER is readable: kind "product" and put the digits in "barcode".\n'
            '- The printed ingredients/nutrition text of a packaged product: kind "label", transcribe the ingredient list and '
            'additive codes exactly as printed into "label_text".\n'
            '- Otherwise kind "none".\n'
            'Return JSON: {"kind":"food|product|label|none","items":[{"name":"...","slug":"<id or empty>","confidence":0..1,'
            '"grams_min":number,"grams_max":number}],"barcode":"","label_text":""}. For food give a realistic edible-weight '
            "range in grams for the portion shown. Never return calories or other nutrition values."
        )
        raw = self._c.generate(prompt, image, json_out=True)
        try:
            data = json.loads(raw)
            kind = str(data.get("kind", "none"))
        except (ValueError, AttributeError) as e:
            raise ProviderError("Gemini returned unreadable output") from e
        digits = re.sub(r"\D", "", str(data.get("barcode", "")))
        if 8 <= len(digits) <= 14:
            return SmartScan("product", barcode=digits)
        if kind == "label" and str(data.get("label_text", "")).strip():
            return SmartScan("label", label_text=str(data["label_text"]).strip())
        if kind == "food":
            dishes, unmatched = [], []
            for it in data.get("items", []) if isinstance(data.get("items"), list) else []:
                try:
                    conf = min(1.0, max(0.0, float(it["confidence"])))
                    lo, hi = sorted((float(it["grams_min"]), float(it["grams_max"])))
                except (KeyError, TypeError, ValueError):
                    continue
                if lo <= 0 or hi > 3000:
                    continue
                slug = str(it.get("slug") or "")
                if slug in allowed:
                    dishes.append(DishCandidate(slug, conf, lo, hi))
                elif str(it.get("name") or "").strip():
                    unmatched.append(DishGuess(str(it["name"]).strip()[:60], conf, lo, hi))
            if dishes or unmatched:
                return SmartScan("food", dishes, unmatched)
        return SmartScan("none")

    @staticmethod
    def _parse_items(items, allowed: set[str]) -> list[DishCandidate]:
        out: list[DishCandidate] = []
        for it in items if isinstance(items, list) else []:
            try:
                slug = str(it["slug"])
                conf = min(1.0, max(0.0, float(it["confidence"])))
                lo, hi = sorted((float(it["grams_min"]), float(it["grams_max"])))
            except (KeyError, TypeError, ValueError):
                continue
            if slug not in allowed or lo <= 0 or hi > 3000:
                continue
            out.append(DishCandidate(slug, conf, lo, hi))
        return out


class GeminiOCRProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str, client: _GeminiClient | None = None):
        self._c = client or _GeminiClient(api_key, model)
        self.version = model

    def extract_text(self, image: bytes, languages: tuple[str, ...] = ("en", "hi")) -> OCRResult:
        text = self._c.generate(
            "Transcribe the ingredient list and any additive codes from this food label exactly as printed. "
            "Output plain text only, no commentary. If there is no label text, output nothing.", image, json_out=False)
        return OCRResult(text=text.strip(), confidence=None)


# ---------------------------------------------------------------- Gateway
@dataclass
class AIGateway:
    llm: LLMProvider = field(default_factory=MockLLMProvider)
    vision: VisionProvider = field(default_factory=NullVisionProvider)
    ocr: OCRProvider = field(default_factory=NullOCRProvider)
    gemini: _GeminiClient | None = None

    @classmethod
    def from_settings(cls, s: Settings) -> AIGateway:
        llm: LLMProvider
        if s.llm_provider == "anthropic":
            llm = AnthropicLLMProvider(s.llm_api_key, s.llm_model)
        elif s.llm_provider == "mock":
            llm = MockLLMProvider()
        else:
            raise ProviderNotConfigured(f"unknown llm provider: {s.llm_provider}")
        gem = bool(s.gemini_api_key)
        shared = _GeminiClient(s.gemini_api_key, s.gemini_model) if gem else None
        vision: VisionProvider = NullVisionProvider()
        if s.vision_provider == "mock":
            vision = MockVisionProvider()
        elif s.vision_provider == "gemini" or (gem and s.vision_provider == "null"):
            vision = GeminiVisionProvider(s.gemini_api_key, s.gemini_model, shared)
        ocr: OCRProvider = NullOCRProvider()
        if s.ocr_provider == "mock":
            ocr = MockOCRProvider()
        elif s.ocr_provider == "gemini" or (gem and s.ocr_provider == "null"):
            ocr = GeminiOCRProvider(s.gemini_api_key, s.gemini_model, shared)
        gw = cls(llm=llm, vision=vision, ocr=ocr)
        gw.gemini = shared
        return gw

    def status(self, with_image: bool = False) -> dict:
        if self.gemini is None:
            return {"gemini_configured": False, "vision": self.vision.name, "ocr": self.ocr.name}
        return {"gemini_configured": True, **self.gemini.probe(with_image)}
