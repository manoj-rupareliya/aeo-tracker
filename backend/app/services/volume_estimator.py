"""
AI Prompt Volume Estimator Service
Estimates monthly AI conversation volume for topics based on various signals
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from uuid import UUID
import math

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from sqlalchemy.orm import selectinload

from app.models import Project, Keyword, LLMRun, LLMRunStatus
from app.models.visibility import PromptVolumeEstimate, KeywordAnalysisResult


class VolumeEstimator:
    """
    Estimates monthly AI prompt volume for topics.

    Uses multiple signals:
    - Google search volume (if available)
    - Historical query patterns
    - Topic popularity indicators
    - Industry benchmarks
    """

    # Base multipliers for converting search volume to AI prompt estimates
    # These are rough estimates - in production, use real data
    AI_ADOPTION_MULTIPLIER = 0.15  # ~15% of searchers also use AI

    # Platform distribution estimates (% of AI queries)
    PLATFORM_DISTRIBUTION = {
        "chatgpt": 0.55,      # ChatGPT ~55% market share
        "claude": 0.15,       # Claude ~15%
        "gemini": 0.20,       # Gemini ~20%
        "perplexity": 0.10,   # Perplexity ~10%
    }

    # Topic category multipliers (some topics more AI-queried)
    CATEGORY_MULTIPLIERS = {
        "technology": 1.5,
        "programming": 2.0,
        "marketing": 1.3,
        "finance": 1.2,
        "healthcare": 0.9,
        "education": 1.4,
        "ecommerce": 1.1,
        "legal": 0.8,
        "other": 1.0,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def estimate_volume_for_project(
        self,
        project_id: UUID,
        estimate_month: Optional[datetime] = None
    ) -> List[PromptVolumeEstimate]:
        """
        Estimate AI prompt volume for all keywords in a project.
        """
        if not estimate_month:
            estimate_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # Get project with keywords
        result = await self.db.execute(
            select(Project)
            .options(selectinload(Project.keywords))
            .where(Project.id == project_id)
        )
        project = result.scalar_one_or_none()

        if not project:
            raise ValueError(f"Project {project_id} not found")

        estimates = []
        category_multiplier = self.CATEGORY_MULTIPLIERS.get(
            project.industry.value if project.industry else "other",
            1.0
        )

        for keyword in project.keywords:
            if not keyword.is_active:
                continue

            estimate = await self._estimate_keyword_volume(
                project_id=project_id,
                keyword=keyword,
                estimate_month=estimate_month,
                category_multiplier=category_multiplier
            )
            estimates.append(estimate)

        await self.db.commit()
        return estimates

    async def _estimate_keyword_volume(
        self,
        project_id: UUID,
        keyword,
        estimate_month: datetime,
        category_multiplier: float
    ) -> PromptVolumeEstimate:
        """Estimate volume for a single keyword."""

        # Check for existing estimate
        result = await self.db.execute(
            select(PromptVolumeEstimate).where(
                and_(
                    PromptVolumeEstimate.project_id == project_id,
                    PromptVolumeEstimate.keyword_id == keyword.id,
                    PromptVolumeEstimate.estimate_month == estimate_month
                )
            )
        )
        existing = result.scalar_one_or_none()

        # Calculate base volume from keyword characteristics
        base_volume = self._calculate_base_volume(keyword.keyword)

        # Apply category multiplier
        adjusted_volume = int(base_volume * category_multiplier)

        # Calculate platform-specific volumes
        chatgpt_volume = int(adjusted_volume * self.PLATFORM_DISTRIBUTION["chatgpt"])
        claude_volume = int(adjusted_volume * self.PLATFORM_DISTRIBUTION["claude"])
        gemini_volume = int(adjusted_volume * self.PLATFORM_DISTRIBUTION["gemini"])
        perplexity_volume = int(adjusted_volume * self.PLATFORM_DISTRIBUTION["perplexity"])

        # Calculate opportunity score (0-100)
        opportunity_score = self._calculate_opportunity_score(adjusted_volume, keyword.keyword)

        # Determine competition level
        competition_level = self._estimate_competition(keyword.keyword)

        # Estimate trend
        volume_trend = "stable"  # Default - would need historical data for real trend

        if existing:
            # Update existing record
            existing.total_estimated_prompts = adjusted_volume
            existing.chatgpt_volume = chatgpt_volume
            existing.claude_volume = claude_volume
            existing.gemini_volume = gemini_volume
            existing.perplexity_volume = perplexity_volume
            existing.estimation_method = "keyword_analysis"
            existing.confidence_level = 0.6
            existing.confidence_reason = "Estimated based on keyword characteristics and industry benchmarks"
            existing.opportunity_score = opportunity_score
            existing.competition_level = competition_level
            existing.volume_trend = volume_trend
            existing.updated_at = datetime.utcnow()
            return existing
        else:
            # Create new estimate
            estimate = PromptVolumeEstimate(
                project_id=project_id,
                keyword_id=keyword.id,
                topic=keyword.keyword,
                topic_cluster=self._get_topic_cluster(keyword.keyword),
                estimate_month=estimate_month,
                total_estimated_prompts=adjusted_volume,
                chatgpt_volume=chatgpt_volume,
                claude_volume=claude_volume,
                gemini_volume=gemini_volume,
                perplexity_volume=perplexity_volume,
                estimation_method="keyword_analysis",
                confidence_level=0.6,
                confidence_reason="Estimated based on keyword characteristics and industry benchmarks",
                opportunity_score=opportunity_score,
                competition_level=competition_level,
                volume_trend=volume_trend,
            )
            self.db.add(estimate)
            return estimate

    def _calculate_base_volume(self, keyword: str) -> int:
        """
        Calculate base monthly volume estimate for a keyword.
        Uses keyword length, word count, and type indicators.
        """
        words = keyword.lower().split()
        word_count = len(words)

        # Base volume decreases with specificity (more words = lower volume)
        if word_count == 1:
            base = 50000
        elif word_count == 2:
            base = 25000
        elif word_count == 3:
            base = 10000
        elif word_count <= 5:
            base = 5000
        else:
            base = 2000

        # Adjust for question-type keywords (higher AI usage)
        question_words = ["what", "how", "why", "which", "best", "top", "compare", "vs"]
        if any(qw in words for qw in question_words):
            base = int(base * 1.5)

        # Adjust for commercial intent
        commercial_words = ["buy", "price", "cost", "cheap", "affordable", "review", "recommend"]
        if any(cw in words for cw in commercial_words):
            base = int(base * 1.3)

        # Adjust for tech/software keywords
        tech_words = ["software", "tool", "app", "platform", "api", "code", "programming"]
        if any(tw in words for tw in tech_words):
            base = int(base * 1.8)

        return base

    def _calculate_opportunity_score(self, volume: int, keyword: str) -> float:
        """Calculate opportunity score (0-100) based on volume and characteristics."""
        # Volume component (0-50 points)
        if volume >= 50000:
            volume_score = 50
        elif volume >= 20000:
            volume_score = 40
        elif volume >= 10000:
            volume_score = 30
        elif volume >= 5000:
            volume_score = 20
        else:
            volume_score = 10

        # Specificity component (0-30 points) - more specific = easier to rank
        word_count = len(keyword.split())
        if word_count >= 4:
            specificity_score = 30
        elif word_count == 3:
            specificity_score = 25
        elif word_count == 2:
            specificity_score = 15
        else:
            specificity_score = 5

        # Intent component (0-20 points)
        intent_words = ["best", "top", "recommend", "compare", "vs", "review"]
        if any(iw in keyword.lower() for iw in intent_words):
            intent_score = 20
        else:
            intent_score = 10

        return min(100, volume_score + specificity_score + intent_score)

    def _estimate_competition(self, keyword: str) -> str:
        """Estimate competition level for a keyword."""
        words = keyword.lower().split()
        word_count = len(words)

        # Short, generic keywords = high competition
        if word_count <= 2:
            return "high"
        elif word_count <= 4:
            return "medium"
        else:
            return "low"

    def _get_topic_cluster(self, keyword: str) -> str:
        """Assign keyword to a topic cluster."""
        keyword_lower = keyword.lower()

        clusters = {
            "software_tools": ["software", "tool", "app", "platform", "saas"],
            "comparisons": ["vs", "compare", "comparison", "alternative", "better"],
            "recommendations": ["best", "top", "recommend", "review"],
            "how_to": ["how to", "guide", "tutorial", "learn"],
            "pricing": ["price", "cost", "pricing", "cheap", "free"],
        }

        for cluster, indicators in clusters.items():
            if any(ind in keyword_lower for ind in indicators):
                return cluster

        return "general"

    async def get_volume_summary(
        self,
        project_id: UUID
    ) -> Dict[str, Any]:
        """Get volume estimation summary for a project."""
        result = await self.db.execute(
            select(PromptVolumeEstimate)
            .where(PromptVolumeEstimate.project_id == project_id)
            .order_by(PromptVolumeEstimate.total_estimated_prompts.desc())
        )
        estimates = result.scalars().all()

        if not estimates:
            return {
                "total_monthly_volume": 0,
                "top_topics": [],
                "platform_breakdown": {
                    "chatgpt": 0,
                    "claude": 0,
                    "gemini": 0,
                    "perplexity": 0
                },
                "opportunity_summary": {
                    "high": 0,
                    "medium": 0,
                    "low": 0
                }
            }

        total_volume = sum(e.total_estimated_prompts for e in estimates)

        platform_breakdown = {
            "chatgpt": sum(e.chatgpt_volume for e in estimates),
            "claude": sum(e.claude_volume for e in estimates),
            "gemini": sum(e.gemini_volume for e in estimates),
            "perplexity": sum(e.perplexity_volume for e in estimates),
        }

        # Opportunity breakdown
        high_opp = sum(1 for e in estimates if e.opportunity_score >= 70)
        medium_opp = sum(1 for e in estimates if 40 <= e.opportunity_score < 70)
        low_opp = sum(1 for e in estimates if e.opportunity_score < 40)

        top_topics = [
            {
                "topic": e.topic,
                "volume": e.total_estimated_prompts,
                "opportunity_score": e.opportunity_score,
                "competition": e.competition_level
            }
            for e in estimates[:10]
        ]

        return {
            "total_monthly_volume": total_volume,
            "top_topics": top_topics,
            "platform_breakdown": platform_breakdown,
            "opportunity_summary": {
                "high": high_opp,
                "medium": medium_opp,
                "low": low_opp
            },
            "total_keywords": len(estimates)
        }
