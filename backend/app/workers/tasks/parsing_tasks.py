"""
Response Parsing Tasks
Extract mentions, citations, and sentiment from LLM responses
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from celery import shared_task
from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app
from app.utils.database import get_sync_db
from app.models import (
    LLMRun, LLMResponse, LLMRunStatus, Brand, Competitor,
    BrandMention, Citation, CitationSource, SentimentPolarity, SourceCategory
)
from app.adapters.parsing import BrandMatcher, BrandConfig, CitationExtractor, SentimentAnalyzer

logger = get_task_logger(__name__)


def run_async(coro):
    """Run async function in sync context"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="app.workers.tasks.parsing_tasks.parse_llm_response",
    max_retries=2,
    default_retry_delay=10,
)
def parse_llm_response(self, llm_run_id: str) -> Dict:
    """
    Parse an LLM response to extract mentions, citations, and sentiment.

    Args:
        llm_run_id: UUID of the LLMRun to parse

    Returns:
        Dict with parsing results
    """
    db = get_sync_db()

    try:
        # Get LLM run and response
        llm_run = db.query(LLMRun).filter(LLMRun.id == llm_run_id).first()
        if not llm_run:
            return {"error": "LLM run not found"}

        llm_response = db.query(LLMResponse).filter(
            LLMResponse.llm_run_id == llm_run_id
        ).first()
        if not llm_response:
            return {"error": "LLM response not found"}

        # Get brands and competitors for matching
        brands = db.query(Brand).filter(Brand.project_id == llm_run.project_id).all()
        competitors = db.query(Competitor).filter(
            Competitor.project_id == llm_run.project_id
        ).all()

        # Configure brand matcher
        own_brands = [
            BrandConfig(
                id=str(b.id),
                name=b.name,
                aliases=b.aliases or [],
                is_own_brand=True
            )
            for b in brands
        ]
        competitor_brands = [
            BrandConfig(
                id=str(c.id),
                name=c.name,
                aliases=c.aliases or [],
                is_own_brand=False
            )
            for c in competitors
        ]

        matcher = BrandMatcher(own_brands, competitor_brands)
        citation_extractor = CitationExtractor(validate_urls=False)
        sentiment_analyzer = SentimentAnalyzer()

        # Parse response text
        response_text = llm_response.raw_response

        # Extract brand mentions
        mentions = matcher.find_mentions(response_text)
        logger.info(f"Found {len(mentions)} brand mentions in run {llm_run_id}")

        # Save mentions
        for mention in mentions:
            # Analyze sentiment for this mention
            sentiment_result = sentiment_analyzer.analyze_mention_context(
                response_text,
                mention.character_offset,
                mention.character_offset + len(mention.mentioned_text)
            )

            brand_mention = BrandMention(
                response_id=llm_response.id,
                mentioned_text=mention.mentioned_text,
                normalized_name=mention.normalized_name,
                is_own_brand=mention.is_own_brand,
                brand_id=mention.brand_id,
                competitor_id=mention.competitor_id,
                mention_position=mention.position,
                character_offset=mention.character_offset,
                context_snippet=mention.context_snippet,
                match_type=mention.match_type,
                match_confidence=mention.match_confidence,
                sentiment=sentiment_result.polarity,
                sentiment_score=sentiment_result.score,
            )
            db.add(brand_mention)

        # Extract citations
        # Check if this is a Perplexity response with native citations
        metadata = llm_response.response_metadata or {}
        perplexity_citations = metadata.get("citations", [])

        if perplexity_citations:
            citations = citation_extractor.extract_perplexity_citations(
                response_text,
                perplexity_citations
            )
        else:
            citations = citation_extractor.extract_citations(response_text)

        logger.info(f"Found {len(citations)} citations in run {llm_run_id}")

        # Save citations
        for citation in citations:
            # Get or create citation source
            source = db.query(CitationSource).filter(
                CitationSource.domain == citation.domain
            ).first()

            if not source and citation.domain:
                source = CitationSource(
                    domain=citation.domain,
                    category=_categorize_domain(citation.domain),
                    total_citations=0,
                )
                db.add(source)
                db.flush()

            if source:
                source.total_citations += 1
                source.last_cited_at = datetime.utcnow()

            citation_record = Citation(
                response_id=llm_response.id,
                source_id=source.id if source else None,
                cited_url=citation.url,
                anchor_text=citation.anchor_text,
                context_snippet=citation.context_snippet,
                citation_position=citation.position,
                is_valid_url=citation.is_valid_url,
                is_accessible=citation.is_accessible,
                http_status_code=citation.http_status_code,
                is_hallucinated=citation.is_hallucinated,
            )
            db.add(citation_record)

        # Update parsed response data
        llm_response.parsed_response = {
            "mentions": [
                {
                    "text": m.mentioned_text,
                    "name": m.normalized_name,
                    "position": m.position,
                    "is_own_brand": m.is_own_brand,
                    "match_type": m.match_type,
                }
                for m in mentions
            ],
            "citations": [
                {
                    "url": c.url,
                    "domain": c.domain,
                    "position": c.position,
                    "is_hallucinated": c.is_hallucinated,
                }
                for c in citations
            ],
            "parsing_completed_at": datetime.utcnow().isoformat(),
        }

        # Update LLM run status
        llm_run.status = LLMRunStatus.SCORING
        db.commit()

        logger.info(f"Parsing completed for run {llm_run_id}")

        # Trigger scoring task
        from app.workers.tasks.scoring_tasks import calculate_score
        calculate_score.delay(llm_run_id)

        return {
            "success": True,
            "run_id": llm_run_id,
            "mentions_found": len(mentions),
            "citations_found": len(citations),
        }

    except Exception as e:
        logger.exception(f"Parsing error for run {llm_run_id}: {e}")
        db.rollback()
        raise self.retry(exc=e)
    finally:
        db.close()


def _categorize_domain(domain: str) -> SourceCategory:
    """Categorize a domain based on patterns"""
    domain_lower = domain.lower()

    # News sites
    news_patterns = [
        "news", "times", "post", "herald", "journal", "tribune",
        "reuters", "bloomberg", "cnn", "bbc", "forbes", "techcrunch",
        "venturebeat", "wired", "theverge", "arstechnica"
    ]
    if any(p in domain_lower for p in news_patterns):
        return SourceCategory.NEWS

    # Official documentation
    doc_patterns = ["docs.", "documentation.", "developer.", "api.", "dev."]
    if any(p in domain_lower for p in doc_patterns):
        return SourceCategory.OFFICIAL_DOCS

    # Review sites
    review_patterns = [
        "g2", "capterra", "trustpilot", "gartner", "review",
        "rating", "comparison", "versus"
    ]
    if any(p in domain_lower for p in review_patterns):
        return SourceCategory.REVIEW_SITE

    # Blogs
    blog_patterns = ["blog", "medium.com", "substack", "wordpress"]
    if any(p in domain_lower for p in blog_patterns):
        return SourceCategory.BLOG

    # Forums
    forum_patterns = [
        "reddit", "stackoverflow", "quora", "forum",
        "community", "discuss", "hackernews"
    ]
    if any(p in domain_lower for p in forum_patterns):
        return SourceCategory.FORUM

    # Social media
    social_patterns = ["twitter", "linkedin", "facebook", "youtube", "x.com"]
    if any(p in domain_lower for p in social_patterns):
        return SourceCategory.SOCIAL_MEDIA

    # Academic
    academic_patterns = [".edu", "arxiv", "scholar", "research", "academic", "ieee"]
    if any(p in domain_lower for p in academic_patterns):
        return SourceCategory.ACADEMIC

    # E-commerce
    ecommerce_patterns = ["amazon", "ebay", "shopify", "shop", "store", "buy"]
    if any(p in domain_lower for p in ecommerce_patterns):
        return SourceCategory.ECOMMERCE

    return SourceCategory.UNKNOWN


@celery_app.task(
    name="app.workers.tasks.parsing_tasks.parse_batch_responses",
)
def parse_batch_responses(llm_run_ids: List[str]) -> Dict:
    """
    Parse multiple LLM responses.

    Args:
        llm_run_ids: List of LLMRun IDs to parse

    Returns:
        Dict with batch parsing results
    """
    results = []
    for run_id in llm_run_ids:
        try:
            result = parse_llm_response(run_id)
            results.append(result)
        except Exception as e:
            results.append({"error": str(e), "run_id": run_id})

    successful = sum(1 for r in results if r.get("success"))
    return {
        "total": len(llm_run_ids),
        "successful": successful,
        "failed": len(llm_run_ids) - successful,
        "results": results,
    }
