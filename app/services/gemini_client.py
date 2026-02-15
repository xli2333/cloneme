from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import settings

try:
    from google import genai
    from google.genai import types as genai_types
except Exception:  # pragma: no cover - import is validated at runtime
    genai = None
    genai_types = None


@dataclass(slots=True)
class GeminiCallResult:
    text: str
    model_used: str


class GeminiClient:
    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required.")
        if genai is None:
            raise RuntimeError("google-genai is not installed.")
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self._available_models: set[str] | None = None

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        value = (name or "").strip()
        if not value:
            return ""
        if value.startswith("models/"):
            return value.split("/", 1)[1]
        return value

    def _ensure_available_models(self) -> set[str]:
        if self._available_models is not None:
            return self._available_models
        names = self.list_models()
        if not names:
            self._available_models = set()
            return self._available_models
        normalized = {
            n for raw in names for n in (raw, self._normalize_model_name(raw)) if n
        }
        self._available_models = normalized
        return self._available_models

    def _candidate_models(self, primary: str) -> list[str]:
        primary_norm = self._normalize_model_name(primary).lower()
        wants_flash = "flash" in primary_norm
        wants_pro = "pro" in primary_norm

        fallbacks = [name for name in settings.gemini_fallback_models if name]
        if wants_flash or wants_pro:
            def _priority(name: str) -> tuple[int, int]:
                n = self._normalize_model_name(name).lower()
                same_family = ("flash" in n) if wants_flash else ("pro" in n)
                # Keep original relative order among same priority items.
                return (0 if same_family else 1, fallbacks.index(name))
            fallbacks = sorted(fallbacks, key=_priority)

        models = [primary]
        for name in fallbacks:
            if name and name not in models:
                models.append(name)
        available = self._ensure_available_models()
        if not available:
            return models
        filtered = [m for m in models if m in available or self._normalize_model_name(m) in available]
        return filtered or models

    def generate(
        self,
        *,
        primary_model: str,
        prompt: str,
        temperature: float = 0.7,
        max_output_tokens: int = 2048,
        response_mime_type: str | None = None,
    ) -> GeminiCallResult:
        last_error: Exception | None = None
        for model_name in self._candidate_models(primary_model):
            try:
                if genai_types is not None:
                    kwargs: dict[str, Any] = {
                        "temperature": temperature,
                        "max_output_tokens": max_output_tokens,
                    }
                    if response_mime_type:
                        kwargs["response_mime_type"] = response_mime_type
                    config = genai_types.GenerateContentConfig(**kwargs)
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config,
                    )
                else:
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                    )
                text = getattr(response, "text", "") or ""
                if not text and getattr(response, "candidates", None):
                    try:
                        parts = response.candidates[0].content.parts
                        text = "".join(getattr(p, "text", "") for p in parts if getattr(p, "text", ""))
                    except Exception:
                        text = ""
                if not text:
                    raise RuntimeError(f"empty response from model {model_name}")
                return GeminiCallResult(text=text.strip(), model_used=model_name)
            except Exception as exc:  # pragma: no cover - runtime fallback
                last_error = exc
                continue
        raise RuntimeError(f"all Gemini model attempts failed: {last_error}")

    def list_models(self) -> list[str]:
        names: list[str] = []
        try:
            for model in self.client.models.list():
                name = getattr(model, "name", "")
                if name:
                    names.append(name)
        except Exception:
            return []
        return names

    def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
        task_type: str = "RETRIEVAL_DOCUMENT",
        output_dimensionality: int | None = None,
    ) -> list[list[float]]:
        if not texts:
            return []

        model_name = model or settings.gemini_embedding_model
        dim = int(output_dimensionality or settings.gemini_embedding_dim)

        if genai_types is not None:
            config = genai_types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=dim,
            )
            response = self.client.models.embed_content(
                model=model_name,
                contents=texts,
                config=config,
            )
        else:
            response = self.client.models.embed_content(
                model=model_name,
                contents=texts,
            )

        embeddings = getattr(response, "embeddings", None) or []
        vectors: list[list[float]] = []
        for item in embeddings:
            values = getattr(item, "values", None) or []
            vec = [float(v) for v in values]
            if dim > 0 and len(vec) != dim:
                raise RuntimeError(
                    f"embedding dim mismatch expected={dim} actual={len(vec)} model={model_name} task_type={task_type}"
                )
            vectors.append(vec)
        return vectors


_client: GeminiClient | None = None


def get_gemini_client() -> GeminiClient:
    global _client
    if _client is None:
        _client = GeminiClient()
    return _client
