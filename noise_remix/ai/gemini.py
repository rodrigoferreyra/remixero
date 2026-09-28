"""Gemini creative-director client (google-genai SDK)."""

from __future__ import annotations

import time
from pathlib import Path

from noise_remix.ai.config import AIConfig, require_api_key
from noise_remix.ai.plan_parse import (
    generate_plan_with_repairs,
    payload_from_gemini_response,
)
from noise_remix.ai.prompts import SYSTEM_INSTRUCTION, build_user_prompt
from noise_remix.ai.retry import call_with_retries
from noise_remix.errors import AIConfigError, AIRequestError
from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.production import ProductionPlan


def generate_production_plan(
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
    """Ask Gemini for a structured ProductionPlan and validate it."""
    api_key = require_api_key(config)
    if config.provider != "gemini":
        raise AIConfigError(f"Gemini client invoked with provider={config.provider}")

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise AIConfigError(
            "google-genai is not installed. Install the AI extra: "
            'pip install "remixero[ai]" or pip install google-genai'
        ) from exc

    client = genai.Client(api_key=api_key)
    prompt = build_user_prompt(
        instruction=instruction,
        analysis=analysis,
        duration_seconds=duration_seconds,
        variation_index=variation_index,
        variations=variations,
    )

    base_contents: list = [prompt]
    uploaded = None
    if upload_audio:
        try:
            uploaded = client.files.upload(file=str(audio_path))
            uploaded = _wait_for_file_active(client, uploaded)
            base_contents = [prompt, uploaded]
        except Exception as exc:  # noqa: BLE001
            base_contents = [
                prompt
                + "\n\n(Note: audio upload failed; rely on local analysis only.)\n"
                + f"Upload error: {exc}"
            ]

    schema = _developer_api_schema(ProductionPlan)
    request_config = types.GenerateContentConfig(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_json_schema=schema,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            disable=True
        ),
    )

    def _request_once(correction: str | None) -> object:
        contents = list(base_contents)
        if correction:
            contents = [*base_contents, correction]

        def _once() -> object:
            try:
                return client.models.generate_content(
                    model=config.model,
                    contents=contents,
                    config=request_config,
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                if "NOT_FOUND" in message or "no longer available" in message:
                    raise AIRequestError(
                        f"Gemini request failed: {exc}\n"
                        f"Configured model: {config.model}. "
                        "Set a current model with REMIXERO_GEMINI_MODEL or "
                        "[ai].gemini_model in remixero.toml (default is gemini-3.8-flash)."
                    ) from exc
                raise

        return call_with_retries(
            operation=_once,
            max_retries=config.max_retries,
            retry_base_seconds=config.retry_base_seconds,
            retry_max_seconds=config.retry_max_seconds,
            provider_label="Gemini",
        )

    try:
        return generate_plan_with_repairs(
            request_once=_request_once,
            extract_payload=payload_from_gemini_response,
            analysis=analysis,
            duration_seconds=duration_seconds,
            provider_label="Gemini",
        )
    finally:
        if uploaded is not None:
            try:
                name = getattr(uploaded, "name", None)
                if name:
                    client.files.delete(name=name)
            except Exception:  # noqa: BLE001
                pass


def _wait_for_file_active(client: object, uploaded: object, *, timeout: float = 60.0):
    """Poll Files API until the upload is ACTIVE when state is exposed."""
    deadline = time.time() + timeout
    current = uploaded
    while time.time() < deadline:
        state = getattr(current, "state", None)
        state_name = getattr(state, "name", None) or str(state or "")
        if not state_name or state_name.upper() in {"ACTIVE", "STATE_UNSPECIFIED"}:
            return current
        if state_name.upper() in {"FAILED", "ERROR"}:
            raise AIRequestError(f"Gemini file upload failed with state {state_name}")
        name = getattr(current, "name", None)
        if not name:
            return current
        time.sleep(0.5)
        current = client.files.get(name=name)  # type: ignore[attr-defined]
    return current


def _developer_api_schema(model_cls: type) -> dict:
    """Build a JSON schema compatible with Gemini Developer API structured output.

    Pydantic often emits ``additionalProperties``, which the Developer API rejects
    (Enterprise Agent Platform only). Strip those keys while keeping the schema
    otherwise intact, and pass it via ``response_json_schema``.
    """
    schema = model_cls.model_json_schema()
    return _strip_unsupported_schema_keys(schema)


def _strip_unsupported_schema_keys(node: object) -> object:
    if isinstance(node, dict):
        cleaned: dict = {}
        for key, value in node.items():
            if key in {"additionalProperties", "additional_properties"}:
                continue
            cleaned[key] = _strip_unsupported_schema_keys(value)
        return cleaned
    if isinstance(node, list):
        return [_strip_unsupported_schema_keys(item) for item in node]
    return node
