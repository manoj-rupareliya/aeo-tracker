"""
Visibility Scoring Engine
Calculates transparent, explainable visibility scores
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BrandMention, Citation, LLMRun, LLMResponse, VisibilityScore,
    Project, Brand, LLMProvider, SentimentPolarity
)
from app.config import get_settings, VISIBILITY_SCORE_WEIGHTS, LLM_MARKET_WEIGHTS

settings = get_settings()


@dataclass
class ScoreComponent:
    """A component of the visibility score with explanation"""
    name: str
    raw_value: float  # Before weighting
    weight: float
    weighted_value: float  # raw_value * weight
    explanation: str
    contributing_factors: List[str] = field(default_factory=list)


@dataclass
class ScoreBreakdown:
    """Complete breakdown of a visibility score"""
    mention_score: ScoreComponent
    position_score: ScoreComponent
    citation_score: ScoreComponent
    sentiment_score: ScoreComponent
    competitor_delta: ScoreComponent
    total_raw: float
    llm_weight: float
    total_weighted: float
    explanation: str


class ScoringEngine:
    """
    Calculates visibility scores with full transparency.

    Scoring Model:
    - Base Score = 0
    - +30 points: Brand mentioned
    - +20 points: Brand in top-3 mentions
    - +15 points: Brand cited as source
    - +10 points: Positive sentiment
    - -5 points: Competitor mentioned before brand
    - -10 points: Brand not mentioned at all

    LLM Weight Multipliers:
    - OpenAI (ChatGPT): 1.0x (market leader)
    - Anthropic (Claude): 0.9x (growing adoption)
    - Google (Gemini): 0.8x (newer entrant)
    - Perplexity: 1.1x (citation-focused, high GEO value)
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    def get_llm_weight(self, provider: LLMProvider) -> float:
        """Get the market weight for an LLM provider"""
        return LLM_MARKET_WEIGHTS.get(provider.value, 1.0)

    async def _get_brand_names(self, project_id: UUID) -> List[str]:
        """Get all brand names (primary + aliases) for a project"""
        result = await self.db.execute(
            select(Brand).where(Brand.project_id == project_id)
        )
        brands = result.scalars().all()

        names = []
        for brand in brands:
            names.append(brand.name.lower())
            names.extend([alias.lower() for alias in brand.aliases])

        return names

    def _calculate_mention_score(
        self,
        mentions: List[BrandMention],
        brand_names: List[str]
    ) -> ScoreComponent:
        """Calculate score for brand mention presence"""
        own_mentions = [m for m in mentions if m.is_own_brand]

        if not own_mentions:
            return ScoreComponent(
                name="mention",
                raw_value=0,
                weight=VISIBILITY_SCORE_WEIGHTS["not_mentioned_penalty"],
                weighted_value=VISIBILITY_SCORE_WEIGHTS["not_mentioned_penalty"],
                explanation="Brand was not mentioned in the response",
                contributing_factors=["No brand mention found"]
            )

        # Brand is mentioned
        return ScoreComponent(
            name="mention",
            raw_value=1,
            weight=VISIBILITY_SCORE_WEIGHTS["mention_present"],
            weighted_value=VISIBILITY_SCORE_WEIGHTS["mention_present"],
            explanation=f"Brand mentioned {len(own_mentions)} time(s)",
            contributing_factors=[f"'{m.mentioned_text}' at position {m.mention_position}" for m in own_mentions[:3]]
        )

    def _calculate_position_score(
        self,
        mentions: List[BrandMention],
        brand_names: List[str]
    ) -> ScoreComponent:
        """Calculate score for brand position in mentions"""
        own_mentions = [m for m in mentions if m.is_own_brand]

        if not own_mentions:
            return ScoreComponent(
                name="position",
                raw_value=0,
                weight=0,
                weighted_value=0,
                explanation="Brand not mentioned, no position score",
                contributing_factors=[]
            )

        # Find earliest mention position
        earliest = min(own_mentions, key=lambda m: m.mention_position)

        if earliest.mention_position <= 3:
            return ScoreComponent(
                name="position",
                raw_value=1,
                weight=VISIBILITY_SCORE_WEIGHTS["top_3_position"],
                weighted_value=VISIBILITY_SCORE_WEIGHTS["top_3_position"],
                explanation=f"Brand appears in position #{earliest.mention_position} (top 3)",
                contributing_factors=[f"First mention at position {earliest.mention_position}"]
            )
        else:
            # Partial credit for later positions (linear decay)
            position_factor = max(0, 1 - (earliest.mention_position - 3) * 0.1)
            weighted = VISIBILITY_SCORE_WEIGHTS["top_3_position"] * position_factor

            return ScoreComponent(
                name="position",
                raw_value=position_factor,
                weight=VISIBILITY_SCORE_WEIGHTS["top_3_position"],
                weighted_value=weighted,
                explanation=f"Brand appears at position #{earliest.mention_position}",
                contributing_factors=[f"Position {earliest.mention_position} receives {position_factor:.0%} position credit"]
            )

    def _calculate_citation_score(
        self,
        citations: List[Citation],
        brand_domain: str
    ) -> ScoreComponent:
        """Calculate score for brand being cited as a source"""
        # Check if brand's domain is cited
        brand_citations = [
            c for c in citations
            if brand_domain.lower() in c.cited_url.lower()
        ]

        if brand_citations:
            return ScoreComponent(
                name="citation",
                raw_value=1,
                weight=VISIBILITY_SCORE_WEIGHTS["citation_present"],
                weighted_value=VISIBILITY_SCORE_WEIGHTS["citation_present"],
                explanation=f"Brand domain cited {len(brand_citations)} time(s)",
                contributing_factors=[c.cited_url for c in brand_citations[:3]]
            )

        return ScoreComponent(
            name="citation",
            raw_value=0,
            weight=0,
            weighted_value=0,
            explanation="Brand domain not cited in response",
            contributing_factors=[]
        )

    def _calculate_sentiment_score(
        self,
        mentions: List[BrandMention]
    ) -> ScoreComponent:
        """Calculate score based on sentiment of brand mentions"""
        own_mentions = [m for m in mentions if m.is_own_brand]

        if not own_mentions:
            return ScoreComponent(
                name="sentiment",
                raw_value=0,
                weight=0,
                weighted_value=0,
                explanation="No mentions to analyze for sentiment",
                contributing_factors=[]
            )

        # Calculate average sentiment
        sentiment_counts = {
            SentimentPolarity.POSITIVE: 0,
            SentimentPolarity.NEUTRAL: 0,
            SentimentPolarity.NEGATIVE: 0,
        }
        for m in own_mentions:
            sentiment_counts[m.sentiment] = sentiment_counts.get(m.sentiment, 0) + 1

        total = len(own_mentions)
        positive_ratio = sentiment_counts[SentimentPolarity.POSITIVE] / total
        negative_ratio = sentiment_counts[SentimentPolarity.NEGATIVE] / total

        # Score based on sentiment balance
        if positive_ratio > 0.5:
            return ScoreComponent(
                name="sentiment",
                raw_value=positive_ratio,
                weight=VISIBILITY_SCORE_WEIGHTS["positive_sentiment"],
                weighted_value=VISIBILITY_SCORE_WEIGHTS["positive_sentiment"] * positive_ratio,
                explanation=f"Positive sentiment in {positive_ratio:.0%} of mentions",
                contributing_factors=[f"{sentiment_counts[SentimentPolarity.POSITIVE]} positive, {sentiment_counts[SentimentPolarity.NEUTRAL]} neutral, {sentiment_counts[SentimentPolarity.NEGATIVE]} negative"]
            )
        elif negative_ratio > 0.3:
            return ScoreComponent(
                name="sentiment",
                raw_value=-negative_ratio,
                weight=-5,
                weighted_value=-5 * negative_ratio,
                explanation=f"Negative sentiment in {negative_ratio:.0%} of mentions",
                contributing_factors=[f"Negative sentiment detected in {sentiment_counts[SentimentPolarity.NEGATIVE]} mention(s)"]
            )
        else:
            return ScoreComponent(
                name="sentiment",
                raw_value=0,
                weight=0,
                weighted_value=0,
                explanation="Neutral sentiment overall",
                contributing_factors=["Mixed or neutral sentiment across mentions"]
            )

    def _calculate_competitor_delta(
        self,
        mentions: List[BrandMention]
    ) -> ScoreComponent:
        """Calculate score impact from competitor mentions"""
        own_mentions = [m for m in mentions if m.is_own_brand]
        competitor_mentions = [m for m in mentions if not m.is_own_brand]

        if not competitor_mentions:
            return ScoreComponent(
                name="competitor_delta",
                raw_value=0,
                weight=0,
                weighted_value=0,
                explanation="No competitor mentions",
                contributing_factors=[]
            )

        if not own_mentions:
            return ScoreComponent(
                name="competitor_delta",
                raw_value=-1,
                weight=VISIBILITY_SCORE_WEIGHTS["competitor_before_penalty"] * 2,
                weighted_value=VISIBILITY_SCORE_WEIGHTS["competitor_before_penalty"] * 2,
                explanation="Competitors mentioned but brand was not",
                contributing_factors=[f"Competitor '{m.normalized_name}' at position {m.mention_position}" for m in competitor_mentions[:3]]
            )

        # Check if competitors appear before brand
        earliest_own = min(own_mentions, key=lambda m: m.mention_position)
        competitors_before = [m for m in competitor_mentions if m.mention_position < earliest_own.mention_position]

        if competitors_before:
            penalty_factor = min(1.0, len(competitors_before) * 0.3)
            return ScoreComponent(
                name="competitor_delta",
                raw_value=-penalty_factor,
                weight=VISIBILITY_SCORE_WEIGHTS["competitor_before_penalty"],
                weighted_value=VISIBILITY_SCORE_WEIGHTS["competitor_before_penalty"] * penalty_factor,
                explanation=f"{len(competitors_before)} competitor(s) mentioned before brand",
                contributing_factors=[f"'{m.normalized_name}' at position {m.mention_position}" for m in competitors_before[:3]]
            )

        return ScoreComponent(
            name="competitor_delta",
            raw_value=0,
            weight=0,
            weighted_value=0,
            explanation="Brand mentioned before competitors",
            contributing_factors=["Favorable positioning relative to competitors"]
        )

    async def calculate_score(
        self,
        llm_run_id: UUID,
        save: bool = True
    ) -> ScoreBreakdown:
        """
        Calculate visibility score for an LLM run.

        Args:
            llm_run_id: The LLM run to score
            save: Whether to save the score to database

        Returns:
            ScoreBreakdown with full explanation
        """
        # Get LLM run and response
        result = await self.db.execute(
            select(LLMRun).where(LLMRun.id == llm_run_id)
        )
        llm_run = result.scalar_one()

        result = await self.db.execute(
            select(LLMResponse).where(LLMResponse.llm_run_id == llm_run_id)
        )
        response = result.scalar_one_or_none()

        if not response:
            raise ValueError(f"No response found for LLM run {llm_run_id}")

        # Get project and brand info
        result = await self.db.execute(
            select(Project).where(Project.id == llm_run.project_id)
        )
        project = result.scalar_one()
        brand_names = await self._get_brand_names(project.id)

        # Get mentions and citations
        result = await self.db.execute(
            select(BrandMention).where(BrandMention.response_id == response.id)
        )
        mentions = list(result.scalars().all())

        result = await self.db.execute(
            select(Citation).where(Citation.response_id == response.id)
        )
        citations = list(result.scalars().all())

        # Calculate score components
        mention_score = self._calculate_mention_score(mentions, brand_names)
        position_score = self._calculate_position_score(mentions, brand_names)
        citation_score = self._calculate_citation_score(citations, project.domain)
        sentiment_score = self._calculate_sentiment_score(mentions)
        competitor_delta = self._calculate_competitor_delta(mentions)

        # Calculate totals
        total_raw = (
            mention_score.weighted_value +
            position_score.weighted_value +
            citation_score.weighted_value +
            sentiment_score.weighted_value +
            competitor_delta.weighted_value
        )

        # Apply LLM weight
        llm_weight = self.get_llm_weight(llm_run.provider)
        total_weighted = total_raw * llm_weight

        # Normalize to 0-100 scale
        # Max possible: 30 + 20 + 15 + 10 = 75 (before LLM weight)
        # Min possible: -10 (not mentioned) + -5 (competitor penalty) = -15
        normalized_score = max(0, min(100, (total_raw + 15) / 90 * 100))

        explanation = self._generate_explanation(
            mention_score, position_score, citation_score,
            sentiment_score, competitor_delta, llm_run.provider
        )

        breakdown = ScoreBreakdown(
            mention_score=mention_score,
            position_score=position_score,
            citation_score=citation_score,
            sentiment_score=sentiment_score,
            competitor_delta=competitor_delta,
            total_raw=total_raw,
            llm_weight=llm_weight,
            total_weighted=total_weighted,
            explanation=explanation
        )

        if save:
            await self._save_score(llm_run, breakdown, normalized_score)

        return breakdown

    def _generate_explanation(
        self,
        mention: ScoreComponent,
        position: ScoreComponent,
        citation: ScoreComponent,
        sentiment: ScoreComponent,
        competitor: ScoreComponent,
        provider: LLMProvider
    ) -> str:
        """Generate human-readable score explanation"""
        parts = []

        # Mention
        if mention.weighted_value > 0:
            parts.append(f"Brand was mentioned (+{mention.weighted_value:.0f})")
        else:
            parts.append(f"Brand was not mentioned ({mention.weighted_value:.0f})")

        # Position
        if position.weighted_value > 0:
            parts.append(f"appeared in top positions (+{position.weighted_value:.0f})")

        # Citation
        if citation.weighted_value > 0:
            parts.append(f"cited as source (+{citation.weighted_value:.0f})")

        # Sentiment
        if sentiment.weighted_value > 0:
            parts.append(f"positive sentiment (+{sentiment.weighted_value:.1f})")
        elif sentiment.weighted_value < 0:
            parts.append(f"negative sentiment ({sentiment.weighted_value:.1f})")

        # Competitor
        if competitor.weighted_value < 0:
            parts.append(f"competitors mentioned first ({competitor.weighted_value:.1f})")

        # LLM weight
        llm_weight = self.get_llm_weight(provider)
        parts.append(f"{provider.value} weight: {llm_weight:.1f}x")

        return ". ".join(parts) + "."

    async def _save_score(
        self,
        llm_run: LLMRun,
        breakdown: ScoreBreakdown,
        normalized_score: float
    ):
        """Save calculated score to database"""
        # Get keyword_id from prompt
        keyword_id = None
        if llm_run.prompt_id:
            from app.models import Prompt
            result = await self.db.execute(
                select(Prompt.keyword_id).where(Prompt.id == llm_run.prompt_id)
            )
            keyword_id = result.scalar_one_or_none()

        score = VisibilityScore(
            project_id=llm_run.project_id,
            llm_run_id=llm_run.id,
            keyword_id=keyword_id,
            provider=llm_run.provider,
            mention_score=breakdown.mention_score.weighted_value,
            position_score=breakdown.position_score.weighted_value,
            citation_score=breakdown.citation_score.weighted_value,
            sentiment_score=breakdown.sentiment_score.weighted_value,
            competitor_delta=breakdown.competitor_delta.weighted_value,
            total_score=normalized_score,
            llm_weight=breakdown.llm_weight,
            weighted_score=normalized_score * breakdown.llm_weight,
            score_explanation={
                "mention": {
                    "value": breakdown.mention_score.weighted_value,
                    "explanation": breakdown.mention_score.explanation,
                    "factors": breakdown.mention_score.contributing_factors
                },
                "position": {
                    "value": breakdown.position_score.weighted_value,
                    "explanation": breakdown.position_score.explanation,
                    "factors": breakdown.position_score.contributing_factors
                },
                "citation": {
                    "value": breakdown.citation_score.weighted_value,
                    "explanation": breakdown.citation_score.explanation,
                    "factors": breakdown.citation_score.contributing_factors
                },
                "sentiment": {
                    "value": breakdown.sentiment_score.weighted_value,
                    "explanation": breakdown.sentiment_score.explanation,
                    "factors": breakdown.sentiment_score.contributing_factors
                },
                "competitor": {
                    "value": breakdown.competitor_delta.weighted_value,
                    "explanation": breakdown.competitor_delta.explanation,
                    "factors": breakdown.competitor_delta.contributing_factors
                },
                "summary": breakdown.explanation
            },
            score_date=datetime.utcnow()
        )

        self.db.add(score)
        await self.db.commit()
