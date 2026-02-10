"""
GEO Recommendation Engine
Generates actionable, evidence-based recommendations for improving LLM visibility
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import (
    LLMProvider, LLMRun, LLMResponse, BrandMention, Citation,
    CitationSource, Keyword, Brand, Competitor, SourceCategory
)
from ..models.models_v2 import (
    GEORecommendation, GapAnalysis, RecommendationType, ConfidenceLevel,
    PreferenceGraphNode, PreferenceGraphEdge, GraphNodeType, GraphEdgeType,
    ResponseSnapshot
)


class GEORecommendationEngine:
    """
    Engine for generating actionable, evidence-based GEO recommendations.

    Principles:
    - No hallucinated recommendations
    - All suggestions backed by observed LLM behavior
    - Confidence level for each recommendation
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # GAP ANALYSIS
    # =========================================================================

    async def analyze_keyword_gap(
        self,
        project_id: UUID,
        keyword_id: UUID,
        provider: Optional[LLMProvider] = None,
        days: int = 30,
    ) -> GapAnalysis:
        """
        Analyze where the brand is absent for a specific keyword.
        Identifies opportunities for improvement.
        """
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get runs for this keyword
        run_query = (
            select(LLMRun)
            .where(
                and_(
                    LLMRun.project_id == project_id,
                    LLMRun.keyword_id == keyword_id,
                    LLMRun.created_at >= start_date,
                )
            )
        )

        if provider:
            run_query = run_query.where(LLMRun.provider == provider)

        result = await self.db.execute(run_query)
        runs = list(result.scalars().all())

        if not runs:
            return None

        run_ids = [r.id for r in runs]
        total_runs = len(runs)

        # Get brand mentions (our brand)
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
        brand_mentions = result.scalar() or 0

        # Calculate brand absent rate
        brand_absent_rate = (total_runs - brand_mentions) / total_runs * 100

        # Get competitor mentions
        result = await self.db.execute(
            select(func.count(BrandMention.id))
            .join(LLMResponse)
            .where(
                and_(
                    LLMResponse.llm_run_id.in_(run_ids),
                    BrandMention.is_own_brand == False,
                )
            )
        )
        competitor_mentions = result.scalar() or 0
        competitor_present_rate = (competitor_mentions / total_runs * 100) if total_runs > 0 else 0

        # Get citations when brand is absent
        # First, find runs where brand was NOT mentioned
        absent_run_ids = []
        for run in runs:
            result = await self.db.execute(
                select(func.count(BrandMention.id))
                .join(LLMResponse)
                .where(
                    and_(
                        LLMResponse.llm_run_id == run.id,
                        BrandMention.is_own_brand == True,
                    )
                )
            )
            if result.scalar() == 0:
                absent_run_ids.append(run.id)

        # Get sources cited when brand is absent
        sources_when_absent = {}
        if absent_run_ids:
            result = await self.db.execute(
                select(CitationSource.domain, func.count(Citation.id))
                .join(Citation)
                .join(LLMResponse)
                .where(LLMResponse.llm_run_id.in_(absent_run_ids))
                .group_by(CitationSource.domain)
                .order_by(func.count(Citation.id).desc())
                .limit(10)
            )
            sources_when_absent = {row[0]: row[1] for row in result.all()}

        # Calculate opportunity score
        opportunity_score = self._calculate_opportunity_score(
            brand_absent_rate, competitor_present_rate, len(sources_when_absent)
        )

        # Generate suggested actions
        suggested_actions = await self._generate_gap_actions(
            sources_when_absent, competitor_present_rate
        )

        # Create gap analysis record
        gap = GapAnalysis(
            project_id=project_id,
            keyword_id=keyword_id,
            provider=provider,
            analysis_date=datetime.utcnow(),
            brand_absent_rate=brand_absent_rate,
            competitor_present_rate=competitor_present_rate,
            sources_cited_when_absent=sources_when_absent,
            opportunity_score=opportunity_score,
            suggested_actions=suggested_actions,
        )

        self.db.add(gap)
        await self.db.flush()
        return gap

    def _calculate_opportunity_score(
        self,
        absent_rate: float,
        competitor_rate: float,
        source_count: int,
    ) -> float:
        """Calculate opportunity score (0-100)."""
        # Higher absent rate = more opportunity
        absent_score = min(absent_rate, 100) * 0.4

        # Higher competitor presence = more urgent opportunity
        competitor_score = min(competitor_rate, 100) * 0.3

        # More cited sources = more actionable
        source_score = min(source_count * 10, 30)

        return absent_score + competitor_score + source_score

    async def _generate_gap_actions(
        self,
        sources: Dict[str, int],
        competitor_rate: float,
    ) -> List[str]:
        """Generate suggested actions based on gap analysis."""
        actions = []

        if sources:
            top_sources = list(sources.keys())[:3]
            for source in top_sources:
                actions.append(f"Get mentioned on {source}")

        if competitor_rate > 50:
            actions.append("Analyze competitor content strategy")
            actions.append("Strengthen differentiation messaging")

        if not sources:
            actions.append("Create content targeting this keyword cluster")

        return actions

    # =========================================================================
    # RECOMMENDATION GENERATION
    # =========================================================================

    async def generate_recommendations(
        self,
        project_id: UUID,
        days: int = 30,
        limit: int = 10,
    ) -> List[GEORecommendation]:
        """
        Generate all types of recommendations for a project.
        Analyzes gaps, sources, and competitor activity.
        """
        recommendations = []

        # Get gap-based recommendations
        gap_recs = await self._generate_gap_recommendations(project_id, days)
        recommendations.extend(gap_recs)

        # Get source-based recommendations
        source_recs = await self._generate_source_recommendations(project_id, days)
        recommendations.extend(source_recs)

        # Get competitor-based recommendations
        competitor_recs = await self._generate_competitor_recommendations(project_id, days)
        recommendations.extend(competitor_recs)

        # Sort by priority and limit
        recommendations.sort(key=lambda r: r.priority_score, reverse=True)
        return recommendations[:limit]

    async def _generate_gap_recommendations(
        self,
        project_id: UUID,
        days: int,
    ) -> List[GEORecommendation]:
        """Generate recommendations based on keyword gaps."""
        recommendations = []

        # Get keywords for this project
        result = await self.db.execute(
            select(Keyword).where(Keyword.project_id == project_id)
        )
        keywords = list(result.scalars().all())

        for keyword in keywords:
            gap = await self.analyze_keyword_gap(project_id, keyword.id, days=days)
            if gap and gap.brand_absent_rate > 40:  # Only recommend if significant gap
                rec = GEORecommendation(
                    project_id=project_id,
                    recommendation_type=RecommendationType.TARGET_KEYWORD,
                    target_keyword_id=keyword.id,
                    title=f"Improve visibility for '{keyword.keyword}'",
                    description=f"Your brand is absent from {gap.brand_absent_rate:.0f}% of responses for this keyword.",
                    action_items=gap.suggested_actions,
                    evidence_summary=f"Based on analysis of LLM responses over {days} days.",
                    supporting_data={
                        "absent_rate": gap.brand_absent_rate,
                        "competitor_rate": gap.competitor_present_rate,
                        "top_sources": list(gap.sources_cited_when_absent.keys())[:5],
                    },
                    target_sources=list(gap.sources_cited_when_absent.keys())[:5],
                    priority_score=gap.opportunity_score,
                    confidence=self._determine_confidence(gap.opportunity_score),
                    confidence_score=self._calculate_confidence_score(gap.opportunity_score),
                    potential_visibility_gain=gap.brand_absent_rate * 0.3,  # Estimate
                    effort_level=self._estimate_effort(gap.sources_cited_when_absent),
                    valid_until=datetime.utcnow() + timedelta(days=30),
                )
                self.db.add(rec)
                recommendations.append(rec)

        await self.db.flush()
        return recommendations

    async def _generate_source_recommendations(
        self,
        project_id: UUID,
        days: int,
    ) -> List[GEORecommendation]:
        """Generate recommendations based on source analysis."""
        recommendations = []
        start_date = datetime.utcnow() - timedelta(days=days)

        # Find sources that are frequently cited but don't mention our brand
        result = await self.db.execute(
            select(
                CitationSource.domain,
                CitationSource.site_name,
                CitationSource.category,
                func.count(Citation.id).label("citation_count"),
            )
            .join(Citation)
            .join(LLMResponse)
            .join(LLMRun)
            .where(
                and_(
                    LLMRun.project_id == project_id,
                    LLMRun.created_at >= start_date,
                )
            )
            .group_by(CitationSource.id)
            .order_by(func.count(Citation.id).desc())
            .limit(20)
        )
        top_sources = result.all()

        for domain, site_name, category, citation_count in top_sources:
            if citation_count >= 3:  # Only recommend for frequently cited sources
                rec = GEORecommendation(
                    project_id=project_id,
                    recommendation_type=RecommendationType.GET_LISTED,
                    title=f"Get listed on {site_name or domain}",
                    description=f"This source is cited {citation_count} times by LLMs in your keyword space.",
                    action_items=[
                        f"Create a profile or listing on {domain}",
                        "Ensure your brand information is accurate and complete",
                        "Add relevant keywords to your listing",
                    ],
                    evidence_summary=f"Cited {citation_count} times in LLM responses over {days} days.",
                    supporting_data={
                        "domain": domain,
                        "citation_count": citation_count,
                        "category": category.value if category else None,
                    },
                    target_sources=[domain],
                    priority_score=min(citation_count * 10, 80),
                    confidence=ConfidenceLevel.MEDIUM,
                    confidence_score=0.7,
                    effort_level="medium",
                    valid_until=datetime.utcnow() + timedelta(days=60),
                )
                self.db.add(rec)
                recommendations.append(rec)

        await self.db.flush()
        return recommendations

    async def _generate_competitor_recommendations(
        self,
        project_id: UUID,
        days: int,
    ) -> List[GEORecommendation]:
        """Generate recommendations based on competitor analysis."""
        recommendations = []
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get competitor mentions
        result = await self.db.execute(
            select(
                BrandMention.brand_name,
                func.count(BrandMention.id).label("mention_count"),
                func.avg(BrandMention.position_in_response).label("avg_position"),
            )
            .join(LLMResponse)
            .join(LLMRun)
            .where(
                and_(
                    LLMRun.project_id == project_id,
                    LLMRun.created_at >= start_date,
                    BrandMention.is_own_brand == False,
                )
            )
            .group_by(BrandMention.brand_name)
            .order_by(func.count(BrandMention.id).desc())
            .limit(5)
        )
        top_competitors = result.all()

        for brand_name, mention_count, avg_position in top_competitors:
            if mention_count >= 5:
                rec = GEORecommendation(
                    project_id=project_id,
                    recommendation_type=RecommendationType.COMPETITOR_GAP,
                    title=f"Address competitor advantage: {brand_name}",
                    description=f"{brand_name} is mentioned {mention_count} times with avg position {avg_position:.1f}.",
                    action_items=[
                        f"Analyze {brand_name}'s content strategy",
                        "Identify differentiating features",
                        "Create comparison content",
                    ],
                    evidence_summary=f"Competitor analysis over {days} days shows strong presence.",
                    supporting_data={
                        "competitor": brand_name,
                        "mention_count": mention_count,
                        "avg_position": avg_position,
                    },
                    competitor_context={brand_name: {"mentions": mention_count, "position": avg_position}},
                    priority_score=min(mention_count * 8, 70),
                    confidence=ConfidenceLevel.MEDIUM,
                    confidence_score=0.75,
                    effort_level="high",
                    valid_until=datetime.utcnow() + timedelta(days=45),
                )
                self.db.add(rec)
                recommendations.append(rec)

        await self.db.flush()
        return recommendations

    def _determine_confidence(self, score: float) -> ConfidenceLevel:
        """Determine confidence level based on score."""
        if score >= 70:
            return ConfidenceLevel.HIGH
        elif score >= 50:
            return ConfidenceLevel.MEDIUM
        elif score >= 30:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.UNCERTAIN

    def _calculate_confidence_score(self, opportunity_score: float) -> float:
        """Calculate confidence score (0-1)."""
        return min(opportunity_score / 100 + 0.3, 1.0)

    def _estimate_effort(self, sources: Dict[str, int]) -> str:
        """Estimate effort level based on sources to target."""
        if len(sources) <= 2:
            return "low"
        elif len(sources) <= 5:
            return "medium"
        else:
            return "high"

    # =========================================================================
    # RECOMMENDATION MANAGEMENT
    # =========================================================================

    async def get_recommendations(
        self,
        project_id: UUID,
        recommendation_type: Optional[RecommendationType] = None,
        include_dismissed: bool = False,
        include_completed: bool = False,
        limit: int = 50,
    ) -> List[GEORecommendation]:
        """Get recommendations for a project."""
        query = select(GEORecommendation).where(
            GEORecommendation.project_id == project_id
        )

        if recommendation_type:
            query = query.where(GEORecommendation.recommendation_type == recommendation_type)

        if not include_dismissed:
            query = query.where(GEORecommendation.is_dismissed == False)

        if not include_completed:
            query = query.where(GEORecommendation.is_completed == False)

        # Only show valid recommendations
        query = query.where(
            or_(
                GEORecommendation.valid_until.is_(None),
                GEORecommendation.valid_until >= datetime.utcnow(),
            )
        )

        query = query.order_by(GEORecommendation.priority_score.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def dismiss_recommendation(
        self,
        recommendation_id: UUID,
    ) -> GEORecommendation:
        """Dismiss a recommendation."""
        result = await self.db.execute(
            select(GEORecommendation).where(GEORecommendation.id == recommendation_id)
        )
        rec = result.scalar_one()
        rec.is_dismissed = True
        await self.db.flush()
        return rec

    async def complete_recommendation(
        self,
        recommendation_id: UUID,
    ) -> GEORecommendation:
        """Mark a recommendation as completed."""
        result = await self.db.execute(
            select(GEORecommendation).where(GEORecommendation.id == recommendation_id)
        )
        rec = result.scalar_one()
        rec.is_completed = True
        rec.completed_at = datetime.utcnow()
        await self.db.flush()
        return rec

    async def get_recommendation_summary(
        self,
        project_id: UUID,
    ) -> Dict[str, Any]:
        """Get a summary of recommendations for a project."""
        # Count by type
        result = await self.db.execute(
            select(
                GEORecommendation.recommendation_type,
                func.count(GEORecommendation.id),
            )
            .where(
                and_(
                    GEORecommendation.project_id == project_id,
                    GEORecommendation.is_dismissed == False,
                    GEORecommendation.is_completed == False,
                )
            )
            .group_by(GEORecommendation.recommendation_type)
        )
        by_type = {row[0].value: row[1] for row in result.all()}

        # Count by confidence
        result = await self.db.execute(
            select(
                GEORecommendation.confidence,
                func.count(GEORecommendation.id),
            )
            .where(
                and_(
                    GEORecommendation.project_id == project_id,
                    GEORecommendation.is_dismissed == False,
                    GEORecommendation.is_completed == False,
                )
            )
            .group_by(GEORecommendation.confidence)
        )
        by_confidence = {row[0].value: row[1] for row in result.all()}

        # Total active
        result = await self.db.execute(
            select(func.count(GEORecommendation.id)).where(
                and_(
                    GEORecommendation.project_id == project_id,
                    GEORecommendation.is_dismissed == False,
                    GEORecommendation.is_completed == False,
                )
            )
        )
        total_active = result.scalar()

        # Completed count
        result = await self.db.execute(
            select(func.count(GEORecommendation.id)).where(
                and_(
                    GEORecommendation.project_id == project_id,
                    GEORecommendation.is_completed == True,
                )
            )
        )
        completed = result.scalar()

        return {
            "total_active": total_active,
            "completed": completed,
            "by_type": by_type,
            "by_confidence": by_confidence,
        }
