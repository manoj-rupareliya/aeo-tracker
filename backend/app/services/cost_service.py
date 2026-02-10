"""
Cost & Performance Governance Service
Minimize spend without losing insight quality

Mechanisms:
- Prompt Hash Caching: SHA-256(prompt + model + temp) → cached response
- Smart Scheduling: Spread queries to avoid rate limits
- Model-specific Limits: Different quotas per LLM provider
- Partial Results: Accept incomplete data gracefully
- Priority Queues: User-initiated > scheduled > background
"""

import hashlib
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
import json

from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import LLMProvider
from ..models.models_v2 import CostBudget, RateLimitState, CacheMetrics


class CostGovernanceService:
    """
    Service for managing costs and performance across LLM operations.
    """

    # Token costs per 1K tokens by provider (approximate, update as needed)
    TOKEN_COSTS = {
        LLMProvider.OPENAI: {"input": 0.003, "output": 0.006},
        LLMProvider.ANTHROPIC: {"input": 0.003, "output": 0.015},
        LLMProvider.GOOGLE: {"input": 0.00025, "output": 0.0005},
        LLMProvider.PERPLEXITY: {"input": 0.0007, "output": 0.0028},
    }

    # Default rate limits by provider
    DEFAULT_RATE_LIMITS = {
        LLMProvider.OPENAI: {
            "requests_per_minute": 60,
            "requests_per_hour": 3500,
            "tokens_per_minute": 90000,
        },
        LLMProvider.ANTHROPIC: {
            "requests_per_minute": 50,
            "requests_per_hour": 1000,
            "tokens_per_minute": 40000,
        },
        LLMProvider.GOOGLE: {
            "requests_per_minute": 60,
            "requests_per_hour": 1500,
            "tokens_per_minute": 32000,
        },
        LLMProvider.PERPLEXITY: {
            "requests_per_minute": 20,
            "requests_per_hour": 500,
            "tokens_per_minute": 20000,
        },
    }

    def __init__(self, db: AsyncSession, redis_client=None):
        self.db = db
        self.redis = redis_client  # Optional Redis for caching

    # =========================================================================
    # CACHE KEY GENERATION
    # =========================================================================

    def generate_cache_key(
        self,
        prompt: str,
        model: str,
        temperature: float,
        provider: LLMProvider,
    ) -> str:
        """
        Generate a unique cache key for a prompt.
        SHA-256(prompt + model + temp + provider)
        """
        key_content = f"{prompt}|{model}|{temperature}|{provider.value}"
        return hashlib.sha256(key_content.encode()).hexdigest()

    async def get_cached_response(
        self,
        cache_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a cached response if available."""
        if self.redis:
            cached = await self.redis.get(f"response:{cache_key}")
            if cached:
                return json.loads(cached)
        return None

    async def cache_response(
        self,
        cache_key: str,
        response: Dict[str, Any],
        ttl_days: int = 7,
    ) -> None:
        """Cache a response with TTL."""
        if self.redis:
            await self.redis.setex(
                f"response:{cache_key}",
                ttl_days * 24 * 60 * 60,  # Convert days to seconds
                json.dumps(response),
            )

    # =========================================================================
    # BUDGET MANAGEMENT
    # =========================================================================

    async def get_or_create_budget(
        self,
        project_id: UUID,
    ) -> CostBudget:
        """Get or create budget settings for a project."""
        result = await self.db.execute(
            select(CostBudget).where(CostBudget.project_id == project_id)
        )
        budget = result.scalar_one_or_none()

        if not budget:
            budget = CostBudget(
                project_id=project_id,
                daily_token_limit=100000,
                daily_cost_limit_usd=Decimal("10.00"),
                monthly_token_limit=2000000,
                monthly_cost_limit_usd=Decimal("200.00"),
            )
            self.db.add(budget)
            await self.db.flush()

        return budget

    async def check_budget(
        self,
        project_id: UUID,
        estimated_tokens: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if a request is within budget.
        Returns (allowed, reason_if_denied)
        """
        budget = await self.get_or_create_budget(project_id)

        # Check if paused
        if budget.is_paused:
            return False, f"Project paused: {budget.pause_reason}"

        # Check daily limits
        if budget.daily_token_limit:
            projected = (budget.tokens_used_today or 0) + estimated_tokens
            if projected > budget.daily_token_limit:
                return False, f"Daily token limit ({budget.daily_token_limit}) exceeded"

        if budget.daily_cost_limit_usd:
            if (budget.cost_today_usd or 0) >= budget.daily_cost_limit_usd:
                return False, f"Daily cost limit (${budget.daily_cost_limit_usd}) exceeded"

        # Check monthly limits
        if budget.monthly_token_limit:
            projected = (budget.tokens_used_this_month or 0) + estimated_tokens
            if projected > budget.monthly_token_limit:
                return False, f"Monthly token limit ({budget.monthly_token_limit}) exceeded"

        if budget.monthly_cost_limit_usd:
            if (budget.cost_this_month_usd or 0) >= budget.monthly_cost_limit_usd:
                return False, f"Monthly cost limit (${budget.monthly_cost_limit_usd}) exceeded"

        return True, None

    async def record_usage(
        self,
        project_id: UUID,
        tokens_used: int,
        cost_usd: Decimal,
    ) -> CostBudget:
        """Record token usage and cost against budget."""
        budget = await self.get_or_create_budget(project_id)

        # Reset daily counters if new day
        today = datetime.utcnow().date()
        if budget.last_daily_reset is None or budget.last_daily_reset.date() < today:
            budget.tokens_used_today = 0
            budget.cost_today_usd = Decimal("0")
            budget.last_daily_reset = datetime.utcnow()

        # Reset monthly counters if new month
        this_month = datetime.utcnow().replace(day=1).date()
        if budget.last_monthly_reset is None or budget.last_monthly_reset.date() < this_month:
            budget.tokens_used_this_month = 0
            budget.cost_this_month_usd = Decimal("0")
            budget.last_monthly_reset = datetime.utcnow()

        # Increment counters
        budget.tokens_used_today = (budget.tokens_used_today or 0) + tokens_used
        budget.cost_today_usd = (budget.cost_today_usd or Decimal("0")) + cost_usd
        budget.tokens_used_this_month = (budget.tokens_used_this_month or 0) + tokens_used
        budget.cost_this_month_usd = (budget.cost_this_month_usd or Decimal("0")) + cost_usd

        # Check if we should pause
        if budget.daily_cost_limit_usd and budget.cost_today_usd >= budget.daily_cost_limit_usd:
            budget.is_paused = True
            budget.paused_at = datetime.utcnow()
            budget.pause_reason = "Daily cost limit exceeded"
        elif budget.monthly_cost_limit_usd and budget.cost_this_month_usd >= budget.monthly_cost_limit_usd:
            budget.is_paused = True
            budget.paused_at = datetime.utcnow()
            budget.pause_reason = "Monthly cost limit exceeded"

        await self.db.flush()
        return budget

    async def update_budget_limits(
        self,
        project_id: UUID,
        daily_token_limit: Optional[int] = None,
        daily_cost_limit_usd: Optional[Decimal] = None,
        monthly_token_limit: Optional[int] = None,
        monthly_cost_limit_usd: Optional[Decimal] = None,
    ) -> CostBudget:
        """Update budget limits for a project."""
        budget = await self.get_or_create_budget(project_id)

        if daily_token_limit is not None:
            budget.daily_token_limit = daily_token_limit
        if daily_cost_limit_usd is not None:
            budget.daily_cost_limit_usd = daily_cost_limit_usd
        if monthly_token_limit is not None:
            budget.monthly_token_limit = monthly_token_limit
        if monthly_cost_limit_usd is not None:
            budget.monthly_cost_limit_usd = monthly_cost_limit_usd

        # Unpause if limits increased above current usage
        if budget.is_paused:
            budget.is_paused = False
            budget.pause_reason = None

        await self.db.flush()
        return budget

    async def unpause_project(
        self,
        project_id: UUID,
    ) -> CostBudget:
        """Manually unpause a project."""
        budget = await self.get_or_create_budget(project_id)
        budget.is_paused = False
        budget.pause_reason = None
        await self.db.flush()
        return budget

    # =========================================================================
    # RATE LIMIT MANAGEMENT
    # =========================================================================

    async def get_or_create_rate_limit_state(
        self,
        project_id: UUID,
        provider: LLMProvider,
    ) -> RateLimitState:
        """Get or create rate limit state for a project/provider combo."""
        result = await self.db.execute(
            select(RateLimitState).where(
                and_(
                    RateLimitState.project_id == project_id,
                    RateLimitState.provider == provider,
                )
            )
        )
        state = result.scalar_one_or_none()

        if not state:
            defaults = self.DEFAULT_RATE_LIMITS.get(provider, {})
            state = RateLimitState(
                project_id=project_id,
                provider=provider,
                requests_per_minute_limit=defaults.get("requests_per_minute", 10),
                requests_per_hour_limit=defaults.get("requests_per_hour", 100),
                tokens_per_minute_limit=defaults.get("tokens_per_minute", 40000),
            )
            self.db.add(state)
            await self.db.flush()

        return state

    async def check_rate_limit(
        self,
        project_id: UUID,
        provider: LLMProvider,
        estimated_tokens: int = 0,
    ) -> Tuple[bool, Optional[str], Optional[int]]:
        """
        Check if request is within rate limits.
        Returns (allowed, reason_if_denied, retry_after_seconds)
        """
        state = await self.get_or_create_rate_limit_state(project_id, provider)

        now = datetime.utcnow()

        # Check if currently rate limited
        if state.is_rate_limited and state.rate_limited_until:
            if now < state.rate_limited_until:
                retry_after = int((state.rate_limited_until - now).total_seconds())
                return False, "Rate limited", retry_after
            else:
                # Rate limit expired, reset
                state.is_rate_limited = False
                state.consecutive_429s = 0

        # Reset minute window if needed
        if state.minute_window_start is None or (now - state.minute_window_start).total_seconds() >= 60:
            state.requests_this_minute = 0
            state.tokens_this_minute = 0
            state.minute_window_start = now

        # Reset hour window if needed
        if state.hour_window_start is None or (now - state.hour_window_start).total_seconds() >= 3600:
            state.requests_this_hour = 0
            state.hour_window_start = now

        # Check limits
        if state.requests_this_minute >= state.requests_per_minute_limit:
            seconds_until_reset = 60 - int((now - state.minute_window_start).total_seconds())
            return False, "Requests per minute limit exceeded", seconds_until_reset

        if state.requests_this_hour >= state.requests_per_hour_limit:
            seconds_until_reset = 3600 - int((now - state.hour_window_start).total_seconds())
            return False, "Requests per hour limit exceeded", seconds_until_reset

        if estimated_tokens > 0 and (state.tokens_this_minute + estimated_tokens) > state.tokens_per_minute_limit:
            seconds_until_reset = 60 - int((now - state.minute_window_start).total_seconds())
            return False, "Tokens per minute limit exceeded", seconds_until_reset

        await self.db.flush()
        return True, None, None

    async def record_request(
        self,
        project_id: UUID,
        provider: LLMProvider,
        tokens_used: int,
    ) -> RateLimitState:
        """Record a request against rate limits."""
        state = await self.get_or_create_rate_limit_state(project_id, provider)

        state.requests_this_minute = (state.requests_this_minute or 0) + 1
        state.requests_this_hour = (state.requests_this_hour or 0) + 1
        state.tokens_this_minute = (state.tokens_this_minute or 0) + tokens_used

        await self.db.flush()
        return state

    async def record_rate_limit_error(
        self,
        project_id: UUID,
        provider: LLMProvider,
        retry_after_seconds: int = 60,
    ) -> RateLimitState:
        """Record a 429 rate limit error from the provider."""
        state = await self.get_or_create_rate_limit_state(project_id, provider)

        state.consecutive_429s = (state.consecutive_429s or 0) + 1
        state.is_rate_limited = True

        # Exponential backoff
        backoff = retry_after_seconds * (2 ** min(state.consecutive_429s - 1, 4))
        state.rate_limited_until = datetime.utcnow() + timedelta(seconds=backoff)

        await self.db.flush()
        return state

    # =========================================================================
    # CACHE METRICS
    # =========================================================================

    async def record_cache_hit(
        self,
        project_id: UUID,
        tokens_saved: int,
        provider: LLMProvider,
    ) -> None:
        """Record a cache hit."""
        await self._update_cache_metrics(project_id, hit=True, tokens_saved=tokens_saved, provider=provider)

    async def record_cache_miss(
        self,
        project_id: UUID,
    ) -> None:
        """Record a cache miss."""
        await self._update_cache_metrics(project_id, hit=False)

    async def _update_cache_metrics(
        self,
        project_id: UUID,
        hit: bool,
        tokens_saved: int = 0,
        provider: Optional[LLMProvider] = None,
    ) -> None:
        """Update cache metrics for today."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        result = await self.db.execute(
            select(CacheMetrics).where(
                and_(
                    CacheMetrics.project_id == project_id,
                    CacheMetrics.date == today,
                )
            )
        )
        metrics = result.scalar_one_or_none()

        if not metrics:
            metrics = CacheMetrics(
                project_id=project_id,
                date=today,
            )
            self.db.add(metrics)

        if hit:
            metrics.cache_hits = (metrics.cache_hits or 0) + 1
            metrics.tokens_saved = (metrics.tokens_saved or 0) + tokens_saved

            # Calculate cost saved
            if provider:
                costs = self.TOKEN_COSTS.get(provider, {"input": 0.003, "output": 0.006})
                avg_cost = (costs["input"] + costs["output"]) / 2
                saved = Decimal(str((tokens_saved / 1000) * avg_cost))
                metrics.estimated_cost_saved_usd = (
                    metrics.estimated_cost_saved_usd or Decimal("0")
                ) + saved
        else:
            metrics.cache_misses = (metrics.cache_misses or 0) + 1

        # Recalculate hit rate
        total = (metrics.cache_hits or 0) + (metrics.cache_misses or 0)
        if total > 0:
            metrics.hit_rate = (metrics.cache_hits or 0) / total

        await self.db.flush()

    async def get_cache_metrics(
        self,
        project_id: UUID,
        days: int = 30,
    ) -> List[CacheMetrics]:
        """Get cache metrics for a project."""
        start_date = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(CacheMetrics)
            .where(
                and_(
                    CacheMetrics.project_id == project_id,
                    CacheMetrics.date >= start_date,
                )
            )
            .order_by(CacheMetrics.date.asc())
        )
        return list(result.scalars().all())

    # =========================================================================
    # COST ESTIMATION
    # =========================================================================

    def estimate_cost(
        self,
        provider: LLMProvider,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> Decimal:
        """Estimate the cost of an LLM call."""
        costs = self.TOKEN_COSTS.get(provider, {"input": 0.003, "output": 0.006})
        input_cost = (prompt_tokens / 1000) * costs["input"]
        output_cost = (completion_tokens / 1000) * costs["output"]
        return Decimal(str(round(input_cost + output_cost, 6)))

    async def get_project_cost_summary(
        self,
        project_id: UUID,
    ) -> Dict[str, Any]:
        """Get cost summary for a project."""
        budget = await self.get_or_create_budget(project_id)
        cache_metrics = await self.get_cache_metrics(project_id, 30)

        total_saved = sum(
            (m.estimated_cost_saved_usd or Decimal("0")) for m in cache_metrics
        )
        total_hits = sum((m.cache_hits or 0) for m in cache_metrics)
        total_misses = sum((m.cache_misses or 0) for m in cache_metrics)

        return {
            "budget": {
                "daily_token_limit": budget.daily_token_limit,
                "daily_cost_limit_usd": float(budget.daily_cost_limit_usd) if budget.daily_cost_limit_usd else None,
                "monthly_token_limit": budget.monthly_token_limit,
                "monthly_cost_limit_usd": float(budget.monthly_cost_limit_usd) if budget.monthly_cost_limit_usd else None,
            },
            "usage": {
                "tokens_today": budget.tokens_used_today or 0,
                "cost_today_usd": float(budget.cost_today_usd) if budget.cost_today_usd else 0,
                "tokens_this_month": budget.tokens_used_this_month or 0,
                "cost_this_month_usd": float(budget.cost_this_month_usd) if budget.cost_this_month_usd else 0,
            },
            "status": {
                "is_paused": budget.is_paused,
                "pause_reason": budget.pause_reason,
            },
            "cache": {
                "total_hits_30d": total_hits,
                "total_misses_30d": total_misses,
                "hit_rate_30d": total_hits / (total_hits + total_misses) if (total_hits + total_misses) > 0 else 0,
                "estimated_savings_usd": float(total_saved),
            },
        }
