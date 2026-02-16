"""
Share of Voice Calculator Service
Calculates SOV metrics across keywords, time periods, and LLM providers
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import selectinload

from app.models import (
    Project, Brand, Competitor, Keyword, LLMRun, LLMResponse,
    BrandMention, LLMProvider, LLMRunStatus
)
from app.models.visibility import (
    ShareOfVoice, PositionTracking, KeywordAnalysisResult
)


class ShareOfVoiceCalculator:
    """
    Calculates Share of Voice metrics:
    - Overall SOV: % of AI responses mentioning our brand
    - Position metrics: Average placement in responses
    - Competitor comparison
    - Trend analysis
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_sov(
        self,
        project_id: UUID,
        period_start: datetime,
        period_end: datetime,
        period_type: str = "daily",
        keyword_id: Optional[UUID] = None,
        provider: Optional[LLMProvider] = None
    ) -> ShareOfVoice:
        """
        Calculate Share of Voice for a project over a time period.

        Args:
            project_id: Project to calculate SOV for
            period_start: Start of period
            period_end: End of period
            period_type: "daily", "weekly", or "monthly"
            keyword_id: Optional specific keyword to analyze
            provider: Optional specific LLM provider to analyze

        Returns:
            ShareOfVoice record with all calculated metrics
        """
        # Get project with brands and competitors
        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        brand_names = [b.name.lower() for b in project.brands]
        brand_names += [alias.lower() for b in project.brands for alias in (b.aliases or [])]

        competitor_info = {}  # {name: competitor_obj}
        for c in project.competitors:
            competitor_info[c.name.lower()] = c
            for alias in (c.aliases or []):
                competitor_info[alias.lower()] = c

        # Build query for analysis results
        query = select(KeywordAnalysisResult).where(
            and_(
                KeywordAnalysisResult.created_at >= period_start,
                KeywordAnalysisResult.created_at <= period_end,
            )
        ).join(LLMRun).where(LLMRun.project_id == project_id)

        if keyword_id:
            query = query.where(KeywordAnalysisResult.keyword_id == keyword_id)
        if provider:
            query = query.where(KeywordAnalysisResult.provider == provider)

        result = await self.db.execute(query)
        analysis_results = result.scalars().all()

        # Calculate metrics
        total_responses = len(analysis_results)
        brand_mention_count = 0
        total_entity_mentions = 0
        position_sum = 0
        first_position_count = 0
        competitor_mentions: Dict[str, int] = defaultdict(int)

        for ar in analysis_results:
            # Count our brand mentions
            if ar.brand_mentioned:
                brand_mention_count += 1
                if ar.brand_position == 1:
                    first_position_count += 1
                if ar.brand_position:
                    position_sum += ar.brand_position

            # Count total entities mentioned
            total_entity_mentions += ar.total_brands_mentioned

            # Count competitor mentions
            for comp in (ar.competitors_mentioned or []):
                comp_name = comp.get("name", "").lower() if isinstance(comp, dict) else str(comp).lower()
                if comp_name:
                    # Find the canonical competitor name
                    if comp_name in competitor_info:
                        canonical = competitor_info[comp_name].name
                        competitor_mentions[canonical] += 1

        # Calculate Share of Voice
        if total_responses > 0:
            sov = (brand_mention_count / total_responses) * 100
            mention_rate = brand_mention_count / total_responses
        else:
            sov = 0
            mention_rate = 0

        # Calculate competitor shares
        competitor_shares = {}
        for comp_name, count in competitor_mentions.items():
            if total_responses > 0:
                competitor_shares[comp_name] = round((count / total_responses) * 100, 2)

        # Calculate average position
        avg_position = position_sum / brand_mention_count if brand_mention_count > 0 else None

        # Get previous period for trend calculation
        period_delta = period_end - period_start
        prev_start = period_start - period_delta
        prev_end = period_start

        prev_query = select(KeywordAnalysisResult).where(
            and_(
                KeywordAnalysisResult.created_at >= prev_start,
                KeywordAnalysisResult.created_at <= prev_end,
            )
        ).join(LLMRun).where(LLMRun.project_id == project_id)

        if keyword_id:
            prev_query = prev_query.where(KeywordAnalysisResult.keyword_id == keyword_id)
        if provider:
            prev_query = prev_query.where(KeywordAnalysisResult.provider == provider)

        prev_result = await self.db.execute(prev_query)
        prev_analysis = prev_result.scalars().all()

        prev_total = len(prev_analysis)
        prev_brand_count = sum(1 for ar in prev_analysis if ar.brand_mentioned)
        prev_sov = (prev_brand_count / prev_total * 100) if prev_total > 0 else 0

        sov_change = sov - prev_sov

        if sov_change > 1:
            trend = "up"
        elif sov_change < -1:
            trend = "down"
        else:
            trend = "stable"

        # Create or update SOV record
        existing = await self.db.execute(
            select(ShareOfVoice).where(
                and_(
                    ShareOfVoice.project_id == project_id,
                    ShareOfVoice.keyword_id == keyword_id,
                    ShareOfVoice.provider == provider,
                    ShareOfVoice.period_start == period_start,
                    ShareOfVoice.period_type == period_type
                )
            )
        )
        sov_record = existing.scalar_one_or_none()

        if not sov_record:
            sov_record = ShareOfVoice(
                project_id=project_id,
                keyword_id=keyword_id,
                provider=provider,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
            )
            self.db.add(sov_record)

        # Update all fields
        sov_record.brand_mention_count = brand_mention_count
        sov_record.brand_mention_rate = round(mention_rate, 4)
        sov_record.total_entity_mentions = total_entity_mentions
        sov_record.total_responses_analyzed = total_responses
        sov_record.share_of_voice = round(sov, 2)
        sov_record.competitor_shares = competitor_shares
        sov_record.avg_mention_position = round(avg_position, 2) if avg_position else None
        sov_record.first_position_count = first_position_count
        sov_record.sov_change = round(sov_change, 2)
        sov_record.trend = trend

        await self.db.commit()
        await self.db.refresh(sov_record)

        return sov_record

    async def calculate_position_tracking(
        self,
        project_id: UUID,
        tracking_date: datetime,
        keyword_id: Optional[UUID] = None,
        provider: Optional[LLMProvider] = None
    ) -> List[PositionTracking]:
        """
        Calculate position tracking metrics for all entities.

        Returns list of PositionTracking records for own brand and competitors.
        """
        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Get analysis results for the date
        day_start = tracking_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        query = select(KeywordAnalysisResult).where(
            and_(
                KeywordAnalysisResult.created_at >= day_start,
                KeywordAnalysisResult.created_at < day_end,
            )
        ).join(LLMRun).where(LLMRun.project_id == project_id)

        if keyword_id:
            query = query.where(KeywordAnalysisResult.keyword_id == keyword_id)
        if provider:
            query = query.where(KeywordAnalysisResult.provider == provider)

        result = await self.db.execute(query)
        analysis_results = result.scalars().all()

        # Collect positions for each entity
        entity_positions: Dict[str, Dict] = defaultdict(lambda: {
            "positions": [],
            "is_own_brand": False
        })

        # Our brand positions
        brand_names = [b.name for b in project.brands]
        for ar in analysis_results:
            if ar.brand_mentioned and ar.brand_position:
                for brand_name in brand_names:
                    entity_positions[brand_name]["positions"].append(ar.brand_position)
                    entity_positions[brand_name]["is_own_brand"] = True

            # Competitor positions
            for comp in (ar.competitors_mentioned or []):
                if isinstance(comp, dict):
                    name = comp.get("name")
                    pos = comp.get("position")
                    if name and pos:
                        entity_positions[name]["positions"].append(pos)

        # Create tracking records
        tracking_records = []

        for entity_name, data in entity_positions.items():
            positions = data["positions"]
            if not positions:
                continue

            avg_pos = sum(positions) / len(positions)
            min_pos = min(positions)
            max_pos = max(positions)

            # Calculate standard deviation
            variance = sum((p - avg_pos) ** 2 for p in positions) / len(positions)
            std_dev = variance ** 0.5

            # Position distribution
            distribution = defaultdict(int)
            for p in positions:
                distribution[str(p)] += 1

            # Get previous day for comparison
            prev_day_start = day_start - timedelta(days=1)
            prev_result = await self.db.execute(
                select(PositionTracking).where(
                    and_(
                        PositionTracking.project_id == project_id,
                        PositionTracking.entity_name == entity_name,
                        PositionTracking.tracking_date >= prev_day_start,
                        PositionTracking.tracking_date < day_start,
                    )
                )
            )
            prev_tracking = prev_result.scalar_one_or_none()
            pos_vs_yesterday = None
            if prev_tracking and prev_tracking.avg_position:
                pos_vs_yesterday = avg_pos - prev_tracking.avg_position

            # Create record
            tracking = PositionTracking(
                project_id=project_id,
                keyword_id=keyword_id,
                entity_name=entity_name,
                is_own_brand=data["is_own_brand"],
                tracking_date=day_start,
                provider=provider,
                avg_position=round(avg_pos, 2),
                min_position=min_pos,
                max_position=max_pos,
                position_std_dev=round(std_dev, 2),
                position_distribution=dict(distribution),
                position_vs_yesterday=round(pos_vs_yesterday, 2) if pos_vs_yesterday else None,
                mentions_analyzed=len(positions)
            )

            self.db.add(tracking)
            tracking_records.append(tracking)

        await self.db.commit()
        return tracking_records

    async def get_sov_summary(
        self,
        project_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get SOV summary for dashboard display.

        Returns aggregated metrics over the specified number of days.
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get latest SOV records
        result = await self.db.execute(
            select(ShareOfVoice)
            .where(
                and_(
                    ShareOfVoice.project_id == project_id,
                    ShareOfVoice.period_start >= start_date,
                    ShareOfVoice.keyword_id.is_(None),  # Aggregate records
                    ShareOfVoice.provider.is_(None)      # Aggregate records
                )
            )
            .order_by(ShareOfVoice.period_start.desc())
        )
        sov_records = result.scalars().all()

        if not sov_records:
            return {
                "share_of_voice": 0,
                "mention_rate": 0,
                "avg_position": None,
                "first_position_rate": 0,
                "trend": "stable",
                "competitor_shares": {},
                "sov_history": [],
                "total_responses": 0
            }

        latest = sov_records[0]
        total_mentions = sum(r.brand_mention_count for r in sov_records)
        total_responses = sum(r.total_responses_analyzed for r in sov_records)
        first_pos_count = sum(r.first_position_count for r in sov_records)

        # Build history for chart
        history = [
            {
                "date": r.period_start.isoformat(),
                "sov": r.share_of_voice,
                "mentions": r.brand_mention_count,
                "responses": r.total_responses_analyzed
            }
            for r in reversed(sov_records)
        ]

        return {
            "share_of_voice": latest.share_of_voice,
            "mention_rate": round(total_mentions / total_responses * 100, 2) if total_responses else 0,
            "avg_position": latest.avg_mention_position,
            "first_position_rate": round(first_pos_count / total_responses * 100, 2) if total_responses else 0,
            "trend": latest.trend,
            "trend_change": latest.sov_change,
            "competitor_shares": latest.competitor_shares or {},
            "sov_history": history,
            "total_responses": total_responses,
            "total_mentions": total_mentions,
            "period_days": days
        }

    async def get_position_summary(
        self,
        project_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get position tracking summary for dashboard."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get position tracking records
        result = await self.db.execute(
            select(PositionTracking)
            .where(
                and_(
                    PositionTracking.project_id == project_id,
                    PositionTracking.tracking_date >= start_date,
                    PositionTracking.is_own_brand == True
                )
            )
            .order_by(PositionTracking.tracking_date.desc())
        )
        position_records = result.scalars().all()

        if not position_records:
            return {
                "avg_position": None,
                "best_position": None,
                "position_trend": "stable",
                "position_history": [],
                "distribution": {}
            }

        latest = position_records[0]
        all_positions = []
        for r in position_records:
            all_positions.append(r.avg_position)

        # Build history
        history = [
            {
                "date": r.tracking_date.isoformat(),
                "avg_position": r.avg_position,
                "min_position": r.min_position,
                "max_position": r.max_position
            }
            for r in reversed(position_records)
        ]

        # Aggregate distribution
        total_distribution: Dict[str, int] = defaultdict(int)
        for r in position_records:
            for pos, count in (r.position_distribution or {}).items():
                total_distribution[pos] += count

        return {
            "avg_position": round(sum(all_positions) / len(all_positions), 2),
            "best_position": min(r.min_position for r in position_records if r.min_position),
            "position_trend": "up" if latest.position_vs_yesterday and latest.position_vs_yesterday < 0 else (
                "down" if latest.position_vs_yesterday and latest.position_vs_yesterday > 0 else "stable"
            ),
            "position_history": history,
            "distribution": dict(total_distribution)
        }

    async def _get_project(self, project_id: UUID) -> Optional[Project]:
        """Get project with brands and competitors."""
        result = await self.db.execute(
            select(Project)
            .options(
                selectinload(Project.brands),
                selectinload(Project.competitors)
            )
            .where(Project.id == project_id)
        )
        return result.scalar_one_or_none()
