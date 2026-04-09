"""
models_registry.py — Single source of truth for all known Gemini models.

To add a new model: append an entry to KNOWN_MODELS following the same shape.
"""

KNOWN_MODELS: dict[str, dict] = {
    "gemini-3-flash-preview": {
        "display_name": "Gemini 3 Flash Preview",
        "context_limit": 1_048_576,
        "tier": "flash",
    },
    "gemini-3.1-pro-preview": {
        "display_name": "Gemini 3.1 Pro Preview",
        "context_limit": 1_048_576,
        "tier": "pro",
    },
    "gemini-1.5-pro": {
        "display_name": "Gemini 1.5 Pro",
        "context_limit": 2_097_152,
        "tier": "pro",
    },
    "gemini-1.5-flash": {
        "display_name": "Gemini 1.5 Flash",
        "context_limit": 1_048_576,
        "tier": "flash",
    },
    "gemini-1.5-flash-8b": {
        "display_name": "Gemini 1.5 Flash 8B",
        "context_limit": 1_048_576,
        "tier": "flash",
    },
    "gemini-2.0-flash": {
        "display_name": "Gemini 2.0 Flash",
        "context_limit": 1_048_576,
        "tier": "flash",
    },
    "gemini-2.0-pro": {
        "display_name": "Gemini 2.0 Pro",
        "context_limit": 2_097_152,
        "tier": "pro",
    },
}

# Fallback values for session models not found in the registry
DEFAULT_CONTEXT_LIMIT = 1_048_576
DEFAULT_TIER = "unknown"


def get_model_info(model_id: str) -> dict:
    """Returns registry info for a model, or a fallback dict if unknown."""
    if model_id in KNOWN_MODELS:
        return KNOWN_MODELS[model_id]
    return {
        "display_name": model_id.replace("-", " ").replace("_", " ").title(),
        "context_limit": DEFAULT_CONTEXT_LIMIT,
        "tier": DEFAULT_TIER,
    }
