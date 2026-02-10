"""
LLM Adapters - Unified interface for multiple LLM providers
"""

from typing import Optional

from app.config import get_settings
from .base import (
    BaseLLMAdapter,
    LLMConfig,
    LLMMessage,
    LLMResponse,
    LLMUsage,
    LLMProviderType,
    LLMAdapterError,
    LLMRateLimitError,
    LLMAuthenticationError,
    LLMTimeoutError,
    LLMInvalidRequestError,
)
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .google_adapter import GoogleAdapter
from .perplexity_adapter import PerplexityAdapter

settings = get_settings()


def get_adapter(
    provider: str,
    api_key: Optional[str] = None,
    config: Optional[LLMConfig] = None
) -> BaseLLMAdapter:
    """
    Factory function to get the appropriate LLM adapter.

    Args:
        provider: One of "openai", "anthropic", "google", "perplexity"
        api_key: Optional API key (uses env var if not provided)
        config: Optional LLM configuration

    Returns:
        Configured LLM adapter instance

    Raises:
        ValueError: If provider is not supported
    """
    adapters = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "google": GoogleAdapter,
        "perplexity": PerplexityAdapter,
    }

    if provider not in adapters:
        raise ValueError(f"Unsupported provider: {provider}. Must be one of {list(adapters.keys())}")

    return adapters[provider](api_key=api_key, config=config)


def get_all_adapters(api_keys: Optional[dict] = None) -> dict[str, BaseLLMAdapter]:
    """
    Get adapters for all configured providers.

    Args:
        api_keys: Optional dict of {provider: api_key}

    Returns:
        Dict of {provider: adapter} for all providers with configured keys
    """
    api_keys = api_keys or {}
    adapters = {}

    provider_configs = [
        ("openai", settings.OPENAI_API_KEY),
        ("anthropic", settings.ANTHROPIC_API_KEY),
        ("google", settings.GOOGLE_API_KEY),
        ("perplexity", settings.PERPLEXITY_API_KEY),
    ]

    for provider, default_key in provider_configs:
        key = api_keys.get(provider) or default_key
        if key:
            adapters[provider] = get_adapter(provider, api_key=key)

    return adapters


__all__ = [
    # Factory
    "get_adapter",
    "get_all_adapters",
    # Base classes
    "BaseLLMAdapter",
    "LLMConfig",
    "LLMMessage",
    "LLMResponse",
    "LLMUsage",
    "LLMProviderType",
    # Exceptions
    "LLMAdapterError",
    "LLMRateLimitError",
    "LLMAuthenticationError",
    "LLMTimeoutError",
    "LLMInvalidRequestError",
    # Adapters
    "OpenAIAdapter",
    "AnthropicAdapter",
    "GoogleAdapter",
    "PerplexityAdapter",
]
