"""Provider-neutral creative director entrypoint."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from noise_remix.ai.config import AIConfig, load_gemini_listen_config
from noise_remix.ai.listen import ListeningBrief, generate_listening_brief
from noise_remix.errors import AIConfigError
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
    hybrid_listen: bool = False,
    status: Callable[[str], None] | None = None,
) -> ProductionPlan:
    """Dispatch to the configured AI provider.

    When ``hybrid_listen`` is True, planning with Groq, and a Gemini API key
    is available, run a Gemini audio-listen pass first and inject those notes
    into the plan prompt. Gemini plan mode already uploads audio, so the
    separate listen pass is always skipped there.
    """
    listening_brief: ListeningBrief | None = None
    if config.provider == "groq" and hybrid_listen:
        listening_brief = _maybe_gemini_listen(
            audio_path=audio_path,
            analysis=analysis,
            instruction=instruction,
            status=status,
        )
    elif config.provider == "gemini" and status is not None and hybrid_listen:
        status("Gemini plan mode listens via audio upload (separate listen skipped)")

    if config.provider == "gemini":
        from noise_remix.ai.gemini import generate_production_plan as gemini_plan

        return gemini_plan(
            audio_path=audio_path,
            analysis=analysis,
            instruction=instruction,
            duration_seconds=duration_seconds,
            config=config,
            variation_index=variation_index,
            variations=variations,
            upload_audio=upload_audio,
            listening_brief=listening_brief,
        )
    if config.provider == "groq":
        from noise_remix.ai.groq_client import generate_production_plan_groq

        return generate_production_plan_groq(
            audio_path=audio_path,
            analysis=analysis,
            instruction=instruction,
            duration_seconds=duration_seconds,
            config=config,
            variation_index=variation_index,
            variations=variations,
            upload_audio=upload_audio,
            listening_brief=listening_brief,
        )
    raise AIConfigError(f"Unsupported AI provider '{config.provider}'")


def _maybe_gemini_listen(
    *,
    audio_path: Path,
    analysis: AudioAnalysis,
    instruction: str,
    status: Callable[[str], None] | None,
) -> ListeningBrief | None:
    listen_config = load_gemini_listen_config()
    if listen_config is None:
        if status is not None:
            status("Listen skipped (no Gemini key)")
        return None
    if status is not None:
        status(
            f"Gemini listening pass (model={listen_config.model})…",
        )
    brief = generate_listening_brief(
        audio_path=audio_path,
        analysis=analysis,
        instruction=instruction,
        config=listen_config,
    )
    if status is not None:
        if brief is None:
            status("Listening notes unavailable; continuing with local analysis only")
        else:
            status("Listening notes attached for plan provider")
    return brief
