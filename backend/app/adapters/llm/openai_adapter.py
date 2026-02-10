"""
OpenAI (ChatGPT) Adapter
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import tiktoken

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


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for OpenAI ChatGPT API"""

    API_BASE = "https://api.openai.com/v1"

    MODELS = [
        "gpt-4-turbo",
        "gpt-4-turbo-preview",
        "gpt-4",
        "gpt-4-32k",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k",
    ]

    # Cost per 1K tokens (USD)
    PRICING = {
        "gpt-4-turbo": {"input": 0.01, "output": 0.03},
        "gpt-4-turbo-preview": {"input": 0.01, "output": 0.03},
        "gpt-4": {"input": 0.03, "output": 0.06},
        "gpt-4-32k": {"input": 0.06, "output": 0.12},
        "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
        "gpt-3.5-turbo-16k": {"input": 0.003, "output": 0.004},
    }

    def __init__(self, api_key: Optional[str] = None, config: Optional[LLMConfig] = None):
        super().__init__(api_key or settings.OPENAI_API_KEY, config)
        self._tokenizer = None

    @property
    def provider(self) -> LLMProviderType:
        return LLMProviderType.OPENAI

    @property
    def default_model(self) -> str:
        return settings.OPENAI_DEFAULT_MODEL

    @property
    def available_models(self) -> List[str]:
        return self.MODELS

    def _get_tokenizer(self):
        """Get tiktoken encoder for token counting"""
        if self._tokenizer is None:
            try:
                self._tokenizer = tiktoken.encoding_for_model("gpt-4")
            except KeyError:
                self._tokenizer = tiktoken.get_encoding("cl100k_base")
        return self._tokenizer

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens using tiktoken"""
        encoder = self._get_tokenizer()
        return len(encoder.encode(text))

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: Optional[str] = None) -> float:
        """Estimate cost based on token counts"""
        model = model or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["gpt-4-turbo"])
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

        # Build request
        payload = {
            "model": cfg.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": cfg.temperature,
            "max_tokens": cfg.max_tokens,
        }

        if cfg.top_p is not None:
            payload["top_p"] = cfg.top_p
        if cfg.frequency_penalty is not None:
            payload["frequency_penalty"] = cfg.frequency_penalty
        if cfg.presence_penalty is not None:
            payload["presence_penalty"] = cfg.presence_penalty
        if cfg.stop_sequences:
            payload["stop"] = cfg.stop_sequences

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
