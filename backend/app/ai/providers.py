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

    def detect_dishes(self, image: bytes) -> list[DishCandidate]: ...


class NullVisionProvider:
    name, version = "null", "0"

    def detect_dishes(self, image: bytes) -> list[DishCandidate]:
        raise ProviderNotConfigured("No food-recognition model is configured (HC_VISION_PROVIDER)")


class MockVisionProvider:
    name, version = "mock", "1"

    def __init__(self, candidates: list[DishCandidate] | None = None):
        self.candidates = candidates or []

    def detect_dishes(self, image: bytes) -> list[DishCandidate]:
        return list(self.candidates)


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
        vision: VisionProvider = MockVisionProvider() if s.vision_provider == "mock" else NullVisionProvider()
        ocr: OCRProvider = MockOCRProvider() if s.ocr_provider == "mock" else NullOCRProvider()
        return cls(llm=llm, vision=vision, ocr=ocr)
