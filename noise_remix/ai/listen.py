"""Gemini audio listening pass — song-aware notes for the plan provider."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from noise_remix.ai.config import AIConfig
from noise_remix.ai.gemini import (
    _developer_api_schema,
    _wait_for_file_active,
)
from noise_remix.ai.retry import call_with_retries
from noise_remix.errors import AIRequestError
from noise_remix.models.analysis import AudioAnalysis


class SalientMoment(BaseModel):
    time: float = Field(ge=0.0, description="Approx seconds into the track")
    label: str = Field(description="Short label, e.g. chorus drop, vocal entry")


class ListeningBrief(BaseModel):
    """Compact song-aware notes from Gemini listening to the source audio."""

    summary: str = Field(description="2–4 sentence overview of the track material")
    structure_notes: str = Field(
        default="",
        description="Form / arrangement description (intro, verse, chorus, etc.)",
    )
    salient_moments: list[SalientMoment] = Field(default_factory=list)
    preserve: str = Field(
        default="",
        description="Elements worth keeping recognizable",
    )
    destroy: str = Field(
        default="",
        description="Elements ripe for heavy transformation",
    )
    energy_curve: str = Field(
        default="",
        description="How energy evolves over the track",
    )


LISTEN_SYSTEM = """You are a careful music listener assisting Remixero, an experimental
audio remix tool. Listen to the attached audio and produce structured listening notes.

Focus on: instrumentation, vocals, density, rhythm, form, and where energy changes.
Be concrete and time-aware when possible. Do not write SuperCollider or executable code.
Do not invent remix processors — only describe what you hear.
"""


def generate_listening_brief(
    *,
    audio_path: Path,
    analysis: AudioAnalysis,
    instruction: str,
    config: AIConfig,
) -> ListeningBrief | None:
    """Ask Gemini to listen to the source audio and return notes, or None on failure."""
    if config.provider != "gemini" or not config.api_key:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return None

    client = genai.Client(api_key=config.api_key)
    user_prompt = (
        f"Creative remix instruction from the user:\n{instruction}\n\n"
        f"Local analysis (approx): duration={analysis.duration:.2f}s, "
        f"transients={len(analysis.transients)}, segments={len(analysis.segments)}, "
        f"estimated_bpm={analysis.estimated_bpm}, "
        f"spectral_flux={analysis.spectral_flux_label}, "
        f"centroid_hz={analysis.spectral_centroid_hz:.0f}.\n\n"
        "Listen to the attached audio and return listening notes JSON for the remix planner."
    )

    uploaded = None
    try:
        try:
            uploaded = client.files.upload(file=str(audio_path))
            uploaded = _wait_for_file_active(client, uploaded)
        except Exception:  # noqa: BLE001
            return None

        schema = _developer_api_schema(ListeningBrief)
        request_config = types.GenerateContentConfig(
            system_instruction=LISTEN_SYSTEM,
            response_mime_type="application/json",
            response_json_schema=schema,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

        def _once() -> object:
            try:
                return client.models.generate_content(
                    model=config.model,
                    contents=[user_prompt, uploaded],
                    config=request_config,
                )
            except Exception as exc:  # noqa: BLE001
                message = str(exc)
                if "NOT_FOUND" in message or "no longer available" in message:
                    raise AIRequestError(
                        f"Gemini listen failed: {exc}\n"
                        f"Configured model: {config.model}."
                    ) from exc
                raise

        response = call_with_retries(
            operation=_once,
            max_retries=min(config.max_retries, 3),
            retry_base_seconds=config.retry_base_seconds,
            retry_max_seconds=config.retry_max_seconds,
            provider_label="Gemini-listen",
        )
        return _parse_listening_brief(response)
    except Exception:  # noqa: BLE001
        return None
    finally:
        if uploaded is not None:
            try:
                name = getattr(uploaded, "name", None)
                if name:
                    client.files.delete(name=name)
            except Exception:  # noqa: BLE001
                pass


def listening_brief_as_prompt_block(brief: ListeningBrief) -> str:
    """Render a listening brief for inclusion in the plan-provider prompt."""
    moments = [
        {"time": moment.time, "label": moment.label}
        for moment in brief.salient_moments[:24]
    ]
    payload = {
        "summary": brief.summary,
        "structure_notes": brief.structure_notes,
        "salient_moments": moments,
        "preserve": brief.preserve,
        "destroy": brief.destroy,
        "energy_curve": brief.energy_curve,
    }
    return (
        "Gemini listening notes (from the actual source audio — honor these "
        "song-specific details while staying inside the DSP registry):\n"
        + json.dumps(payload, indent=2)
    )


def _parse_listening_brief(response: object) -> ListeningBrief | None:
    parsed = getattr(response, "parsed", None)
    if isinstance(parsed, ListeningBrief):
        return parsed
    if parsed is not None and hasattr(parsed, "model_dump"):
        try:
            return ListeningBrief.model_validate(parsed.model_dump())
        except Exception:  # noqa: BLE001
            pass
    if isinstance(parsed, dict):
        try:
            return ListeningBrief.model_validate(parsed)
        except Exception:  # noqa: BLE001
            pass
    text = getattr(response, "text", None)
    if not text:
        return None
    try:
        return ListeningBrief.model_validate(json.loads(text))
    except Exception:  # noqa: BLE001
        return None
