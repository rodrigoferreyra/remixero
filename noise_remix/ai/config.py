"""AI configuration (env + optional TOML). Never stores API keys in metadata."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

from noise_remix.errors import AIConfigError

DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
# Model with Structured Outputs support on Groq (override via REMIXERO_GROQ_MODEL).
DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
SUPPORTED_PROVIDERS = ("gemini", "groq")


class AIConfig(BaseModel):
    enabled: bool = False
    provider: str = "gemini"
    model: str = DEFAULT_GEMINI_MODEL
    api_key: str | None = Field(default=None, repr=False)
    max_retries: int = Field(default=5, ge=0, le=20)
    retry_base_seconds: float = Field(default=2.0, gt=0.0)
    retry_max_seconds: float = Field(default=45.0, gt=0.0)


def load_ai_config(
    config_path: Path | None = None,
    *,
    provider_override: str | None = None,
) -> AIConfig:
    """Load AI settings from optional TOML and environment overrides."""
    data: dict = {}
    path = config_path or Path("remixero.toml")
    if path.is_file():
        with path.open("rb") as handle:
            parsed = tomllib.load(handle)
        data = dict(parsed.get("ai") or {})

    provider = (
        provider_override
        or os.environ.get("REMIXERO_AI_PROVIDER")
        or data.get("provider")
        or _auto_provider()
    )
    provider = str(provider).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise AIConfigError(
            f"Unsupported AI provider '{provider}'. "
            f"Supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )

    if provider == "groq":
        env_key = os.environ.get("GROQ_API_KEY")
        model = (
            os.environ.get("REMIXERO_GROQ_MODEL")
            or data.get("groq_model")
            or data.get("model")
            or DEFAULT_GROQ_MODEL
        )
    else:
        env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        model = (
            os.environ.get("REMIXERO_GEMINI_MODEL")
            or data.get("gemini_model")
            or data.get("model")
            or DEFAULT_GEMINI_MODEL
        )

    enabled = bool(data.get("enabled", False))
    max_retries = _env_int("REMIXERO_AI_MAX_RETRIES", data.get("max_retries"), 5)
    # Keep older Gemini-specific env names working.
    if os.environ.get("REMIXERO_GEMINI_MAX_RETRIES"):
        max_retries = _env_int("REMIXERO_GEMINI_MAX_RETRIES", None, max_retries)
    retry_base = _env_float(
        "REMIXERO_AI_RETRY_BASE",
        data.get("retry_base_seconds"),
        2.0,
    )
    if os.environ.get("REMIXERO_GEMINI_RETRY_BASE"):
        retry_base = _env_float("REMIXERO_GEMINI_RETRY_BASE", None, retry_base)
    retry_max = _env_float(
        "REMIXERO_AI_RETRY_MAX",
        data.get("retry_max_seconds"),
        45.0,
    )
    if os.environ.get("REMIXERO_GEMINI_RETRY_MAX"):
        retry_max = _env_float("REMIXERO_GEMINI_RETRY_MAX", None, retry_max)

    return AIConfig(
        enabled=enabled,
        provider=provider,
        model=str(model),
        api_key=env_key,
        max_retries=max(0, max_retries),
        retry_base_seconds=max(0.1, retry_base),
        retry_max_seconds=max(0.1, retry_max),
    )


def gemini_api_key() -> str | None:
    """Return the Gemini/Google API key from the environment, if set."""
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key is None:
        return None
    key = key.strip()
    return key or None


def gemini_api_key_available() -> bool:
    return gemini_api_key() is not None


def load_gemini_listen_config(config_path: Path | None = None) -> AIConfig | None:
    """Load a Gemini-provider config used only for the audio listening pass.

    Returns None when no Gemini key is available (listen step should be skipped).
    """
    key = gemini_api_key()
    if not key:
        return None

    data: dict = {}
    path = config_path or Path("remixero.toml")
    if path.is_file():
        with path.open("rb") as handle:
            parsed = tomllib.load(handle)
        data = dict(parsed.get("ai") or {})

    model = (
        os.environ.get("REMIXERO_GEMINI_MODEL")
        or data.get("gemini_model")
        or data.get("model")
        or DEFAULT_GEMINI_MODEL
    )
    max_retries = _env_int("REMIXERO_AI_MAX_RETRIES", data.get("max_retries"), 5)
    if os.environ.get("REMIXERO_GEMINI_MAX_RETRIES"):
        max_retries = _env_int("REMIXERO_GEMINI_MAX_RETRIES", None, max_retries)
    retry_base = _env_float(
        "REMIXERO_AI_RETRY_BASE",
        data.get("retry_base_seconds"),
        2.0,
    )
    if os.environ.get("REMIXERO_GEMINI_RETRY_BASE"):
        retry_base = _env_float("REMIXERO_GEMINI_RETRY_BASE", None, retry_base)
    retry_max = _env_float(
        "REMIXERO_AI_RETRY_MAX",
        data.get("retry_max_seconds"),
        45.0,
    )
    if os.environ.get("REMIXERO_GEMINI_RETRY_MAX"):
        retry_max = _env_float("REMIXERO_GEMINI_RETRY_MAX", None, retry_max)

    return AIConfig(
        enabled=True,
        provider="gemini",
        model=str(model),
        api_key=key,
        max_retries=max(0, max_retries),
        retry_base_seconds=max(0.1, retry_base),
        retry_max_seconds=max(0.1, retry_max),
    )


def require_api_key(config: AIConfig) -> str:
    if config.provider == "gemini":
        env_name = "GEMINI_API_KEY"
    elif config.provider == "groq":
        env_name = "GROQ_API_KEY"
    else:
        raise AIConfigError(
            f"Unsupported AI provider '{config.provider}'. "
            f"Supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )
    if not config.api_key:
        raise AIConfigError(
            f"{env_name} is not set. Export {env_name} before using --ai/--prompt "
            f"with provider={config.provider}."
        )
    return config.api_key


# Backwards-compatible alias
def require_gemini_api_key(config: AIConfig) -> str:
    if config.provider != "gemini":
        raise AIConfigError(
            f"require_gemini_api_key called with provider={config.provider}"
        )
    return require_api_key(config)


def _auto_provider() -> str:
    """Prefer an explicitly available key; default to gemini."""
    if os.environ.get("GROQ_API_KEY") and not (
        os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    ):
        return "groq"
    return "gemini"


def _env_int(name: str, configured: object, default: int) -> int:
    raw = os.environ.get(name)
    if raw is not None and raw.strip():
        return int(raw)
    if configured is not None:
        return int(configured)  # type: ignore[arg-type]
    return default


def _env_float(name: str, configured: object, default: float) -> float:
    raw = os.environ.get(name)
    if raw is not None and raw.strip():
        return float(raw)
    if configured is not None:
        return float(configured)  # type: ignore[arg-type]
    return default
