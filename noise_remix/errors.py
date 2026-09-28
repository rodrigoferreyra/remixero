"""Application-level exceptions with user-facing messages."""


class RemixeroError(Exception):
    """Base error for Remixero failures."""


class DependencyError(RemixeroError):
    """A required external tool is missing or unusable."""


class InputError(RemixeroError):
    """The input audio file is missing, unsupported, or invalid."""


class ConversionError(RemixeroError):
    """Audio conversion failed."""


class RenderError(RemixeroError):
    """SuperCollider rendering failed or produced no valid output."""


class OutputError(RemixeroError):
    """Output path preparation failed."""


class AIConfigError(RemixeroError):
    """AI provider is not configured or unavailable."""


class AIRequestError(RemixeroError):
    """The AI provider request failed."""


class ProductionPlanError(RemixeroError):
    """Production plan is missing, invalid, or unsafe."""
