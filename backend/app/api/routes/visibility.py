"""
Visibility Analytics API Routes
Endpoints for Share of Voice, Citations, Positions, and Visibility Insights
"""

from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    User, Project, LLMRun, LLMResponse, LLMProvider, Keyword
)
from app.models.visibility import (
    ShareOfVoice, PositionTracking, KeywordAnalysisResult,
    OutreachOpportunity, ContentGap, PromptVolumeEstimate,
    OutreachStatus, ContentGapType
)
from app.utils import get_db
from app.api.routes.auth import get_current_user
from app.services import VisibilityAnalyzer, ShareOfVoiceCalculator, CitationExtractor

router = APIRouter()


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ShareOfVoiceResponse(BaseModel):
    share_of_voice: float
    mention_rate: float
    avg_position: Optional[float]
    first_position_rate: float
    trend: str
    trend_change: Optional[float]
    competitor_shares: dict
    sov_history: list
    total_responses: int
    total_mentions: int
    period_days: int


class PositionSummaryResponse(BaseModel):
    avg_position: Optional[float]
    best_position: Optional[int]
    position_trend: str
    position_history: list
    distribution: dict


class CitationSummaryResponse(BaseModel):
    total_citations: int
    unique_sources: int
    our_domain_citations: int
    our_citation_rate: float
    competitor_citations: int
    competitor_citation_rate: float
    citations_by_llm: dict
    top_sources: list
    new_outreach_opportunities: int
    open_content_gaps: int
    action_items: int
    analysis_period_days: int


class KeywordAnalysisResponse(BaseModel):
    keyword_id: str
    keyword: str
    provider: str
    brand_mentioned: bool
    brand_position: Optional[int]
    total_brands_mentioned: int
    our_domain_cited: bool
    total_citations: int
    visibility_score: float
    sentiment: str
    analysis_date: str


class OutreachOpportunityResponse(BaseModel):
    id: str
    page_url: str
    page_domain: str
    opportunity_type: str
    opportunity_reason: str
    citation_count: int
    llms_citing: list
    relevant_keywords: list
    priority_score: float
    impact_estimate: str
    effort_estimate: str
    status: str


class ContentGapResponse(BaseModel):
    id: str
    gap_type: str
    gap_description: str
    related_keywords: list
    content_type_needed: str
    opportunity_score: float
    recommended_action: str
    action_items: list
    priority: str
    is_addressed: bool


class PromptVolumeResponse(BaseModel):
    topic: str
    total_estimated_prompts: int
    chatgpt_volume: int
    claude_volume: int
    gemini_volume: int
    perplexity_volume: int
    opportunity_score: float
    competition_level: str
    volume_trend: str


class VisibilityDashboardResponse(BaseModel):
    share_of_voice: ShareOfVoiceResponse
    position_summary: PositionSummaryResponse
    citation_summary: CitationSummaryResponse
    recent_analyses: list
    top_opportunities: list


# ============================================================================
# SHARE OF VOICE ENDPOINTS
# ============================================================================

@router.get("/sov/{project_id}", response_model=ShareOfVoiceResponse)
async def get_share_of_voice(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get Share of Voice metrics for a project."""
    # Verify project ownership
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    calculator = ShareOfVoiceCalculator(db)
    summary = await calculator.get_sov_summary(project_id, days)

    return ShareOfVoiceResponse(**summary)


@router.get("/sov/{project_id}/by-keyword")
async def get_sov_by_keyword(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get Share of Voice broken down by keyword."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get SOV by keyword
    result = await db.execute(
        select(ShareOfVoice)
        .where(
            and_(
                ShareOfVoice.project_id == project_id,
                ShareOfVoice.period_start >= start_date,
                ShareOfVoice.keyword_id.isnot(None)
            )
        )
        .options(selectinload(ShareOfVoice.keyword))
        .order_by(desc(ShareOfVoice.share_of_voice))
    )
    sov_records = result.scalars().all()

    return [
        {
            "keyword_id": str(r.keyword_id),
            "keyword": r.keyword.keyword if r.keyword else "Unknown",
            "share_of_voice": r.share_of_voice,
            "mention_count": r.brand_mention_count,
            "avg_position": r.avg_mention_position,
            "trend": r.trend,
            "competitor_shares": r.competitor_shares
        }
        for r in sov_records
    ]


@router.get("/sov/{project_id}/by-llm")
async def get_sov_by_llm(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get Share of Voice broken down by LLM provider."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    result = await db.execute(
        select(ShareOfVoice)
        .where(
            and_(
                ShareOfVoice.project_id == project_id,
                ShareOfVoice.period_start >= start_date,
                ShareOfVoice.keyword_id.is_(None),
                ShareOfVoice.provider.isnot(None)
            )
        )
        .order_by(desc(ShareOfVoice.share_of_voice))
    )
    sov_records = result.scalars().all()

    return [
        {
            "provider": r.provider.value,
            "share_of_voice": r.share_of_voice,
            "mention_count": r.brand_mention_count,
            "avg_position": r.avg_mention_position,
            "trend": r.trend
        }
        for r in sov_records
    ]


# ============================================================================
# POSITION TRACKING ENDPOINTS
# ============================================================================

@router.get("/positions/{project_id}", response_model=PositionSummaryResponse)
async def get_position_summary(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get position tracking summary for a project."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    calculator = ShareOfVoiceCalculator(db)
    summary = await calculator.get_position_summary(project_id, days)

    return PositionSummaryResponse(**summary)


@router.get("/positions/{project_id}/ranking")
async def get_entity_ranking(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get ranking of all entities (brand + competitors) by average position."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    result = await db.execute(
        select(
            PositionTracking.entity_name,
            PositionTracking.is_own_brand,
            func.avg(PositionTracking.avg_position).label("avg_pos"),
            func.sum(PositionTracking.mentions_analyzed).label("total_mentions")
        )
        .where(
            and_(
                PositionTracking.project_id == project_id,
                PositionTracking.tracking_date >= start_date
            )
        )
        .group_by(PositionTracking.entity_name, PositionTracking.is_own_brand)
        .order_by("avg_pos")
    )

    rankings = result.all()

    return [
        {
            "rank": i + 1,
            "entity_name": r.entity_name,
            "is_own_brand": r.is_own_brand,
            "avg_position": round(r.avg_pos, 2) if r.avg_pos else None,
            "total_mentions": r.total_mentions
        }
        for i, r in enumerate(rankings)
    ]


# ============================================================================
# CITATION ENDPOINTS
# ============================================================================

@router.get("/citations/{project_id}", response_model=CitationSummaryResponse)
async def get_citation_summary(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get citation analysis summary for a project."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    extractor = CitationExtractor(db)
    summary = await extractor.get_citation_summary(project_id, days)

    return CitationSummaryResponse(**summary)


@router.get("/citations/{project_id}/sources")
async def get_citation_sources(
    project_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get ranked list of citation sources by authority."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    extractor = CitationExtractor(db)
    sources = await extractor.get_source_authority_ranking(project_id, limit)

    return sources


# ============================================================================
# KEYWORD ANALYSIS ENDPOINTS
# ============================================================================

@router.get("/analysis/{project_id}/keywords")
async def get_keyword_analyses(
    project_id: UUID,
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get recent keyword analysis results."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(KeywordAnalysisResult)
        .join(LLMRun)
        .where(LLMRun.project_id == project_id)
        .options(selectinload(KeywordAnalysisResult.keyword))
        .order_by(desc(KeywordAnalysisResult.created_at))
        .limit(limit)
    )
    analyses = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "keyword_id": str(a.keyword_id) if a.keyword_id else None,
            "keyword": a.keyword.keyword if a.keyword else "Unknown",
            "provider": a.provider.value,
            "brand_mentioned": a.brand_mentioned,
            "brand_position": a.brand_position,
            "total_brands_mentioned": a.total_brands_mentioned,
            "our_domain_cited": a.our_domain_cited,
            "total_citations": a.total_citations,
            "visibility_score": a.total_visibility_score,
            "sentiment": a.overall_sentiment.value if a.overall_sentiment else "neutral",
            "competitors_mentioned": a.competitors_mentioned,
            "analysis_date": a.created_at.isoformat()
        }
        for a in analyses
    ]


@router.get("/analysis/{project_id}/keyword/{keyword_id}")
async def get_keyword_analysis_detail(
    project_id: UUID,
    keyword_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed analysis for a specific keyword."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(KeywordAnalysisResult)
        .join(LLMRun)
        .where(
            and_(
                LLMRun.project_id == project_id,
                KeywordAnalysisResult.keyword_id == keyword_id
            )
        )
        .order_by(desc(KeywordAnalysisResult.created_at))
        .limit(10)
    )
    analyses = result.scalars().all()

    keyword = await db.get(Keyword, keyword_id)

    return {
        "keyword_id": str(keyword_id),
        "keyword": keyword.keyword if keyword else "Unknown",
        "analyses_by_llm": [
            {
                "provider": a.provider.value,
                "brand_mentioned": a.brand_mentioned,
                "brand_position": a.brand_position,
                "total_citations": a.total_citations,
                "our_domain_cited": a.our_domain_cited,
                "visibility_score": a.total_visibility_score,
                "citations": a.citations_summary,
                "competitors": a.competitors_mentioned,
                "fan_out_queries": a.fan_out_queries,
                "sentiment": a.overall_sentiment.value if a.overall_sentiment else "neutral",
                "analysis_date": a.created_at.isoformat()
            }
            for a in analyses
        ]
    }


# ============================================================================
# OUTREACH OPPORTUNITIES ENDPOINTS
# ============================================================================

@router.get("/opportunities/{project_id}")
async def get_outreach_opportunities(
    project_id: UUID,
    status: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get outreach opportunities for a project."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    query = select(OutreachOpportunity).where(
        OutreachOpportunity.project_id == project_id
    )

    if status:
        query = query.where(OutreachOpportunity.status == OutreachStatus(status))

    query = query.order_by(desc(OutreachOpportunity.priority_score)).limit(limit)

    result = await db.execute(query)
    opportunities = result.scalars().all()

    return [
        {
            "id": str(o.id),
            "page_url": o.page_url,
            "page_domain": o.page_domain,
            "page_title": o.page_title,
            "opportunity_type": o.opportunity_type,
            "opportunity_reason": o.opportunity_reason,
            "citation_count": o.citation_count,
            "llms_citing": o.llms_citing,
            "relevant_keywords": o.relevant_keywords,
            "priority_score": o.priority_score,
            "impact_estimate": o.impact_estimate,
            "effort_estimate": o.effort_estimate,
            "status": o.status.value,
            "created_at": o.created_at.isoformat()
        }
        for o in opportunities
    ]


@router.post("/opportunities/{project_id}/generate")
async def generate_opportunities(
    project_id: UUID,
    min_citations: int = Query(3, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate new outreach opportunities based on citation analysis."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    extractor = CitationExtractor(db)
    opportunities = await extractor.identify_outreach_opportunities(project_id, min_citations)

    return {
        "generated": len(opportunities),
        "message": f"Generated {len(opportunities)} new outreach opportunities"
    }


@router.patch("/opportunities/{opportunity_id}/status")
async def update_opportunity_status(
    opportunity_id: UUID,
    status: str,
    notes: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update the status of an outreach opportunity."""
    opportunity = await db.get(OutreachOpportunity, opportunity_id)
    if not opportunity:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    # Verify ownership
    project = await db.get(Project, opportunity.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    opportunity.status = OutreachStatus(status)
    if notes:
        opportunity.notes = notes
    if status == "contacted":
        opportunity.last_contacted_at = datetime.utcnow()

    await db.commit()

    return {"status": "updated", "new_status": status}


# ============================================================================
# CONTENT GAPS ENDPOINTS
# ============================================================================

@router.get("/gaps/{project_id}")
async def get_content_gaps(
    project_id: UUID,
    priority: Optional[str] = None,
    addressed: bool = False,
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get content gaps for a project."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    query = select(ContentGap).where(
        and_(
            ContentGap.project_id == project_id,
            ContentGap.is_addressed == addressed
        )
    )

    if priority:
        query = query.where(ContentGap.priority == priority)

    query = query.order_by(desc(ContentGap.opportunity_score)).limit(limit)

    result = await db.execute(query)
    gaps = result.scalars().all()

    return [
        {
            "id": str(g.id),
            "gap_type": g.gap_type.value,
            "gap_description": g.gap_description,
            "related_keywords": g.related_keywords,
            "content_type_needed": g.content_type_needed,
            "content_format": g.content_format,
            "opportunity_score": g.opportunity_score,
            "recommended_action": g.recommended_action,
            "action_items": g.action_items,
            "priority": g.priority,
            "effort_required": g.effort_required,
            "competitor_examples": g.competitor_examples,
            "is_addressed": g.is_addressed,
            "created_at": g.created_at.isoformat()
        }
        for g in gaps
    ]


@router.post("/gaps/{project_id}/detect")
async def detect_content_gaps(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Detect new content gaps based on citation analysis."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    extractor = CitationExtractor(db)
    gaps = await extractor.detect_content_gaps(project_id)

    return {
        "detected": len(gaps),
        "message": f"Detected {len(gaps)} content gaps"
    }


@router.patch("/gaps/{gap_id}/address")
async def mark_gap_addressed(
    gap_id: UUID,
    addressed_url: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a content gap as addressed."""
    gap = await db.get(ContentGap, gap_id)
    if not gap:
        raise HTTPException(status_code=404, detail="Content gap not found")

    project = await db.get(Project, gap.project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Content gap not found")

    gap.is_addressed = True
    gap.addressed_url = addressed_url
    gap.addressed_at = datetime.utcnow()

    await db.commit()

    return {"status": "addressed", "addressed_url": addressed_url}


# ============================================================================
# AI PROMPT VOLUME ENDPOINTS
# ============================================================================

@router.get("/volume/{project_id}")
async def get_prompt_volume_estimates(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get AI prompt volume estimates for project keywords."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(PromptVolumeEstimate)
        .where(PromptVolumeEstimate.project_id == project_id)
        .order_by(desc(PromptVolumeEstimate.total_estimated_prompts))
    )
    volumes = result.scalars().all()

    return [
        {
            "id": str(v.id),
            "topic": v.topic,
            "keyword_id": str(v.keyword_id) if v.keyword_id else None,
            "total_estimated_prompts": v.total_estimated_prompts,
            "chatgpt_volume": v.chatgpt_volume,
            "claude_volume": v.claude_volume,
            "gemini_volume": v.gemini_volume,
            "perplexity_volume": v.perplexity_volume,
            "opportunity_score": v.opportunity_score,
            "competition_level": v.competition_level,
            "volume_trend": v.volume_trend,
            "google_search_volume": v.google_search_volume,
            "estimate_month": v.estimate_month.isoformat() if v.estimate_month else None
        }
        for v in volumes
    ]


@router.post("/volume/{project_id}/estimate")
async def generate_volume_estimates(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Generate AI prompt volume estimates for all project keywords."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.services.volume_estimator import VolumeEstimator
    estimator = VolumeEstimator(db)

    estimates = await estimator.estimate_volume_for_project(project_id)
    summary = await estimator.get_volume_summary(project_id)

    return {
        "estimated_keywords": len(estimates),
        "total_monthly_volume": summary["total_monthly_volume"],
        "platform_breakdown": summary["platform_breakdown"],
        "opportunity_summary": summary["opportunity_summary"],
        "message": f"Generated volume estimates for {len(estimates)} keywords"
    }


@router.get("/volume/{project_id}/summary")
async def get_volume_summary(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get volume estimation summary for a project."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    from app.services.volume_estimator import VolumeEstimator
    estimator = VolumeEstimator(db)

    summary = await estimator.get_volume_summary(project_id)
    return summary


# ============================================================================
# KEYWORD RANKING ENDPOINTS
# ============================================================================

@router.get("/rankings/{project_id}")
async def get_keyword_rankings(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get keyword rankings showing which keywords rank in top positions.
    Returns keywords with their position across different LLMs.
    """
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get latest analysis results per keyword per provider
    result = await db.execute(
        select(KeywordAnalysisResult)
        .join(LLMRun)
        .where(
            and_(
                LLMRun.project_id == project_id,
                KeywordAnalysisResult.created_at >= start_date,
                KeywordAnalysisResult.brand_mentioned == True
            )
        )
        .options(selectinload(KeywordAnalysisResult.keyword))
        .order_by(KeywordAnalysisResult.brand_position.asc())
    )
    analyses = result.scalars().all()

    # Group by keyword
    keyword_data = {}
    for analysis in analyses:
        if not analysis.keyword:
            continue

        kw_id = str(analysis.keyword_id)
        if kw_id not in keyword_data:
            keyword_data[kw_id] = {
                "keyword_id": kw_id,
                "keyword": analysis.keyword.keyword,
                "positions_by_llm": {},
                "best_position": None,
                "avg_position": None,
                "total_mentions": 0,
                "top_10_count": 0,
                "visibility_scores": [],
            }

        provider = analysis.provider.value
        position = analysis.brand_position

        # Track position by LLM
        if provider not in keyword_data[kw_id]["positions_by_llm"]:
            keyword_data[kw_id]["positions_by_llm"][provider] = {
                "position": position,
                "visibility_score": analysis.total_visibility_score,
                "mentioned": True,
                "our_domain_cited": analysis.our_domain_cited,
            }

        keyword_data[kw_id]["total_mentions"] += 1
        if position and position <= 10:
            keyword_data[kw_id]["top_10_count"] += 1

        if position:
            if keyword_data[kw_id]["best_position"] is None or position < keyword_data[kw_id]["best_position"]:
                keyword_data[kw_id]["best_position"] = position

        keyword_data[kw_id]["visibility_scores"].append(analysis.total_visibility_score or 0)

    # Calculate averages and sort
    rankings = []
    for kw_id, data in keyword_data.items():
        positions = [p["position"] for p in data["positions_by_llm"].values() if p["position"]]
        data["avg_position"] = round(sum(positions) / len(positions), 1) if positions else None
        data["avg_visibility_score"] = round(sum(data["visibility_scores"]) / len(data["visibility_scores"]), 1) if data["visibility_scores"] else 0
        del data["visibility_scores"]  # Remove raw scores
        rankings.append(data)

    # Sort by best position (top rankings first)
    rankings.sort(key=lambda x: (x["best_position"] or 999, -(x["top_10_count"] or 0)))

    return {
        "rankings": rankings,
        "total_keywords_with_mentions": len(rankings),
        "top_10_keywords": len([r for r in rankings if r["best_position"] and r["best_position"] <= 10]),
        "analysis_period_days": days
    }


@router.get("/rankings/{project_id}/keyword/{keyword_id}")
async def get_keyword_ranking_detail(
    project_id: UUID,
    keyword_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed ranking breakdown for a specific keyword across all LLMs.
    """
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    keyword = await db.get(Keyword, keyword_id)
    if not keyword or keyword.project_id != project_id:
        raise HTTPException(status_code=404, detail="Keyword not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get all analyses for this keyword
    result = await db.execute(
        select(KeywordAnalysisResult)
        .join(LLMRun)
        .where(
            and_(
                LLMRun.project_id == project_id,
                KeywordAnalysisResult.keyword_id == keyword_id,
                KeywordAnalysisResult.created_at >= start_date
            )
        )
        .order_by(desc(KeywordAnalysisResult.created_at))
    )
    analyses = result.scalars().all()

    # Group by provider
    llm_breakdown = {}
    for provider in ["openai", "anthropic", "google", "perplexity"]:
        provider_analyses = [a for a in analyses if a.provider.value == provider]

        if provider_analyses:
            latest = provider_analyses[0]
            positions = [a.brand_position for a in provider_analyses if a.brand_position]
            visibility_scores = [a.total_visibility_score for a in provider_analyses if a.total_visibility_score]

            llm_breakdown[provider] = {
                "brand_mentioned": latest.brand_mentioned,
                "current_position": latest.brand_position,
                "avg_position": round(sum(positions) / len(positions), 1) if positions else None,
                "best_position": min(positions) if positions else None,
                "worst_position": max(positions) if positions else None,
                "mention_count": sum(1 for a in provider_analyses if a.brand_mentioned),
                "total_analyses": len(provider_analyses),
                "visibility_score": latest.total_visibility_score,
                "avg_visibility_score": round(sum(visibility_scores) / len(visibility_scores), 1) if visibility_scores else 0,
                "our_domain_cited": latest.our_domain_cited,
                "total_citations": latest.total_citations,
                "competitors_mentioned": latest.competitors_mentioned or [],
                "sentiment": latest.overall_sentiment.value if latest.overall_sentiment else "neutral",
                "last_analysis": latest.created_at.isoformat(),
            }
        else:
            llm_breakdown[provider] = {
                "brand_mentioned": False,
                "current_position": None,
                "avg_position": None,
                "best_position": None,
                "worst_position": None,
                "mention_count": 0,
                "total_analyses": 0,
                "visibility_score": 0,
                "avg_visibility_score": 0,
                "our_domain_cited": False,
                "total_citations": 0,
                "competitors_mentioned": [],
                "sentiment": "neutral",
                "last_analysis": None,
            }

    # Position history for chart
    position_history = []
    for analysis in reversed(analyses[:30]):  # Last 30 analyses
        position_history.append({
            "date": analysis.created_at.isoformat(),
            "provider": analysis.provider.value,
            "position": analysis.brand_position,
            "visibility_score": analysis.total_visibility_score,
        })

    return {
        "keyword_id": str(keyword_id),
        "keyword": keyword.keyword,
        "llm_breakdown": llm_breakdown,
        "position_history": position_history,
        "analysis_period_days": days,
    }


# ============================================================================
# KEYWORD RANKING RESULTS - DETAILED VIEW
# ============================================================================

@router.get("/ranking-results/{project_id}/keyword/{keyword_id}")
async def get_keyword_ranking_results(
    project_id: UUID,
    keyword_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete ranking results for a keyword - who ranked in top positions
    with full citation details and reasons why they appeared.
    """
    from app.models import Citation, CitationSource, BrandMention, LLMResponse

    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    keyword = await db.get(Keyword, keyword_id)
    if not keyword or keyword.project_id != project_id:
        raise HTTPException(status_code=404, detail="Keyword not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get keyword analysis results which have keyword_id directly
    # This works for both sync execution (no prompt) and async execution (with prompt)
    analysis_results = await db.execute(
        select(KeywordAnalysisResult)
        .where(
            and_(
                KeywordAnalysisResult.keyword_id == keyword_id,
                KeywordAnalysisResult.created_at >= start_date
            )
        )
        .options(selectinload(KeywordAnalysisResult.keyword))
        .order_by(desc(KeywordAnalysisResult.created_at))
    )
    analyses = analysis_results.scalars().all()

    # Get LLM runs with responses for brand mentions and citations
    # Use the response_id from KeywordAnalysisResult to get the data
    response_ids = [a.response_id for a in analyses if a.response_id]

    responses_with_data = {}
    if response_ids:
        responses_result = await db.execute(
            select(LLMResponse)
            .where(LLMResponse.id.in_(response_ids))
            .options(
                selectinload(LLMResponse.brand_mentions),
                selectinload(LLMResponse.citations).selectinload(Citation.source),
                selectinload(LLMResponse.llm_run)
            )
        )
        for resp in responses_result.scalars().all():
            responses_with_data[resp.id] = resp

    # Build ranking results by LLM from analyses
    ranking_results = {}

    for analysis in analyses:
        provider = analysis.provider.value

        # Skip if we already have newer data for this provider
        if provider in ranking_results:
            continue

        # Get the response with brand mentions and citations
        response = responses_with_data.get(analysis.response_id) if analysis.response_id else None
        llm_run = response.llm_run if response else None

        ranking_results[provider] = {
            "provider": provider,
            "model": analysis.model_name or (llm_run.model_name if llm_run else "unknown"),
            "last_run": analysis.created_at.isoformat(),
            "raw_response": response.raw_response[:2000] if response and response.raw_response else None,
            "ranked_entities": [],
            "citations": [],
            "our_brand_position": analysis.brand_position,
            "our_brand_mentioned": analysis.brand_mentioned,
            "total_brands_mentioned": analysis.total_brands_mentioned or 0,
            "visibility_score": analysis.total_visibility_score,
            "mention_type": analysis.mention_type.value if analysis.mention_type else None,
            "competitors_mentioned": analysis.competitors_mentioned or [],
            "fan_out_queries": analysis.fan_out_queries or [],
            "has_shopping_recommendations": analysis.has_shopping_recommendations,
        }

        # Get brand mentions from response if available
        if response and response.brand_mentions:
            mentions = sorted(response.brand_mentions, key=lambda m: m.mention_position)
            ranked_entities = []

            for mention in mentions:
                entity_data = {
                    "position": mention.mention_position,
                    "name": mention.normalized_name,
                    "mentioned_text": mention.mentioned_text,
                    "is_own_brand": mention.is_own_brand,
                    "context": mention.context_snippet,
                    "sentiment": mention.sentiment.value if mention.sentiment else "neutral",
                    "sentiment_score": mention.sentiment_score,
                    "match_type": mention.match_type,
                    "match_confidence": mention.match_confidence,
                }
                ranked_entities.append(entity_data)

            ranking_results[provider]["ranked_entities"] = ranked_entities
        else:
            # Use competitors_mentioned from analysis as fallback
            ranked_entities = []
            if analysis.brand_mentioned:
                ranked_entities.append({
                    "position": analysis.brand_position or 1,
                    "name": "Your Brand",
                    "mentioned_text": "Your Brand",
                    "is_own_brand": True,
                    "context": analysis.mention_context,
                    "sentiment": "neutral",
                    "sentiment_score": 0,
                    "match_type": "exact",
                    "match_confidence": 1.0,
                })
            for comp in (analysis.competitors_mentioned or []):
                if isinstance(comp, dict):
                    ranked_entities.append({
                        "position": comp.get("position", 0),
                        "name": comp.get("name", "Unknown"),
                        "mentioned_text": comp.get("name", "Unknown"),
                        "is_own_brand": False,
                        "context": comp.get("context"),
                        "sentiment": "neutral",
                        "sentiment_score": 0,
                        "match_type": "extracted",
                        "match_confidence": 0.8,
                    })
            ranked_entities.sort(key=lambda x: x["position"])
            ranking_results[provider]["ranked_entities"] = ranked_entities

        # Get citations from response if available
        if response and response.citations:
            citations = sorted(response.citations, key=lambda c: c.citation_position or 999)
            citation_details = []

            for citation in citations:
                citation_data = {
                    "position": citation.citation_position,
                    "url": citation.cited_url,
                    "domain": citation.source.domain if citation.source else None,
                    "category": citation.source.category.value if citation.source and citation.source.category else "unknown",
                    "domain_authority": citation.source.domain_authority if citation.source else None,
                    "anchor_text": citation.anchor_text,
                    "context": citation.context_snippet,
                    "is_valid": citation.is_valid_url,
                    "is_accessible": citation.is_accessible,
                    "is_hallucinated": citation.is_hallucinated,
                    "is_our_domain": citation.source.domain == project.domain if citation.source else False,
                }
                citation_details.append(citation_data)

            ranking_results[provider]["citations"] = citation_details
        else:
            # Use citations_summary from analysis as fallback
            citation_details = []
            for i, cit in enumerate(analysis.citations_summary or []):
                if isinstance(cit, dict):
                    citation_details.append({
                        "position": cit.get("position", i + 1),
                        "url": cit.get("url", ""),
                        "domain": cit.get("domain"),
                        "category": cit.get("purpose", "unknown"),
                        "domain_authority": None,
                        "anchor_text": cit.get("anchor_text"),
                        "context": cit.get("context"),
                        "is_valid": True,
                        "is_accessible": None,
                        "is_hallucinated": False,
                        "is_our_domain": cit.get("is_own_domain", False),
                    })
            ranking_results[provider]["citations"] = citation_details

    return {
        "keyword_id": str(keyword_id),
        "keyword": keyword.keyword,
        "project_domain": project.domain,
        "analysis_period_days": days,
        "results_by_llm": ranking_results,
        "summary": {
            "total_llms_analyzed": len(ranking_results),
            "llms_mentioning_us": sum(1 for r in ranking_results.values() if r.get("our_brand_mentioned")),
            "best_position": min(
                (r.get("our_brand_position") for r in ranking_results.values() if r.get("our_brand_position")),
                default=None
            ),
            "total_citations_across_llms": sum(len(r.get("citations", [])) for r in ranking_results.values()),
        }
    }


@router.get("/ranking-results/{project_id}")
async def get_all_keyword_ranking_results(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get ranking results summary for all keywords in a project.
    Shows who ranked in top positions for each keyword.
    """
    from app.models import BrandMention, LLMResponse

    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)

    # Get all keywords for this project
    keywords_result = await db.execute(
        select(Keyword)
        .where(
            and_(
                Keyword.project_id == project_id,
                Keyword.is_active == True
            )
        )
        .limit(limit)
    )
    keywords = keywords_result.scalars().all()

    results = []

    for keyword in keywords:
        # Get latest analysis for each LLM
        analysis_result = await db.execute(
            select(KeywordAnalysisResult)
            .join(LLMRun)
            .where(
                and_(
                    LLMRun.project_id == project_id,
                    KeywordAnalysisResult.keyword_id == keyword.id,
                    KeywordAnalysisResult.created_at >= start_date
                )
            )
            .order_by(desc(KeywordAnalysisResult.created_at))
        )
        analyses = analysis_result.scalars().all()

        # Get unique latest analysis per provider
        seen_providers = set()
        latest_analyses = []
        for a in analyses:
            if a.provider.value not in seen_providers:
                seen_providers.add(a.provider.value)
                latest_analyses.append(a)

        # Build top rankers list
        top_rankers = []
        our_positions = {}
        citations_by_llm = {}

        for analysis in latest_analyses:
            provider = analysis.provider.value

            # Track our position
            if analysis.brand_mentioned and analysis.brand_position:
                our_positions[provider] = analysis.brand_position

            # Get competitors that ranked
            if analysis.competitors_mentioned:
                for comp in analysis.competitors_mentioned:
                    if isinstance(comp, dict):
                        top_rankers.append({
                            "name": comp.get("name", "Unknown"),
                            "position": comp.get("position"),
                            "provider": provider,
                        })

            # Track citations
            citations_by_llm[provider] = {
                "total": analysis.total_citations,
                "our_domain_cited": analysis.our_domain_cited,
            }

        # Sort top rankers by position
        top_rankers.sort(key=lambda x: x.get("position") or 999)

        keyword_result = {
            "keyword_id": str(keyword.id),
            "keyword": keyword.keyword,
            "our_positions": our_positions,
            "best_our_position": min(our_positions.values()) if our_positions else None,
            "top_rankers": top_rankers[:10],  # Top 10 competitors
            "total_competitors_found": len(set(r.get("name") for r in top_rankers)),
            "citations_by_llm": citations_by_llm,
            "llms_analyzed": len(latest_analyses),
            "llms_mentioning_us": len(our_positions),
        }
        results.append(keyword_result)

    # Sort by best position (keywords where we rank well first)
    results.sort(key=lambda x: (x.get("best_our_position") or 999, -x.get("llms_mentioning_us", 0)))

    return {
        "project_id": str(project_id),
        "project_domain": project.domain,
        "analysis_period_days": days,
        "total_keywords": len(results),
        "keywords_with_mentions": len([r for r in results if r.get("best_our_position")]),
        "results": results,
    }


# ============================================================================
# VISIBILITY DASHBOARD
# ============================================================================

@router.get("/dashboard/{project_id}")
async def get_visibility_dashboard(
    project_id: UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get comprehensive visibility dashboard data."""
    project = await db.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get all summaries
    sov_calc = ShareOfVoiceCalculator(db)
    citation_ext = CitationExtractor(db)

    sov_summary = await sov_calc.get_sov_summary(project_id, days)
    position_summary = await sov_calc.get_position_summary(project_id, days)
    citation_summary = await citation_ext.get_citation_summary(project_id, days)

    # Get recent analyses
    result = await db.execute(
        select(KeywordAnalysisResult)
        .join(LLMRun)
        .where(LLMRun.project_id == project_id)
        .order_by(desc(KeywordAnalysisResult.created_at))
        .limit(10)
    )
    recent_analyses = result.scalars().all()

    # Get top opportunities
    result = await db.execute(
        select(OutreachOpportunity)
        .where(
            and_(
                OutreachOpportunity.project_id == project_id,
                OutreachOpportunity.status == OutreachStatus.NEW
            )
        )
        .order_by(desc(OutreachOpportunity.priority_score))
        .limit(5)
    )
    top_opportunities = result.scalars().all()

    return {
        "share_of_voice": sov_summary,
        "position_summary": position_summary,
        "citation_summary": citation_summary,
        "recent_analyses": [
            {
                "keyword": a.keyword.keyword if a.keyword else "Unknown",
                "provider": a.provider.value,
                "visibility_score": a.total_visibility_score,
                "brand_mentioned": a.brand_mentioned,
                "date": a.created_at.isoformat()
            }
            for a in recent_analyses
        ],
        "top_opportunities": [
            {
                "domain": o.page_domain,
                "citation_count": o.citation_count,
                "priority_score": o.priority_score,
                "opportunity_type": o.opportunity_type
            }
            for o in top_opportunities
        ]
    }
