"""Groq creative-director client (official groq SDK, OpenAI-compatible chat)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from noise_remix.ai.config import AIConfig, require_api_key
from noise_remix.ai.groq_schema import GROQ_PRODUCTION_PLAN_SCHEMA
from noise_remix.ai.plan_parse import generate_plan_with_repairs, payload_from_chat_response
from noise_remix.ai.prompts import SYSTEM_INSTRUCTION, build_user_prompt
from noise_remix.ai.retry import call_with_retries
from noise_remix.errors import AIConfigError, AIRequestError
from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.production import ProductionPlan

# Prefer json_object: Groq json_schema often returns json_validate_failed
# (empty failed_generation) on large nested plans.
_DEFAULT_RESPONSE_MODE = "json_object"


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
        "Return ONLY valid JSON for the production plan schema.\n"
        "If the creative instruction is abstract (genre, mood, vibe), expand it into "
        "concrete sections/layers/processors yourself — do not leave it vague."
    )

    schema = GROQ_PRODUCTION_PLAN_SCHEMA
    # json_object is the reliable path; schema mode is attempted only if forced later.
    response_mode = _DEFAULT_RESPONSE_MODE

    def _request_once(correction: str | None) -> object:
        nonlocal response_mode
        user_content = prompt
        if correction:
            user_content = (
                prompt
                + "\n\n"
                + correction
                + "\nKeep the plan simpler if needed: 3–5 sections, 2–4 layers."
            )

        def _create(*, mode: str, temperature: float) -> object:
            if mode == "json_schema":
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
                    temperature=temperature,
                )
            return client.chat.completions.create(
                model=config.model,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_INSTRUCTION
                        + "\nRespond with a single JSON object only. "
                        "No markdown fences.",
                    },
                    {
                        "role": "user",
                        "content": user_content
                        + "\n\nRequired JSON shape (follow closely):\n"
                        + json.dumps(schema),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=temperature,
            )

        temperature = 0.4 if correction else 0.6

        def _once() -> object:
            return _create(mode=response_mode, temperature=temperature)

        try:
            return call_with_retries(
                operation=_once,
                max_retries=config.max_retries,
                retry_base_seconds=config.retry_base_seconds,
                retry_max_seconds=config.retry_max_seconds,
                provider_label="Groq",
            )
        except AIRequestError as exc:
            if not _looks_like_json_format_error(exc):
                raise
            # Flip mode and retry once.
            alt = "json_object" if response_mode == "json_schema" else "json_schema"
            if alt == response_mode:
                raise
            print(
                f"→ Groq {response_mode} response failed JSON validation; "
                f"retrying with {alt}...",
                file=sys.stderr,
                flush=True,
            )
            response_mode = alt

            def _alt_once() -> object:
                return _create(mode=response_mode, temperature=0.3)

            return call_with_retries(
                operation=_alt_once,
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
        instruction=instruction,
    )


def _looks_like_json_format_error(exc: Exception) -> bool:
    text = str(exc).lower()
    markers = (
        "json_validate_failed",
        "failed to validate json",
        "failed_generation",
        "json_schema",
        "response_format",
        "invalid_request",
        "invalid json",
        "schema",
        "unsupported",
        "not supported",
    )
    return any(marker in text for marker in markers)
