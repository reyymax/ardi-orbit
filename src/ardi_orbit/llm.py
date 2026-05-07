"""LLM wrapper around litellm with JSON-mode helpers."""

from __future__ import annotations

import json
import os
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import Settings
from .logging import get_logger

log = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """Raised when the LLM returns malformed output we cannot recover from."""


def _configure_provider_env(settings: Settings) -> None:
    """Wire MiMo creds into env vars litellm understands.

    MiMo exposes an OpenAI-compatible API, so we map MIMO_* -> OPENAI_*
    when the active model uses the openai/ provider prefix and the user
    hasn't already set their own OpenAI creds.
    """
    if settings.mimo_api_key and not os.environ.get("OPENAI_API_KEY_USER_SET"):
        os.environ.setdefault("OPENAI_API_KEY", settings.mimo_api_key)
        os.environ.setdefault("OPENAI_API_BASE", settings.mimo_api_base)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((LLMError, TimeoutError)),
)
def chat_json(
    *,
    model: str,
    system: str,
    user: str,
    schema: type[T],
    settings: Settings,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> T:
    """Call the LLM and parse its JSON response into the given schema.

    Retries up to 3 times on malformed output.
    """
    # Lazy import so tests can run without litellm installed.
    import litellm

    _configure_provider_env(settings)

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    log.debug("LLM call model=%s temp=%s schema=%s", model, temperature, schema.__name__)

    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
    except Exception as exc:
        raise LLMError(f"LLM request failed: {exc}") from exc

    content = _extract_content(response)
    parsed = _parse_json(content)
    try:
        return schema.model_validate(parsed)
    except ValidationError as exc:
        raise LLMError(f"LLM output failed schema validation: {exc}\nRaw: {content}") from exc


def _extract_content(response: Any) -> str:
    try:
        return response.choices[0].message.content or ""
    except (AttributeError, IndexError, KeyError) as exc:
        raise LLMError(f"Unexpected LLM response shape: {response!r}") from exc


def _parse_json(content: str) -> dict[str, Any]:
    """Best-effort JSON extraction from a model response."""
    text = content.strip()
    # Strip common code fences
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        # Try to locate the first {...} block as a fallback
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise LLMError(f"Could not parse JSON from LLM output: {content!r}") from exc
