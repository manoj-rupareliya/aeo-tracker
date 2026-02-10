"""
Perplexity Adapter
Specialized for citation-rich responses
"""

from datetime import datetime
from typing import List, Optional

import httpx

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
)

settings = get_settings()


class PerplexityAdapter(BaseLLMAdapter):
    """
    Adapter for Perplexity API
    Perplexity is especially valuable for GEO because it natively
    provides source citations in responses.
    """

    API_BASE = "https://api.perplexity.ai"

    MODELS = [
        "llama-3.1-sonar-small-128k-online",
        "llama-3.1-sonar-large-128k-online",
        "llama-3.1-sonar-huge-128k-online",
    ]

    # Cost per 1K tokens (USD)
    PRICING = {
        "llama-3.1-sonar-small-128k-online": {"input": 0.0002, "output": 0.0002},
        "llama-3.1-sonar-large-128k-online": {"input": 0.001, "output": 0.001},
        "llama-3.1-sonar-huge-128k-online": {"input": 0.005, "output": 0.005},
    }

    def __init__(self, api_key: Optional[str] = None, config: Optional[LLMConfig] = None):
        super().__init__(api_key or settings.PERPLEXITY_API_KEY, config)

    @property
    def provider(self) -> LLMProviderType:
        return LLMProviderType.PERPLEXITY

    @property
    def default_model(self) -> str:
        return settings.PERPLEXITY_DEFAULT_MODEL

    @property
    def available_models(self) -> List[str]:
        return self.MODELS

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens (rough approximation)"""
        return len(text) // 4

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: Optional[str] = None) -> float:
        """Estimate cost based on token counts"""
        model = model or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["llama-3.1-sonar-large-128k-online"])
        input_cost = (input_tokens / 1000) * pricing["input"]
        output_cost = (output_tokens / 1000) * pricing["output"]
        return input_cost + output_cost

    async def execute(
        self,
        prompt: str,
        config: Optional[LLMConfig] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Execute a single prompt"""
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(role="user", content=prompt))
        return await self.execute_chat(messages, config)

    async def execute_chat(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Execute a chat conversation"""
        cfg = config or self.config or LLMConfig(model=self.default_model)
        request_time = datetime.utcnow()

        # Build request (Perplexity uses OpenAI-compatible format)
        payload = {
            "model": cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
            # Perplexity-specific: request citations
            "return_citations": True,
            "return_related_questions": False,
        }

        if cfg.top_p is not None:
            payload["top_p"] = cfg.top_p
        if cfg.frequency_penalty is not None:
            payload["frequency_penalty"] = cfg.frequency_penalty
        if cfg.presence_penalty is not None:
            payload["presence_penalty"] = cfg.presence_penalty

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=cfg.timeout) as client:
                response = await client.post(
                    f"{self.API_BASE}/chat/completions",
                    json=payload,
                    headers=headers,
                )

            response_time = datetime.utcnow()

            if response.status_code == 401:
                raise LLMAuthenticationError(
                    "Invalid API key",
                    self.provider,
                    {"status_code": response.status_code}
                )
            elif response.status_code == 429:
                raise LLMRateLimitError(
                    "Rate limit exceeded",
                    self.provider,
                    {"status_code": response.status_code}
                )
            elif response.status_code != 200:
                raise LLMAdapterError(
                    f"API error: {response.text}",
                    self.provider,
                    {"status_code": response.status_code, "response": response.text}
                )

            data = response.json()
            choice = data["choices"][0]
            usage_data = data.get("usage", {})

            usage = LLMUsage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )

            # Extract citations from Perplexity response
            # Perplexity returns citations in a special field
            citations = data.get("citations", [])

            return LLMResponse(
                content=choice["message"]["content"],
                raw_response=data,
                provider=self.provider,
                model=cfg.model,
                finish_reason=choice.get("finish_reason"),
                usage=usage,
                estimated_cost_usd=self.estimate_cost(
                    usage.prompt_tokens, usage.completion_tokens, cfg.model
                ),
                request_time=request_time,
                response_time=response_time,
                latency_ms=self._calculate_latency(request_time, response_time),
                citations=citations,  # Perplexity-specific
            )

        except httpx.TimeoutException:
            raise LLMTimeoutError(
                f"Request timed out after {cfg.timeout}s",
                self.provider,
            )
        except httpx.RequestError as e:
            raise LLMAdapterError(
                f"Request failed: {str(e)}",
                self.provider,
            )
