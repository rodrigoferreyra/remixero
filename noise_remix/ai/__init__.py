"""Optional AI creative-director package."""

from noise_remix.ai.config import AIConfig, load_ai_config
from noise_remix.ai.director import generate_production_plan
from noise_remix.ai.registry import CAPABILITY_REGISTRY, registry_processor_names

__all__ = [
    "AIConfig",
    "CAPABILITY_REGISTRY",
    "generate_production_plan",
    "load_ai_config",
    "registry_processor_names",
]
