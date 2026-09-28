"""Shared parse → repair → validate pipeline for AI production plans."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

from noise_remix.ai.repair import parse_production_plan
from noise_remix.ai.validate import validate_production_plan
from noise_remix.errors import AIRequestError, ProductionPlanError
from noise_remix.models.analysis import AudioAnalysis
from noise_remix.models.production import ProductionPlan

# Extra attempts after the first response when the plan is incomplete/invalid.
MAX_PLAN_REPAIR_ATTEMPTS = 2


def finalize_plan_payload(
    payload: object,
    *,
    analysis: AudioAnalysis,
    duration_seconds: float,
) -> ProductionPlan:
    """Coerce raw JSON, Pydantic-validate, then semantically validate."""
    plan = parse_production_plan(
        payload,
        default_duration=min(duration_seconds, analysis.duration),
        default_primary_mode="destroy",
    )
    return validate_production_plan(
        plan,
        source_duration=analysis.duration,
        max_duration=duration_seconds,
    )


def extract_json_payload(text: str) -> object:
    """Parse JSON from a model response, tolerating markdown fences."""
    content = text.strip()
    if not content:
        raise AIRequestError("Model returned an empty production plan response.")
    if content.startswith("```"):
        lines = content.splitlines()
        # Drop opening fence and optional language tag, and closing fence.
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # Try to salvage the outermost object if the model added trailing noise.
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(content[start : end + 1])
            except json.JSONDecodeError as exc:
                raise AIRequestError(
                    "Model returned malformed JSON for the production plan."
                ) from exc
        raise AIRequestError(
            "Model returned malformed JSON for the production plan."
        )


def generate_plan_with_repairs(
    *,
    request_once: Callable[[str | None], object],
    extract_payload: Callable[[object], object],
    analysis: AudioAnalysis,
    duration_seconds: float,
    provider_label: str,
    max_attempts: int = MAX_PLAN_REPAIR_ATTEMPTS + 1,
) -> ProductionPlan:
    """Call the provider, repairing/retrying when plan validation fails."""
    correction: str | None = None
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        response = request_once(correction)
        try:
            payload = extract_payload(response)
            return finalize_plan_payload(
                payload,
                analysis=analysis,
                duration_seconds=duration_seconds,
            )
        except (ProductionPlanError, AIRequestError) as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            print(
                f"→ {provider_label} production plan invalid "
                f"(attempt {attempt}/{max_attempts}); asking for a corrected plan...",
                file=sys.stderr,
                flush=True,
            )
            correction = (
                "Your previous production plan was invalid and could not be used.\n"
                f"Validation error: {exc}\n\n"
                "Return a COMPLETE corrected JSON production plan that includes:\n"
                "- title, description, duration_seconds\n"
                "- global_parameters (overall_intensity, primary_mode, source_preservation)\n"
                "- sections (non-empty array; each with start, end, name, active_layers)\n"
                "- layers (non-empty array; each with id and processor)\n"
                "Rules:\n"
                "- every active_layers entry MUST be an exact layers[].id value\n"
                "- do not invent role names like 'coloring' unless that exact id exists\n"
                "- use only registry processors\n"
                "- respond with a single JSON object only"
            )
    assert last_error is not None
    raise ProductionPlanError(
        f"{provider_label} could not produce a valid production plan "
        f"after {max_attempts} attempts: {last_error}"
    ) from last_error


def payload_from_chat_response(response: object) -> object:
    try:
        content = response.choices[0].message.content  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        raise AIRequestError(f"Unexpected chat response shape: {exc}") from exc
    if not content:
        raise AIRequestError("Model returned an empty production plan response.")
    return extract_json_payload(content)


def payload_from_gemini_response(response: object) -> object:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, ProductionPlan):
        return parsed.model_dump()
    if parsed is not None and hasattr(parsed, "model_dump"):
        return parsed.model_dump()
    if isinstance(parsed, dict):
        return parsed
    text = getattr(response, "text", None)
    if not text:
        raise AIRequestError("Gemini returned an empty production plan response.")
    return extract_json_payload(text)
