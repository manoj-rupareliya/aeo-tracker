"""
Citation Extractor Service
Analyzes citations, identifies opportunities, and tracks source authority
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from collections import defaultdict
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from app.models import (
    Project, Citation, CitationSource, LLMRun, LLMResponse,
    LLMProvider, SourceCategory
)
from app.models.visibility import (
    CitationDetail, CitationPurpose, OutreachOpportunity, ContentGap,
    ContentGapType, OutreachStatus, KeywordAnalysisResult
)


class CitationExtractor:
    """
    Handles citation analysis and opportunity detection:
    - Citation frequency tracking
    - Source authority analysis
    - Outreach opportunity identification
    - Content gap detection
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_citations_for_project(
        self,
        project_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Comprehensive citation analysis for a project.

        Returns analysis including:
        - Top cited sources
        - Citation frequency by LLM
        - Own domain citation rate
        - Competitor citation analysis
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        our_domain = project.domain.lower().replace("www.", "")
        competitor_domains = [c.domain.lower().replace("www.", "") for c in project.competitors if c.domain]

        # Get all citations for the project in the period
        citations_query = (
            select(Citation)
            .join(LLMResponse)
            .join(LLMRun)
            .where(
                and_(
                    LLMRun.project_id == project_id,
                    Citation.created_at >= start_date
                )
            )
            .options(selectinload(Citation.source))
        )

        result = await self.db.execute(citations_query)
        citations = result.scalars().all()

        # Analyze citations
        source_counts: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0,
            "positions": [],
            "llms": set(),
            "purposes": [],
            "is_ours": False,
            "is_competitor": False
        })

        llm_citations: Dict[str, int] = defaultdict(int)
        our_citations = 0
        competitor_citations = 0
        total_citations = len(citations)

        for citation in citations:
            if not citation.source:
                continue

            domain = citation.source.domain.lower()
            source_counts[domain]["count"] += 1
            if citation.citation_position:
                source_counts[domain]["positions"].append(citation.citation_position)

            # Get LLM provider from response
            run_result = await self.db.execute(
                select(LLMRun.provider)
                .join(LLMResponse)
                .where(LLMResponse.id == citation.response_id)
            )
            provider = run_result.scalar_one_or_none()
            if provider:
                source_counts[domain]["llms"].add(provider.value)
                llm_citations[provider.value] += 1

            # Check if our domain or competitor
            if domain == our_domain or our_domain in domain:
                source_counts[domain]["is_ours"] = True
                our_citations += 1
            elif any(comp in domain for comp in competitor_domains):
                source_counts[domain]["is_competitor"] = True
                competitor_citations += 1

        # Build top sources list
        top_sources = []
        for domain, data in sorted(source_counts.items(), key=lambda x: x[1]["count"], reverse=True)[:20]:
            avg_position = sum(data["positions"]) / len(data["positions"]) if data["positions"] else None
            top_sources.append({
                "domain": domain,
                "citation_count": data["count"],
                "avg_position": round(avg_position, 2) if avg_position else None,
                "llms_citing": list(data["llms"]),
                "is_own_domain": data["is_ours"],
                "is_competitor": data["is_competitor"],
                "citation_rate": round(data["count"] / total_citations * 100, 2) if total_citations else 0
            })

        return {
            "total_citations": total_citations,
            "unique_sources": len(source_counts),
            "our_domain_citations": our_citations,
            "our_citation_rate": round(our_citations / total_citations * 100, 2) if total_citations else 0,
            "competitor_citations": competitor_citations,
            "competitor_citation_rate": round(competitor_citations / total_citations * 100, 2) if total_citations else 0,
            "citations_by_llm": dict(llm_citations),
            "top_sources": top_sources,
            "analysis_period_days": days
        }

    async def identify_outreach_opportunities(
        self,
        project_id: UUID,
        min_citations: int = 3
    ) -> List[OutreachOpportunity]:
        """
        Identify pages frequently cited by AI that don't mention our brand.

        These are outreach opportunities for:
        - Getting backlinks
        - Getting brand mentions
        - Content partnerships
        """
        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        our_domain = project.domain.lower().replace("www.", "")
        brand_names = [b.name.lower() for b in project.brands]

        # Get frequently cited sources
        result = await self.db.execute(
            select(CitationSource, func.count(Citation.id).label("cite_count"))
            .join(Citation)
            .join(LLMResponse)
            .join(LLMRun)
            .where(LLMRun.project_id == project_id)
            .group_by(CitationSource.id)
            .having(func.count(Citation.id) >= min_citations)
            .order_by(desc("cite_count"))
        )
        frequent_sources = result.all()

        opportunities = []

        for source, cite_count in frequent_sources:
            # Skip our own domain
            if source.domain == our_domain or our_domain in source.domain:
                continue

            # Get citation details
            citations_result = await self.db.execute(
                select(Citation)
                .where(Citation.source_id == source.id)
                .options(selectinload(Citation.response))
                .limit(10)
            )
            sample_citations = citations_result.scalars().all()

            # Get which LLMs cite this source
            llms_citing = set()
            for c in sample_citations:
                if c.response:
                    run_result = await self.db.execute(
                        select(LLMRun.provider)
                        .where(LLMRun.id == c.response.llm_run_id)
                    )
                    provider = run_result.scalar_one_or_none()
                    if provider:
                        llms_citing.add(provider.value)

            # Get relevant keywords
            keywords = set()
            for c in sample_citations:
                if c.response:
                    run_result = await self.db.execute(
                        select(LLMRun)
                        .where(LLMRun.id == c.response.llm_run_id)
                        .options(selectinload(LLMRun.prompt))
                    )
                    run = run_result.scalar_one_or_none()
                    if run and run.prompt and run.prompt.keyword:
                        keywords.add(run.prompt.keyword.keyword)

            # Determine opportunity type and priority
            if cite_count >= 10:
                priority_score = 90
                impact = "high"
            elif cite_count >= 5:
                priority_score = 70
                impact = "medium"
            else:
                priority_score = 50
                impact = "low"

            # Create opportunity
            opportunity = OutreachOpportunity(
                project_id=project_id,
                source_id=source.id,
                page_url=f"https://{source.domain}",
                page_title=source.site_name,
                page_domain=source.domain,
                opportunity_type="backlink",
                opportunity_reason=f"Frequently cited by AI ({cite_count} times). Getting a mention here could improve AI visibility.",
                citation_count=cite_count,
                citation_frequency=round(cite_count / 100, 4),  # Approximation
                llms_citing=list(llms_citing),
                relevant_keywords=list(keywords)[:10],
                mentions_us=False,
                priority_score=priority_score,
                impact_estimate=impact,
                effort_estimate="medium",
                status=OutreachStatus.NEW
            )

            self.db.add(opportunity)
            opportunities.append(opportunity)

        await self.db.commit()
        return opportunities

    async def detect_content_gaps(
        self,
        project_id: UUID
    ) -> List[ContentGap]:
        """
        Identify content gaps based on what competitors are cited for
        and what types of content AI prefers.
        """
        project = await self._get_project(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        our_domain = project.domain.lower().replace("www.", "")
        competitor_domains = {c.domain.lower().replace("www.", ""): c for c in project.competitors if c.domain}

        # Get analysis results where competitors are cited but we're not
        result = await self.db.execute(
            select(KeywordAnalysisResult)
            .join(LLMRun)
            .where(
                and_(
                    LLMRun.project_id == project_id,
                    KeywordAnalysisResult.our_domain_cited == False,
                    KeywordAnalysisResult.total_citations > 0
                )
            )
            .options(selectinload(KeywordAnalysisResult.keyword))
        )
        uncited_results = result.scalars().all()

        # Group by keyword/topic
        keyword_gaps: Dict[str, Dict] = defaultdict(lambda: {
            "count": 0,
            "competitor_sources": [],
            "other_sources": [],
            "content_types": set()
        })

        for ar in uncited_results:
            keyword_text = ar.keyword.keyword if ar.keyword else "Unknown"
            keyword_gaps[keyword_text]["count"] += 1

            for citation in (ar.citations_summary or []):
                domain = citation.get("domain", "")
                purpose = citation.get("purpose", "authority")

                if domain in competitor_domains:
                    keyword_gaps[keyword_text]["competitor_sources"].append({
                        "domain": domain,
                        "competitor": competitor_domains[domain].name,
                        "url": citation.get("url"),
                        "purpose": purpose
                    })
                else:
                    keyword_gaps[keyword_text]["other_sources"].append({
                        "domain": domain,
                        "url": citation.get("url"),
                        "purpose": purpose
                    })

                keyword_gaps[keyword_text]["content_types"].add(purpose)

        # Create content gap records
        gaps = []

        for keyword, data in keyword_gaps.items():
            if data["count"] < 2:  # Skip if too few occurrences
                continue

            # Determine gap type
            if data["competitor_sources"]:
                gap_type = ContentGapType.COMPETITOR_ONLY
                description = f"Competitors are being cited for '{keyword}' queries but we are not."
            elif data["other_sources"]:
                gap_type = ContentGapType.MISSING_PAGE
                description = f"AI is citing other sources for '{keyword}' queries. We may need content on this topic."
            else:
                gap_type = ContentGapType.THIN_CONTENT
                description = f"We're not being cited for '{keyword}' queries. Content may need improvement."

            # Determine content type needed
            content_types = list(data["content_types"])
            content_type_needed = content_types[0] if content_types else "article"

            # Calculate opportunity score
            opportunity_score = min(100, data["count"] * 10 + len(data["competitor_sources"]) * 20)

            # Determine priority
            if opportunity_score >= 80:
                priority = "critical"
            elif opportunity_score >= 60:
                priority = "high"
            elif opportunity_score >= 40:
                priority = "medium"
            else:
                priority = "low"

            # Create gap record
            gap = ContentGap(
                project_id=project_id,
                gap_type=gap_type,
                gap_description=description,
                related_keywords=[keyword],
                content_type_needed=content_type_needed,
                content_format="article",
                competitor_examples=data["competitor_sources"][:5],
                cited_sources=data["other_sources"][:5],
                opportunity_score=opportunity_score,
                recommended_action=self._get_gap_action(gap_type, keyword, content_type_needed),
                action_items=self._get_gap_action_items(gap_type, keyword),
                priority=priority,
                effort_required="medium"
            )

            self.db.add(gap)
            gaps.append(gap)

        await self.db.commit()
        return gaps

    async def get_citation_summary(
        self,
        project_id: UUID,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get citation summary for dashboard display."""
        analysis = await self.analyze_citations_for_project(project_id, days)

        # Get outreach opportunities count
        result = await self.db.execute(
            select(func.count(OutreachOpportunity.id))
            .where(
                and_(
                    OutreachOpportunity.project_id == project_id,
                    OutreachOpportunity.status == OutreachStatus.NEW
                )
            )
        )
        new_opportunities = result.scalar() or 0

        # Get content gaps count
        result = await self.db.execute(
            select(func.count(ContentGap.id))
            .where(
                and_(
                    ContentGap.project_id == project_id,
                    ContentGap.is_addressed == False
                )
            )
        )
        open_gaps = result.scalar() or 0

        return {
            **analysis,
            "new_outreach_opportunities": new_opportunities,
            "open_content_gaps": open_gaps,
            "action_items": new_opportunities + open_gaps
        }

    async def get_source_authority_ranking(
        self,
        project_id: UUID,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get ranked list of sources by their authority in AI responses."""
        result = await self.db.execute(
            select(
                CitationSource,
                func.count(Citation.id).label("cite_count"),
                func.avg(Citation.citation_position).label("avg_position")
            )
            .join(Citation)
            .join(LLMResponse)
            .join(LLMRun)
            .where(LLMRun.project_id == project_id)
            .group_by(CitationSource.id)
            .order_by(desc("cite_count"))
            .limit(limit)
        )

        sources = result.all()

        ranking = []
        for i, (source, count, avg_pos) in enumerate(sources):
            # Calculate authority score (higher count + lower position = higher authority)
            authority = count * 10
            if avg_pos:
                authority += (10 - min(avg_pos, 10)) * 5

            ranking.append({
                "rank": i + 1,
                "domain": source.domain,
                "site_name": source.site_name,
                "category": source.category.value if source.category else "unknown",
                "citation_count": count,
                "avg_position": round(avg_pos, 2) if avg_pos else None,
                "authority_score": round(authority, 2),
                "domain_authority": source.domain_authority
            })

        return ranking

    def _get_gap_action(self, gap_type: ContentGapType, keyword: str, content_type: str) -> str:
        """Generate recommended action for a content gap."""
        if gap_type == ContentGapType.COMPETITOR_ONLY:
            return f"Create {content_type} content about '{keyword}' to compete with content being cited from competitors."
        elif gap_type == ContentGapType.MISSING_PAGE:
            return f"Create a new {content_type} page targeting '{keyword}' to be considered as a citation source."
        elif gap_type == ContentGapType.THIN_CONTENT:
            return f"Expand existing content about '{keyword}' with more depth, data, and examples."
        elif gap_type == ContentGapType.NO_BACKLINK:
            return f"Reach out to sources being cited for '{keyword}' to request backlinks or mentions."
        else:
            return f"Review content strategy for '{keyword}' queries."

    def _get_gap_action_items(self, gap_type: ContentGapType, keyword: str) -> List[str]:
        """Generate action items for a content gap."""
        if gap_type == ContentGapType.COMPETITOR_ONLY:
            return [
                f"Analyze competitor content ranking for '{keyword}'",
                "Identify unique angles or additional value to provide",
                "Create comprehensive content with original data/insights",
                "Build backlinks to the new content"
            ]
        elif gap_type == ContentGapType.MISSING_PAGE:
            return [
                f"Research user intent for '{keyword}' queries",
                "Outline content structure based on cited sources",
                "Create authoritative, well-researched content",
                "Optimize for AI discoverability"
            ]
        elif gap_type == ContentGapType.THIN_CONTENT:
            return [
                "Audit existing content on this topic",
                "Add more depth, examples, and data",
                "Update with latest information",
                "Improve internal linking"
            ]
        else:
            return [
                "Review current content",
                "Identify improvement opportunities",
                "Take action based on analysis"
            ]

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
