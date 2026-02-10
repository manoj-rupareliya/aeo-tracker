"""
Google (Gemini) Adapter
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


class GoogleAdapter(BaseLLMAdapter):
    """Adapter for Google Gemini API"""

    API_BASE = "https://generativelanguage.googleapis.com/v1beta"

    MODELS = [
        "gemini-1.5-pro",
        "gemini-1.5-flash",
        "gemini-1.0-pro",
    ]

    # Cost per 1K tokens (USD) - varies by context length
    PRICING = {
        "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
        "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
        "gemini-1.0-pro": {"input": 0.0005, "output": 0.0015},
    }

    def __init__(self, api_key: Optional[str] = None, config: Optional[LLMConfig] = None):
        super().__init__(api_key or settings.GOOGLE_API_KEY, config)

    @property
    def provider(self) -> LLMProviderType:
        return LLMProviderType.GOOGLE

    @property
    def default_model(self) -> str:
        return settings.GOOGLE_DEFAULT_MODEL

    @property
    def available_models(self) -> List[str]:
        return self.MODELS

    def estimate_tokens(self, text: str) -> int:
        """Estimate tokens (rough approximation)"""
        # Gemini uses a similar tokenization approach
        return len(text) // 4

    def estimate_cost(self, input_tokens: int, output_tokens: int, model: Optional[str] = None) -> float:
        """Estimate cost based on token counts"""
        model = model or self.default_model
        pricing = self.PRICING.get(model, self.PRICING["gemini-1.5-pro"])
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
            messages.append(LLMMessage(role="user", content=system_prompt))
            messages.append(LLMMessage(role="model", content="Understood. I will follow these instructions."))
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

        # Convert messages to Gemini format
        contents = []
        system_instruction = None

        for msg in messages:
            if msg.role == "system":
                system_instruction = msg.content
            else:
                role = "user" if msg.role == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg.content}]
                })

        # Build request
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": cfg.temperature,
                "maxOutputTokens": cfg.max_tokens,
            }
        }

        if cfg.top_p is not None:
            payload["generationConfig"]["topP"] = cfg.top_p
        if cfg.stop_sequences:
            payload["generationConfig"]["stopSequences"] = cfg.stop_sequences
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        url = f"{self.API_BASE}/models/{cfg.model}:generateContent?key={self.api_key}"

        try:
            async with httpx.AsyncClient(timeout=cfg.timeout) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )

            response_time = datetime.utcnow()

            if response.status_code == 401 or response.status_code == 403:
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

            # Check for errors in response
            if "error" in data:
                raise LLMAdapterError(
                    data["error"].get("message", "Unknown error"),
                    self.provider,
                    {"error": data["error"]}
                )

            # Extract content
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMAdapterError(
                    "No response candidates returned",
                    self.provider,
                    {"response": data}
                )

            content = ""
            for part in candidates[0].get("content", {}).get("parts", []):
                if "text" in part:
                    content += part["text"]

            # Extract usage
            usage_metadata = data.get("usageMetadata", {})
            usage = LLMUsage(
                prompt_tokens=usage_metadata.get("promptTokenCount", 0),
                completion_tokens=usage_metadata.get("candidatesTokenCount", 0),
                total_tokens=usage_metadata.get("totalTokenCount", 0),
            )

            return LLMResponse(
                content=content,
                raw_response=data,
                provider=self.provider,
                model=cfg.model,
                finish_reason=candidates[0].get("finishReason"),
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
