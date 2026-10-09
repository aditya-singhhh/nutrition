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
class SmartScan:
    kind: str  # food | label | none
    dishes: list = field(default_factory=list)  # list[DishCandidate] when kind == food
    label_text: str = ""  # when kind == label


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


class _GeminiClient:
    _BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str, model: str, timeout: float = 45.0):
        if not api_key:
            raise ProviderNotConfigured("HC_GEMINI_API_KEY is required for the gemini provider")
        self._key, self._model, self._timeout = api_key, model, timeout

    def generate(self, prompt: str, image: bytes, *, json_out: bool) -> str:
        import base64

        body: dict = {
            "contents": [{"parts": [{"text": prompt},
                                    {"inline_data": {"mime_type": _mime(image), "data": base64.b64encode(image).decode()}}]}],
            "generationConfig": {"temperature": 0},
        }
        if json_out:
            body["generationConfig"]["responseMimeType"] = "application/json"
        try:
            r = httpx.post(f"{self._BASE}/{self._model}:generateContent", json=body,
                           headers={"x-goog-api-key": self._key}, timeout=self._timeout)
            r.raise_for_status()
            parts = r.json()["candidates"][0]["content"]["parts"]
            return "".join(p.get("text", "") for p in parts)
        except httpx.HTTPStatusError as e:  # status code only: never log the key or the image
            code = e.response.status_code
            hint = {400: "bad request (check HC_GEMINI_MODEL)", 401: "key rejected", 403: "key rejected or not allowed",
                    404: "model not found (check HC_GEMINI_MODEL)", 429: "rate limit reached, try again shortly"}.get(code, "")
            raise ProviderError(f"Gemini returned HTTP {code} {hint}".strip()) from e
        except (httpx.HTTPError, KeyError, IndexError, ValueError) as e:
            raise ProviderError(f"Gemini call failed: {type(e).__name__}") from e


class GeminiVisionProvider:
    """Names dishes from a photo. The model may ONLY pick from our known food list and gives no nutrition numbers;
    all nutrients are computed from the verified food table by the caller."""

    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self._c = _GeminiClient(api_key, model)
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
        """One call: decide whether the photo shows food or a packaged-food label, and extract accordingly."""
        import json

        known = known or []
        allowed = {slug for slug, _ in known}
        menu = "\n".join(f"{slug} = {name}" for slug, name in known)
        prompt = (
            "You are the scanner of an Indian nutrition app. Decide what the photo shows.\n"
            '- If it shows prepared food or a meal, set kind to "food" and list dishes using ONLY these ids:\n'
            f"{menu}\n"
            '- If it mainly shows the printed ingredients/nutrition text of a packaged product, set kind to "label" and '
            "transcribe the ingredient list and additive codes exactly as printed into label_text.\n"
            '- Otherwise set kind to "none".\n'
            'Return JSON: {"kind":"food|label|none","items":[{"slug":"<id>","confidence":0..1,"grams_min":number,'
            '"grams_max":number}],"label_text":"..."}. Items only for kind food: one per distinct dish, realistic edible-weight '
            "range in grams, leave out dishes not in the list. Never return calories or other nutrition values."
        )
        raw = self._c.generate(prompt, image, json_out=True)
        try:
            data = json.loads(raw)
            kind = str(data.get("kind", "none"))
        except (ValueError, AttributeError) as e:
            raise ProviderError("Gemini returned unreadable output") from e
        if kind == "food":
            dishes = self._parse_items(data.get("items", []), allowed)
            return SmartScan("food", dishes) if dishes else SmartScan("none")
        if kind == "label" and str(data.get("label_text", "")).strip():
            return SmartScan("label", label_text=str(data["label_text"]).strip())
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

    def __init__(self, api_key: str, model: str):
        self._c = _GeminiClient(api_key, model)
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
        vision: VisionProvider = NullVisionProvider()
        if s.vision_provider == "mock":
            vision = MockVisionProvider()
        elif s.vision_provider == "gemini" or (gem and s.vision_provider == "null"):
            vision = GeminiVisionProvider(s.gemini_api_key, s.gemini_model)
        ocr: OCRProvider = NullOCRProvider()
        if s.ocr_provider == "mock":
            ocr = MockOCRProvider()
        elif s.ocr_provider == "gemini" or (gem and s.ocr_provider == "null"):
            ocr = GeminiOCRProvider(s.gemini_api_key, s.gemini_model)
        return cls(llm=llm, vision=vision, ocr=ocr)
