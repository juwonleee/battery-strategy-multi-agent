from __future__ import annotations

from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from config import AppConfig
from prompts import PromptBundle

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - handled at runtime when dependency is missing
    OpenAI = None


T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    """Raised when a structured OpenAI call cannot be completed."""


def create_openai_client(config: AppConfig) -> OpenAI:
    if OpenAI is None:
        raise StructuredOutputError(
            "openai is not installed. Run `pip install -r requirements.txt` first."
        )
    return _build_openai_client(config.openai_api_key, config.openai_timeout_seconds)


def invoke_structured_output(
    *,
    config: AppConfig,
    prompt: PromptBundle,
    response_model: type[T],
) -> T:
    client = create_openai_client(config)
    response = client.responses.parse(
        model=config.openai_model,
        instructions=prompt.instructions,
        input=prompt.input_text,
        text_format=response_model,
        max_output_tokens=config.openai_max_output_tokens,
    )
    parsed = getattr(response, "output_parsed", None)
    if parsed is None:
        raise StructuredOutputError(
            f"OpenAI returned no parsed output for prompt '{prompt.name}'."
        )
    return parsed


@lru_cache(maxsize=2)
def _build_openai_client(api_key: str, timeout_seconds: int) -> OpenAI:
    if OpenAI is None:
        raise StructuredOutputError(
            "openai is not installed. Run `pip install -r requirements.txt` first."
        )
    return OpenAI(api_key=api_key, timeout=timeout_seconds)
