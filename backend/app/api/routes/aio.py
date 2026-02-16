"""
AI Overview (AIO) Routes
Fetches and analyzes Google AI Overview data using Serper.dev API
"""

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.models import Project, Keyword, User
from app.models.visibility import AIOResult
from app.utils import get_db
from app.api.middleware.auth import get_current_user
from app.config import get_settings
from app.services.serper_service import SerperService

router = APIRouter()
settings = get_settings()


# Response Models
class AIOSource(BaseModel):
    title: Optional[str] = None
    link: Optional[str] = None
    snippet: Optional[str] = None


class CompetitorInAIO(BaseModel):
    name: str
    position: int
    context: Optional[str] = None


class AIOAnalysisResponse(BaseModel):
    keyword_id: str
    keyword: str
    query: str
    search_timestamp: str
    country: str

    # AIO Presence
    has_ai_overview: bool
    aio_type: Optional[str] = None
    aio_text: Optional[str] = None

    # Brand Analysis
    brand_in_aio: bool
    brand_aio_position: Optional[int] = None
    brand_aio_context: Optional[str] = None
    domain_in_aio: bool
    domain_aio_position: Optional[int] = None

    # Sources & Mentions
    aio_sources: List[dict] = []
    aio_mentions: List[dict] = []

    # Competitor Analysis
    competitors_in_aio: List[CompetitorInAIO] = []

    # Organic Results
    brand_in_organic: bool
    brand_organic_position: Optional[int] = None
    competitors_in_organic: List[dict] = []
    organic_results: List[dict] = []

    # Knowledge Graph
    has_knowledge_graph: bool = False


class BulkAIORequest(BaseModel):
    keyword_ids: Optional[List[UUID]] = None
    # Note: country is now set at project level


class BulkAIOResponse(BaseModel):
    success: bool
    total_keywords: int
    analyzed: int
    errors: List[str] = []
    results: List[AIOAnalysisResponse] = []


@router.get("/test")
async def test_serper_connection(
    user: User = Depends(get_current_user),
):
    """Test Serper.dev API connection"""
    if not settings.SERPER_API_KEY:
        raise HTTPException(status_code=400, detail="SERPER_API_KEY not configured")

    from app.services.serper_service import test_serper_api
    result = await test_serper_api(settings.SERPER_API_KEY)

    if not result["success"]:
        raise HTTPException(status_code=500, detail=f"Serper API error: {result.get('error')}")

    return result


@router.get("/{project_id}/keyword/{keyword_id}", response_model=AIOAnalysisResponse)
async def get_aio_for_keyword(
    project_id: UUID,
    keyword_id: UUID,
    force_refresh: bool = Query(False, description="Force new API call instead of using cached data"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Get Google AI Overview data for a specific keyword.
    Uses project's country setting for location-specific results.
    Checks brand and competitor presence in AIO.
    """
    if not settings.SERPER_API_KEY:
        raise HTTPException(status_code=400, detail="SERPER_API_KEY not configured. Please add it to your .env file.")

    # Verify project ownership and get project data
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Use project's country setting
    country = project.country or "in"

    # Get keyword
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id, Keyword.project_id == project_id)
    )
    keyword = result.scalar_one_or_none()
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    # Check for cached result (less than 24 hours old)
    if not force_refresh:
        result = await db.execute(
            select(AIOResult).where(
                and_(
                    AIOResult.keyword_id == keyword_id,
                    AIOResult.country == country,
                    AIOResult.created_at >= datetime.utcnow() - timedelta(hours=24)
                )
            ).order_by(AIOResult.created_at.desc())
        )
        cached = result.scalar_one_or_none()
        if cached:
            return _aio_result_to_response(cached, keyword.keyword)

    # Get brand name and competitors
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.brands), selectinload(Project.competitors))
        .where(Project.id == project_id)
    )
    project = result.scalar_one()

    brand_name = project.brands[0].name if project.brands else project.domain.split(".")[0]
    brand_domain = project.domain
    competitors = [c.name for c in project.competitors]

    # Fetch AIO data from Serper
    serper = SerperService(settings.SERPER_API_KEY)
    try:
        aio_data = await serper.get_ai_overview(
            query=keyword.keyword,
            brand_name=brand_name,
            brand_domain=brand_domain,
            competitors=competitors,
            country=country
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Serper API error: {str(e)}")

    # Save result to database
    aio_result = AIOResult(
        keyword_id=keyword_id,
        project_id=project_id,
        country=country,
        has_ai_overview=aio_data["has_ai_overview"],
        aio_type=aio_data.get("aio_type"),
        aio_text=aio_data.get("aio_text"),
        brand_in_aio=aio_data["brand_in_aio"],
        brand_aio_position=aio_data.get("brand_aio_position"),
        brand_aio_context=aio_data.get("brand_aio_context"),
        domain_in_aio=aio_data["domain_in_aio"],
        domain_aio_position=aio_data.get("domain_aio_position"),
        aio_sources=aio_data.get("aio_sources", []),
        aio_mentions=aio_data.get("aio_mentions", []),
        competitors_in_aio=aio_data.get("competitors_in_aio", []),
        brand_in_organic=aio_data["brand_in_organic"],
        brand_organic_position=aio_data.get("brand_organic_position"),
        competitors_in_organic=aio_data.get("competitors_in_organic", []),
        organic_results=aio_data.get("organic_results", []),
        has_knowledge_graph=aio_data.get("has_knowledge_graph", False),
        raw_response=aio_data
    )
    db.add(aio_result)
    await db.commit()

    return AIOAnalysisResponse(
        keyword_id=str(keyword_id),
        keyword=keyword.keyword,
        query=aio_data["query"],
        search_timestamp=aio_data["search_timestamp"],
        country=country,
        has_ai_overview=aio_data["has_ai_overview"],
        aio_type=aio_data.get("aio_type"),
        aio_text=aio_data.get("aio_text"),
        brand_in_aio=aio_data["brand_in_aio"],
        brand_aio_position=aio_data.get("brand_aio_position"),
        brand_aio_context=aio_data.get("brand_aio_context"),
        domain_in_aio=aio_data["domain_in_aio"],
        domain_aio_position=aio_data.get("domain_aio_position"),
        aio_sources=aio_data.get("aio_sources", []),
        aio_mentions=aio_data.get("aio_mentions", []),
        competitors_in_aio=[
            CompetitorInAIO(**c) for c in aio_data.get("competitors_in_aio", [])
        ],
        brand_in_organic=aio_data["brand_in_organic"],
        brand_organic_position=aio_data.get("brand_organic_position"),
        competitors_in_organic=aio_data.get("competitors_in_organic", []),
        organic_results=aio_data.get("organic_results", []),
        has_knowledge_graph=aio_data.get("has_knowledge_graph", False)
    )


@router.post("/{project_id}/analyze-bulk", response_model=BulkAIOResponse)
async def analyze_bulk_keywords(
    project_id: UUID,
    request: BulkAIORequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Analyze multiple keywords for AI Overview presence.
    Uses project's country setting for location-specific results.
    Limited to 10 keywords per request to conserve API credits.
    """
    if not settings.SERPER_API_KEY:
        raise HTTPException(status_code=400, detail="SERPER_API_KEY not configured")

    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Use project's country setting
    country = project.country or "in"

    # Get keywords
    keyword_query = select(Keyword).where(
        Keyword.project_id == project_id,
        Keyword.is_active == True
    )
    if request.keyword_ids:
        keyword_query = keyword_query.where(Keyword.id.in_(request.keyword_ids))

    result = await db.execute(keyword_query.limit(10))  # Limit to 10
    keywords = result.scalars().all()

    if not keywords:
        raise HTTPException(status_code=400, detail="No keywords found")

    # Get project with brands and competitors
    from sqlalchemy.orm import selectinload
    result = await db.execute(
        select(Project)
        .options(selectinload(Project.brands), selectinload(Project.competitors))
        .where(Project.id == project_id)
    )
    project = result.scalar_one()

    brand_name = project.brands[0].name if project.brands else project.domain.split(".")[0]
    brand_domain = project.domain
    competitors = [c.name for c in project.competitors]

    # Analyze each keyword
    serper = SerperService(settings.SERPER_API_KEY)
    results = []
    errors = []

    for keyword in keywords:
        try:
            aio_data = await serper.get_ai_overview(
                query=keyword.keyword,
                brand_name=brand_name,
                brand_domain=brand_domain,
                competitors=competitors,
                country=country
            )

            # Save to database
            aio_result = AIOResult(
                keyword_id=keyword.id,
                project_id=project_id,
                country=country,
                has_ai_overview=aio_data["has_ai_overview"],
                aio_type=aio_data.get("aio_type"),
                aio_text=aio_data.get("aio_text"),
                brand_in_aio=aio_data["brand_in_aio"],
                brand_aio_position=aio_data.get("brand_aio_position"),
                brand_aio_context=aio_data.get("brand_aio_context"),
                domain_in_aio=aio_data["domain_in_aio"],
                domain_aio_position=aio_data.get("domain_aio_position"),
                aio_sources=aio_data.get("aio_sources", []),
                aio_mentions=aio_data.get("aio_mentions", []),
                competitors_in_aio=aio_data.get("competitors_in_aio", []),
                brand_in_organic=aio_data["brand_in_organic"],
                brand_organic_position=aio_data.get("brand_organic_position"),
                competitors_in_organic=aio_data.get("competitors_in_organic", []),
                organic_results=aio_data.get("organic_results", []),
                has_knowledge_graph=aio_data.get("has_knowledge_graph", False),
                raw_response=aio_data
            )
            db.add(aio_result)

            results.append(AIOAnalysisResponse(
                keyword_id=str(keyword.id),
                keyword=keyword.keyword,
                query=aio_data["query"],
                search_timestamp=aio_data["search_timestamp"],
                country=country,
                has_ai_overview=aio_data["has_ai_overview"],
                aio_type=aio_data.get("aio_type"),
                aio_text=aio_data.get("aio_text"),
                brand_in_aio=aio_data["brand_in_aio"],
                brand_aio_position=aio_data.get("brand_aio_position"),
                brand_aio_context=aio_data.get("brand_aio_context"),
                domain_in_aio=aio_data["domain_in_aio"],
                domain_aio_position=aio_data.get("domain_aio_position"),
                aio_sources=aio_data.get("aio_sources", []),
                aio_mentions=aio_data.get("aio_mentions", []),
                competitors_in_aio=[
                    CompetitorInAIO(**c) for c in aio_data.get("competitors_in_aio", [])
                ],
                brand_in_organic=aio_data["brand_in_organic"],
                brand_organic_position=aio_data.get("brand_organic_position"),
                competitors_in_organic=aio_data.get("competitors_in_organic", []),
                organic_results=aio_data.get("organic_results", []),
                has_knowledge_graph=aio_data.get("has_knowledge_graph", False)
            ))

        except Exception as e:
            errors.append(f"Error analyzing '{keyword.keyword}': {str(e)}")

    await db.commit()

    return BulkAIOResponse(
        success=len(results) > 0,
        total_keywords=len(keywords),
        analyzed=len(results),
        errors=errors,
        results=results
    )


@router.get("/{project_id}/history/{keyword_id}")
async def get_aio_history(
    project_id: UUID,
    keyword_id: UUID,
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get historical AIO data for a keyword"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Get keyword
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id, Keyword.project_id == project_id)
    )
    keyword = result.scalar_one_or_none()
    if not keyword:
        raise HTTPException(status_code=404, detail="Keyword not found")

    # Get historical data
    result = await db.execute(
        select(AIOResult).where(
            AIOResult.keyword_id == keyword_id,
            AIOResult.created_at >= datetime.utcnow() - timedelta(days=days)
        ).order_by(AIOResult.created_at.desc())
    )
    history = result.scalars().all()

    return {
        "keyword_id": str(keyword_id),
        "keyword": keyword.keyword,
        "days": days,
        "total_records": len(history),
        "history": [
            {
                "id": str(h.id),
                "timestamp": h.created_at.isoformat(),
                "country": h.country,
                "has_ai_overview": h.has_ai_overview,
                "brand_in_aio": h.brand_in_aio,
                "brand_aio_position": h.brand_aio_position,
                "domain_in_aio": h.domain_in_aio,
                "brand_in_organic": h.brand_in_organic,
                "brand_organic_position": h.brand_organic_position,
                "competitors_in_aio": h.competitors_in_aio,
            }
            for h in history
        ]
    }


@router.get("/{project_id}/summary")
async def get_aio_summary(
    project_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get AIO summary for all keywords in a project"""
    # Verify project ownership
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.owner_id == user.id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    # Get latest AIO results for each keyword
    from sqlalchemy import func, distinct

    # Get all keywords
    result = await db.execute(
        select(Keyword).where(Keyword.project_id == project_id, Keyword.is_active == True)
    )
    keywords = result.scalars().all()

    summary = {
        "total_keywords": len(keywords),
        "keywords_with_aio_data": 0,
        "keywords_in_aio": 0,
        "brand_in_aio_count": 0,
        "domain_in_aio_count": 0,
        "brand_in_organic_count": 0,
        "keywords": []
    }

    for keyword in keywords:
        # Get latest AIO result for this keyword
        result = await db.execute(
            select(AIOResult).where(
                AIOResult.keyword_id == keyword.id
            ).order_by(AIOResult.created_at.desc()).limit(1)
        )
        aio = result.scalar_one_or_none()

        keyword_data = {
            "keyword_id": str(keyword.id),
            "keyword": keyword.keyword,
            "has_aio_data": aio is not None,
            "has_ai_overview": aio.has_ai_overview if aio else None,
            "brand_in_aio": aio.brand_in_aio if aio else None,
            "brand_aio_position": aio.brand_aio_position if aio else None,
            "domain_in_aio": aio.domain_in_aio if aio else None,
            "brand_in_organic": aio.brand_in_organic if aio else None,
            "brand_organic_position": aio.brand_organic_position if aio else None,
            "last_checked": aio.created_at.isoformat() if aio else None
        }
        summary["keywords"].append(keyword_data)

        if aio:
            summary["keywords_with_aio_data"] += 1
            if aio.has_ai_overview:
                summary["keywords_in_aio"] += 1
            if aio.brand_in_aio:
                summary["brand_in_aio_count"] += 1
            if aio.domain_in_aio:
                summary["domain_in_aio_count"] += 1
            if aio.brand_in_organic:
                summary["brand_in_organic_count"] += 1

    return summary


def _aio_result_to_response(aio: AIOResult, keyword_text: str) -> AIOAnalysisResponse:
    """Convert AIOResult model to response"""
    return AIOAnalysisResponse(
        keyword_id=str(aio.keyword_id),
        keyword=keyword_text,
        query=keyword_text,
        search_timestamp=aio.created_at.isoformat(),
        country=aio.country,
        has_ai_overview=aio.has_ai_overview,
        aio_type=aio.aio_type,
        aio_text=aio.aio_text,
        brand_in_aio=aio.brand_in_aio,
        brand_aio_position=aio.brand_aio_position,
        brand_aio_context=aio.brand_aio_context,
        domain_in_aio=aio.domain_in_aio,
        domain_aio_position=aio.domain_aio_position,
        aio_sources=aio.aio_sources or [],
        aio_mentions=aio.aio_mentions or [],
        competitors_in_aio=[
            CompetitorInAIO(**c) for c in (aio.competitors_in_aio or [])
        ],
        brand_in_organic=aio.brand_in_organic,
        brand_organic_position=aio.brand_organic_position,
        competitors_in_organic=aio.competitors_in_organic or [],
        organic_results=aio.organic_results or [],
        has_knowledge_graph=aio.has_knowledge_graph
    )
