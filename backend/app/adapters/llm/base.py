"""
Base LLM Adapter Interface
All LLM providers must implement this interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum


class LLMProviderType(str, Enum):
    """Supported LLM providers"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    PERPLEXITY = "perplexity"


@dataclass
class LLMConfig:
    """Configuration for LLM request"""
    model: str
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 60  # seconds
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop_sequences: Optional[List[str]] = None
    extra_params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMMessage:
    """A message in the conversation"""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMUsage:
    """Token usage information"""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class LLMResponse:
    """Standardized LLM response across all providers"""
    # Core response
    content: str
    raw_response: Dict[str, Any]  # Original response from provider

    # Metadata
    provider: LLMProviderType
    model: str
    finish_reason: Optional[str] = None

    # Usage & Cost
    usage: Optional[LLMUsage] = None
    estimated_cost_usd: Optional[float] = None

    # Timing
    request_time: Optional[datetime] = None
    response_time: Optional[datetime] = None
    latency_ms: Optional[int] = None

    # Citations (for Perplexity and similar)
    citations: List[str] = field(default_factory=list)

    # Error handling
    error: Optional[str] = None
    is_error: bool = False


class BaseLLMAdapter(ABC):
    """
    Abstract base class for LLM adapters.
    Each provider (OpenAI, Anthropic, Google, Perplexity) implements this interface.
    """

    def __init__(self, api_key: str, config: Optional[LLMConfig] = None):
        self.api_key = api_key
        self.config = config

    @property
    @abstractmethod
    def provider(self) -> LLMProviderType:
        """Return the provider type"""
        pass

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Return the default model for this provider"""
        pass

    @property
    @abstractmethod
    def available_models(self) -> List[str]:
        """Return list of available models"""
        pass

    @abstractmethod
    async def execute(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """
        Execute a prompt against the LLM.

        Args:
            prompt: The user prompt to send
            config: Optional configuration override
            system_prompt: Optional system prompt

        Returns:
            LLMResponse with standardized response data
        """
        pass

    @abstractmethod
    async def execute_chat(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """
        Execute a multi-turn chat conversation.

        Args:
            messages: List of messages in the conversation
            config: Optional configuration override

        Returns:
            LLMResponse with standardized response data
        """
        pass

    @abstractmethod
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        pass

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Estimate the cost of a request.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Estimated cost in USD
        """
        pass

    async def health_check(self) -> bool:
        """
        Check if the adapter can connect to the provider.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.execute("Say 'ok'", LLMConfig(
                model=self.default_model,
                max_tokens=10,
                temperature=0,
            ))
            return not response.is_error
        except Exception:
            return False

    def _calculate_latency(self, start: datetime, end: datetime) -> int:
        """Calculate latency in milliseconds"""
        return int((end - start).total_seconds() * 1000)


class LLMAdapterError(Exception):
    """Base exception for LLM adapter errors"""
    def __init__(self, message: str, provider: LLMProviderType, details: Optional[Dict] = None):
        super().__init__(message)
        self.provider = provider
        self.details = details or {}


class LLMRateLimitError(LLMAdapterError):
    """Rate limit exceeded"""
    pass


class LLMAuthenticationError(LLMAdapterError):
    """Authentication failed"""
    pass


class LLMTimeoutError(LLMAdapterError):
    """Request timed out"""
    pass


class LLMInvalidRequestError(LLMAdapterError):
    """Invalid request parameters"""
    pass
