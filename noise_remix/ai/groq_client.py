"""Groq creative-director client (official groq SDK, OpenAI-compatible chat)."""

from __future__ import annotations

import json
from pathlib import Path

from noise_remix.ai.config import AIConfig, require_api_key
from noise_remix.ai.plan_parse import generate_plan_with_repairs, payload_from_chat_response
from noise_remix.ai.prompts import SYSTEM_INSTRUCTION, build_user_prompt
from noise_remix.ai.retry import call_with_retries
from noise_remix.errors import AIConfigError, AIRequestError
from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.production import ProductionPlan


def generate_production_plan_groq(
    *,
    audio_path: Path,
    analysis: AudioAnalysis,
    instruction: str,
    duration_seconds: float,
    config: AIConfig,
    variation_index: int = 0,
    variations: int = 1,
    upload_audio: bool = True,
) -> ProductionPlan:
    """Ask Groq for a structured ProductionPlan and validate it.

    Groq chat models do not ingest the source audio the way Gemini Files API does.
    Local deterministic analysis is provided in the prompt instead. ``upload_audio``
    is accepted for API symmetry and ignored.
    """
    del audio_path, upload_audio  # analysis-only context for Groq
    api_key = require_api_key(config)
    if config.provider != "groq":
        raise AIConfigError(f"Groq client invoked with provider={config.provider}")

    try:
        from groq import Groq
    except ImportError as exc:
        raise AIConfigError(
            "groq is not installed. Install the AI extra: "
            'pip install "remixero[ai]" or pip install groq'
        ) from exc

    client = Groq(api_key=api_key)
    prompt = build_user_prompt(
        instruction=instruction,
        analysis=analysis,
        duration_seconds=duration_seconds,
        variation_index=variation_index,
        variations=variations,
    )
    prompt += (
        "\n\nProvider note: audio bytes are not attached on Groq; "
        "rely on the local analysis JSON above.\n"
        "Return ONLY valid JSON for the production plan schema."
    )

    schema = _groq_json_schema(ProductionPlan)
    use_json_object = False

    def _request_once(correction: str | None) -> object:
        nonlocal use_json_object
        user_content = prompt
        if correction:
            user_content = prompt + "\n\n" + correction

        def _json_schema_once() -> object:
            return client.chat.completions.create(
                model=config.model,
                messages=[
                    {"role": "system", "content": SYSTEM_INSTRUCTION},
                    {"role": "user", "content": user_content},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "production_plan",
                        "strict": False,
                        "schema": schema,
                    },
                },
                temperature=0.7,
            )

        def _json_object_once() -> object:
            return client.chat.completions.create(
                model=config.model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_INSTRUCTION
                        + "\nRespond with a single JSON object only.",
                    },
                    {
                        "role": "user",
                        "content": user_content
                        + "\n\nJSON schema (follow closely):\n"
                        + json.dumps(schema),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )

        operation = _json_object_once if use_json_object else _json_schema_once
        try:
            return call_with_retries(
                operation=operation,
                max_retries=config.max_retries,
                retry_base_seconds=config.retry_base_seconds,
                retry_max_seconds=config.retry_max_seconds,
                provider_label="Groq",
            )
        except AIRequestError as exc:
            if use_json_object or not _looks_like_format_error(exc):
                raise
            use_json_object = True
            return call_with_retries(
                operation=_json_object_once,
                max_retries=config.max_retries,
                retry_base_seconds=config.retry_base_seconds,
                retry_max_seconds=config.retry_max_seconds,
                provider_label="Groq",
            )

    return generate_plan_with_repairs(
        request_once=_request_once,
        extract_payload=payload_from_chat_response,
        analysis=analysis,
        duration_seconds=duration_seconds,
        provider_label="Groq",
    )


def _looks_like_format_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "json_schema",
        "response_format",
        "invalid_request",
        "400",
        "schema",
        "unsupported",
        "not supported",
    )
    return any(marker in text for marker in markers)


def _groq_json_schema(model_cls: type) -> dict:
    """Prepare a JSON schema suitable for Groq structured outputs."""
    schema = model_cls.model_json_schema()
    return _normalize_schema(schema)


def _normalize_schema(node: object) -> object:
    if isinstance(node, dict):
        cleaned: dict = {}
        for key, value in node.items():
            if key in {"title", "examples", "default"}:
                continue
            cleaned[key] = _normalize_schema(value)
        if cleaned.get("type") == "object" and "additionalProperties" not in cleaned:
            cleaned["additionalProperties"] = False
        return cleaned
    if isinstance(node, list):
        return [_normalize_schema(item) for item in node]
    return node
