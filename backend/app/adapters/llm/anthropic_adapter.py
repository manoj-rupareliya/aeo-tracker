"""
Anthropic (Claude) Adapter
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


class AnthropicAdapter(BaseLLMAdapter):
    """Adapter for Anthropic Claude API"""

    API_BASE = "https://api.anthropic.com/v1"
    API_VERSION = "2023-06-01"

    MODELS = [
        "claude-3-opus-20240229",
        "claude-3-sonnet-20240229",
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20241022",
    ]

    # Cost per 1K tokens (USD)
    PRICING = {
        "claude-3-opus-20240229": {"input": 0.015, "output": 0.075},
        "claude-3-sonnet-20240229": {"input": 0.003, "output": 0.015},
        "claude-3-haiku-20240307": {"input": 0.00025, "output": 0.00125},
        "claude-3-5-sonnet-20241022": {"input": 0.003, "output": 0.015},
    }

    def __init__(self, api_key: Optional[str] = None, config: Optional[LLMConfig] = None):
        super().__init__(api_key or settings.ANTHROPIC_API_KEY, config)

    @property
    def provider(self) -> LLMProviderType:
        return LLMProviderType.ANTHROPIC

    @property
    def default_model(self) -> str:
        return settings.ANTHROPIC_DEFAULT_MODEL

    @property
    def available_models(self) -> List[str]:
        return self.MODELS

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens (rough approximation - Claude uses similar tokenization to GPT)"""
        # Claude's tokenizer is similar to GPT-4's
        # Rough estimate: ~4 characters per token for English
        return len(text) // 4

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: Optional[str] = None) -> float:
        """Estimate cost based on token counts"""
        model = model or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["claude-3-opus-20240229"])
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
        messages = [LLMMessage(role="user", content=prompt)]
        return await self._execute_with_system(messages, system_prompt, config)

    async def execute_chat(
        self,
        messages: List[LLMMessage],
        config: Optional[LLMConfig] = None,
    ) -> LLMResponse:
        """Execute a chat conversation"""
        # Extract system message if present
        system_prompt = None
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system_prompt = msg.content
            else:
                chat_messages.append(msg)
        return await self._execute_with_system(chat_messages, system_prompt, config)

    async def _execute_with_system(
        self,
        messages: List[LLMMessage],
        system_prompt: Optional[str],
        config: Optional[LLMConfig],
    ) -> LLMResponse:
        """Execute with optional system prompt"""
        cfg = config or self.config or LLMConfig(model=self.default_model)
        request_time = datetime.utcnow()

        # Build request
        payload = {
            "model": cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_tokens": cfg.max_tokens,
            "temperature": cfg.temperature,
        }

        if system_prompt:
            payload["system"] = system_prompt

        if cfg.top_p is not None:
            payload["top_p"] = cfg.top_p
        if cfg.stop_sequences:
            payload["stop_sequences"] = cfg.stop_sequences

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": self.API_VERSION,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=cfg.timeout) as client:
                response = await client.post(
                    f"{self.API_BASE}/messages",
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

            # Extract content from response
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")

            # Extract usage
            usage_data = data.get("usage", {})
            usage = LLMUsage(
                prompt_tokens=usage_data.get("input_tokens", 0),
                completion_tokens=usage_data.get("output_tokens", 0),
                total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
            )

            return LLMResponse(
                content=content,
                raw_response=data,
                provider=self.provider,
                model=cfg.model,
                finish_reason=data.get("stop_reason"),
                usage=usage,
                estimated_cost_usd=self.estimate_cost(
                    usage.prompt_tokens, usage.completion_tokens, cfg.model
                ),
                request_time=request_time,
                response_time=response_time,
                latency_ms=self._calculate_latency(request_time, response_time),
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
