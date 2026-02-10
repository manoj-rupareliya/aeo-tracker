"""
Share of AI Voice (SAIV) Engine
Quantifies brand presence in AI-generated content

Formula: SAIV = (Brand Mentions in AI Responses) / (Total Entity Mentions) × 100

Properties:
- Reproducible (same inputs = same output)
- Transparent (calculation visible)
- Comparable (relative to competitors)
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID
from collections import defaultdict

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import LLMProvider, LLMRun, LLMResponse, BrandMention
from ..models.models_v2 import SAIVSnapshot, SAIVBreakdown


class SAIVEngine:
    """
    Engine for calculating and tracking Share of AI Voice metrics.

    SAIV represents the percentage of total brand/entity mentions
    that belong to your brand in LLM responses.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # SAIV CALCULATION
    # =========================================================================

    async def calculate_saiv(
        self,
        project_id: UUID,
        start_date: datetime,
        end_date: datetime,
        period_type: str = "daily",
    ) -> SAIVSnapshot:
        """
        Calculate SAIV for a project over a time period.

        Formula: SAIV = (Own Brand Mentions) / (Total Entity Mentions) × 100
        """
        # Get all runs in the period
        result = await self.db.execute(
            select(LLMRun).where(
                and_(
                    LLMRun.project_id == project_id,
                    LLMRun.created_at >= start_date,
                    LLMRun.created_at <= end_date,
                )
            )
        )
        runs = list(result.scalars().all())

        if not runs:
            return None

        run_ids = [r.id for r in runs]

        # Count own brand mentions
        result = await self.db.execute(
            select(func.count(BrandMention.id))
            .join(LLMResponse)
            .where(
                and_(
                    LLMResponse.llm_run_id.in_(run_ids),
                    BrandMention.is_own_brand == True,
                )
            )
        )
        own_brand_mentions = result.scalar() or 0

        # Count total entity mentions (all brands)
        result = await self.db.execute(
            select(func.count(BrandMention.id))
            .join(LLMResponse)
            .where(LLMResponse.llm_run_id.in_(run_ids))
        )
        total_mentions = result.scalar() or 0

        # Calculate overall SAIV
        overall_saiv = 0.0
        if total_mentions > 0:
            overall_saiv = (own_brand_mentions / total_mentions) * 100

        # Calculate SAIV by LLM provider
        saiv_by_llm = await self._calculate_saiv_by_llm(run_ids)

        # Calculate competitor SAIV
        competitor_saiv = await self._calculate_competitor_saiv(run_ids, total_mentions)

        # Get previous snapshot for delta calculation
        result = await self.db.execute(
            select(SAIVSnapshot)
            .where(
                and_(
                    SAIVSnapshot.project_id == project_id,
                    SAIVSnapshot.period_type == period_type,
                    SAIVSnapshot.snapshot_date < start_date,
                )
            )
            .order_by(SAIVSnapshot.snapshot_date.desc())
            .limit(1)
        )
        previous = result.scalar_one_or_none()

        saiv_delta = None
        trend_direction = "stable"
        if previous:
            saiv_delta = overall_saiv - previous.overall_saiv
            if saiv_delta > 1:
                trend_direction = "up"
            elif saiv_delta < -1:
                trend_direction = "down"

        # Create snapshot
        snapshot = SAIVSnapshot(
            project_id=project_id,
            snapshot_date=end_date,
            period_type=period_type,
            overall_saiv=overall_saiv,
            total_brand_mentions=own_brand_mentions,
            total_entity_mentions=total_mentions,
            saiv_by_llm=saiv_by_llm,
            competitor_saiv=competitor_saiv,
            saiv_delta=saiv_delta,
            trend_direction=trend_direction,
            runs_analyzed=len(runs),
            calculation_method="standard",
        )

        self.db.add(snapshot)
        await self.db.flush()

        # Create breakdowns
        await self._create_saiv_breakdowns(snapshot.id, run_ids)

        return snapshot

    async def _calculate_saiv_by_llm(
        self,
        run_ids: List[UUID],
    ) -> Dict[str, float]:
        """Calculate SAIV broken down by LLM provider."""
        # Get runs grouped by provider
        result = await self.db.execute(
            select(LLMRun.provider, LLMRun.id).where(LLMRun.id.in_(run_ids))
        )
        runs_by_provider = defaultdict(list)
        for provider, run_id in result.all():
            runs_by_provider[provider].append(run_id)

        saiv_by_llm = {}
        for provider, provider_run_ids in runs_by_provider.items():
            # Own brand mentions for this provider
            result = await self.db.execute(
                select(func.count(BrandMention.id))
                .join(LLMResponse)
                .where(
                    and_(
                        LLMResponse.llm_run_id.in_(provider_run_ids),
                        BrandMention.is_own_brand == True,
                    )
                )
            )
            own_mentions = result.scalar() or 0

            # Total mentions for this provider
            result = await self.db.execute(
                select(func.count(BrandMention.id))
                .join(LLMResponse)
                .where(LLMResponse.llm_run_id.in_(provider_run_ids))
            )
            total_mentions = result.scalar() or 0

            if total_mentions > 0:
                saiv_by_llm[provider.value] = (own_mentions / total_mentions) * 100
            else:
                saiv_by_llm[provider.value] = 0.0

        return saiv_by_llm

    async def _calculate_competitor_saiv(
        self,
        run_ids: List[UUID],
        total_mentions: int,
    ) -> Dict[str, float]:
        """Calculate SAIV for each competitor."""
        if total_mentions == 0:
            return {}

        result = await self.db.execute(
            select(
                BrandMention.brand_name,
                func.count(BrandMention.id),
            )
            .join(LLMResponse)
            .where(
                and_(
                    LLMResponse.llm_run_id.in_(run_ids),
                    BrandMention.is_own_brand == False,
                )
            )
            .group_by(BrandMention.brand_name)
        )

        competitor_saiv = {}
        for brand_name, count in result.all():
            competitor_saiv[brand_name] = (count / total_mentions) * 100

        return competitor_saiv

    async def _create_saiv_breakdowns(
        self,
        snapshot_id: UUID,
        run_ids: List[UUID],
    ) -> None:
        """Create detailed SAIV breakdowns by dimension."""
        # Breakdown by LLM provider
        result = await self.db.execute(
            select(LLMRun.provider, LLMRun.id).where(LLMRun.id.in_(run_ids))
        )
        runs_by_provider = defaultdict(list)
        for provider, run_id in result.all():
            runs_by_provider[provider].append(run_id)

        for provider, provider_run_ids in runs_by_provider.items():
            # Get counts for this provider
            result = await self.db.execute(
                select(func.count(BrandMention.id))
                .join(LLMResponse)
                .where(
                    and_(
                        LLMResponse.llm_run_id.in_(provider_run_ids),
                        BrandMention.is_own_brand == True,
                    )
                )
            )
            brand_mentions = result.scalar() or 0

            result = await self.db.execute(
                select(func.count(BrandMention.id))
                .join(LLMResponse)
                .where(LLMResponse.llm_run_id.in_(provider_run_ids))
            )
            total_mentions = result.scalar() or 0

            saiv_value = (brand_mentions / total_mentions * 100) if total_mentions > 0 else 0

            breakdown = SAIVBreakdown(
                saiv_snapshot_id=snapshot_id,
                dimension_type="llm",
                dimension_value=provider.value,
                saiv_value=saiv_value,
                brand_mentions=brand_mentions,
                total_mentions=total_mentions,
                runs_analyzed=len(provider_run_ids),
            )
            self.db.add(breakdown)

        await self.db.flush()

    # =========================================================================
    # SAIV QUERIES
    # =========================================================================

    async def get_current_saiv(
        self,
        project_id: UUID,
        period_type: str = "daily",
    ) -> Optional[SAIVSnapshot]:
        """Get the most recent SAIV snapshot."""
        result = await self.db.execute(
            select(SAIVSnapshot)
            .where(
                and_(
                    SAIVSnapshot.project_id == project_id,
                    SAIVSnapshot.period_type == period_type,
                )
            )
            .order_by(SAIVSnapshot.snapshot_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_saiv_history(
        self,
        project_id: UUID,
        period_type: str = "daily",
        days: int = 30,
    ) -> List[SAIVSnapshot]:
        """Get SAIV history for trending."""
        start_date = datetime.utcnow() - timedelta(days=days)

        result = await self.db.execute(
            select(SAIVSnapshot)
            .where(
                and_(
                    SAIVSnapshot.project_id == project_id,
                    SAIVSnapshot.period_type == period_type,
                    SAIVSnapshot.snapshot_date >= start_date,
                )
            )
            .order_by(SAIVSnapshot.snapshot_date.asc())
        )
        return list(result.scalars().all())

    async def get_saiv_breakdown(
        self,
        snapshot_id: UUID,
        dimension_type: Optional[str] = None,
    ) -> List[SAIVBreakdown]:
        """Get SAIV breakdown by dimension."""
        query = select(SAIVBreakdown).where(
            SAIVBreakdown.saiv_snapshot_id == snapshot_id
        )

        if dimension_type:
            query = query.where(SAIVBreakdown.dimension_type == dimension_type)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def compare_saiv_periods(
        self,
        project_id: UUID,
        current_start: datetime,
        current_end: datetime,
        previous_start: datetime,
        previous_end: datetime,
    ) -> Dict[str, Any]:
        """Compare SAIV between two time periods."""
        # Calculate current period
        current = await self.calculate_saiv(
            project_id, current_start, current_end, "comparison"
        )

        # Calculate previous period
        previous = await self.calculate_saiv(
            project_id, previous_start, previous_end, "comparison"
        )

        if not current or not previous:
            return {"error": "Insufficient data for comparison"}

        # Calculate changes
        saiv_change = current.overall_saiv - previous.overall_saiv
        mentions_change = current.total_brand_mentions - previous.total_brand_mentions

        # Calculate LLM-specific changes
        llm_changes = {}
        for llm, current_saiv in current.saiv_by_llm.items():
            previous_saiv = previous.saiv_by_llm.get(llm, 0)
            llm_changes[llm] = {
                "current": current_saiv,
                "previous": previous_saiv,
                "change": current_saiv - previous_saiv,
            }

        return {
            "current_period": {
                "start": current_start.isoformat(),
                "end": current_end.isoformat(),
                "saiv": current.overall_saiv,
                "mentions": current.total_brand_mentions,
            },
            "previous_period": {
                "start": previous_start.isoformat(),
                "end": previous_end.isoformat(),
                "saiv": previous.overall_saiv,
                "mentions": previous.total_brand_mentions,
            },
            "changes": {
                "saiv_change": saiv_change,
                "saiv_change_percent": (saiv_change / previous.overall_saiv * 100) if previous.overall_saiv > 0 else 0,
                "mentions_change": mentions_change,
            },
            "by_llm": llm_changes,
        }

    # =========================================================================
    # SAIV INSIGHTS
    # =========================================================================

    async def get_saiv_insights(
        self,
        project_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Generate insights from SAIV data."""
        history = await self.get_saiv_history(project_id, "daily", days)

        if len(history) < 2:
            return {"error": "Insufficient data for insights"}

        # Calculate statistics
        saiv_values = [s.overall_saiv for s in history]
        avg_saiv = sum(saiv_values) / len(saiv_values)
        max_saiv = max(saiv_values)
        min_saiv = min(saiv_values)

        # Calculate trend
        first_half = saiv_values[:len(saiv_values)//2]
        second_half = saiv_values[len(saiv_values)//2:]
        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)
        trend = avg_second - avg_first

        # Find best and worst performing LLMs
        latest = history[-1] if history else None
        best_llm = None
        worst_llm = None

        if latest and latest.saiv_by_llm:
            sorted_llms = sorted(
                latest.saiv_by_llm.items(),
                key=lambda x: x[1],
                reverse=True
            )
            best_llm = sorted_llms[0] if sorted_llms else None
            worst_llm = sorted_llms[-1] if sorted_llms else None

        # Find top competitor
        top_competitor = None
        if latest and latest.competitor_saiv:
            sorted_competitors = sorted(
                latest.competitor_saiv.items(),
                key=lambda x: x[1],
                reverse=True
            )
            if sorted_competitors:
                top_competitor = {
                    "name": sorted_competitors[0][0],
                    "saiv": sorted_competitors[0][1],
                }

        return {
            "period_days": days,
            "data_points": len(history),
            "statistics": {
                "current_saiv": saiv_values[-1] if saiv_values else 0,
                "average_saiv": avg_saiv,
                "max_saiv": max_saiv,
                "min_saiv": min_saiv,
                "volatility": max_saiv - min_saiv,
            },
            "trend": {
                "direction": "up" if trend > 1 else ("down" if trend < -1 else "stable"),
                "change": trend,
            },
            "llm_performance": {
                "best": {"llm": best_llm[0], "saiv": best_llm[1]} if best_llm else None,
                "worst": {"llm": worst_llm[0], "saiv": worst_llm[1]} if worst_llm else None,
            },
            "top_competitor": top_competitor,
        }

    async def calculate_saiv_for_today(
        self,
        project_id: UUID,
    ) -> SAIVSnapshot:
        """Calculate SAIV for today (convenience method)."""
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        tomorrow = today + timedelta(days=1)

        return await self.calculate_saiv(project_id, today, tomorrow, "daily")

    async def calculate_saiv_for_week(
        self,
        project_id: UUID,
    ) -> SAIVSnapshot:
        """Calculate SAIV for the current week."""
        today = datetime.utcnow()
        week_start = today - timedelta(days=today.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)

        return await self.calculate_saiv(project_id, week_start, today, "weekly")

    async def calculate_saiv_for_month(
        self,
        project_id: UUID,
    ) -> SAIVSnapshot:
        """Calculate SAIV for the current month."""
        today = datetime.utcnow()
        month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        return await self.calculate_saiv(project_id, month_start, today, "monthly")
