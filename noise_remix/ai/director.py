"""Provider-neutral creative director entrypoint."""

from __future__ import annotations

from pathlib import Path

from noise_remix.ai.config import AIConfig
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
) -> ProductionPlan:
    """Dispatch to the configured AI provider."""
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
        )
    raise AIConfigError(f"Unsupported AI provider '{config.provider}'")
