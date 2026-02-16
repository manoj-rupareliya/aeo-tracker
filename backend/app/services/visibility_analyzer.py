"""
Visibility Analyzer Service
Extracts mentions, citations, positions, and calculates visibility metrics from LLM responses
"""

import re
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from uuid import UUID
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import (
    Project, Brand, Competitor, Keyword, LLMRun, LLMResponse,
    BrandMention, Citation, CitationSource, VisibilityScore,
    LLMProvider, SentimentPolarity, PromptType
)
from app.models.visibility import (
    MentionType, CitationPurpose, KeywordAnalysisResult,
    ExtractedEntity, FanOutQuery, ShoppingRecommendation, CitationDetail
)


class VisibilityAnalyzer:
    """
    Analyzes LLM responses to extract:
    - Brand mentions with positions
    - Citations with source analysis
    - Fan-out queries (web searches)
    - Shopping recommendations
    - Sentiment analysis
    - Visibility scoring
    """

    # URL patterns
    URL_PATTERN = re.compile(
        r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s\]\)]*'
    )

    # Citation patterns (markdown links, references)
    CITATION_PATTERN = re.compile(
        r'\[([^\]]+)\]\(([^)]+)\)|'  # Markdown links
        r'Source:\s*([^\n]+)|'       # "Source: url" format
        r'Reference:\s*([^\n]+)|'    # "Reference: url" format
        r'(?:According to|per|via)\s+([^\n,]+)'  # Attribution patterns
    )

    # Shopping recommendation patterns
    SHOPPING_PATTERNS = [
        r'(?:best|top|recommended)\s+(?:choice|pick|option)[:\s]+([^\n]+)',
        r'(?:we recommend|i recommend|our pick)[:\s]+([^\n]+)',
        r'(?:budget pick|premium pick|best overall)[:\s]+([^\n]+)',
        r'(?:\d+\.\s*)([^:\n]+)[\s-]+\$[\d,]+',  # Numbered list with price
    ]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_response(
        self,
        llm_run_id: UUID,
        response_text: str,
        project_id: UUID,
        keyword_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of an LLM response.

        Returns:
            Dict containing all extracted data and calculated scores
        """
        # Get project data for context
        project = await self._get_project_with_brands(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Get LLM run info
        run = await self.db.get(LLMRun, llm_run_id)
        if not run:
            raise ValueError(f"LLM Run {llm_run_id} not found")

        # Extract all data
        brand_names = [b.name for b in project.brands] + sum([b.aliases for b in project.brands], [])
        competitor_names = [c.name for c in project.competitors] + sum([c.aliases for c in project.competitors], [])

        # Also include project domain as a brand to check (without TLD for matching)
        # e.g., for factohr.com, we also check for "factohr"
        domain_brand = project.domain.replace("www.", "").split(".")[0]  # e.g., "factohr" from "factohr.com"
        if domain_brand and domain_brand not in [b.lower() for b in brand_names]:
            brand_names.append(domain_brand)
            # Also add the full domain without TLD parts
            full_domain_name = project.domain.replace("www.", "").rsplit(".", 1)[0]  # e.g., "factohr" from "factohr.com"
            if full_domain_name != domain_brand:
                brand_names.append(full_domain_name)

        # 1. Extract brand mentions
        mentions = self._extract_brand_mentions(
            response_text,
            brand_names,
            competitor_names,
            project.brands,
            project.competitors,
            project.domain
        )

        # 2. Extract citations
        citations = self._extract_citations(response_text, project.domain)

        # 3. Extract fan-out queries (if present in response)
        fan_out_queries = self._extract_fan_out_queries(response_text)

        # 4. Extract shopping recommendations
        shopping_recs = self._extract_shopping_recommendations(
            response_text, brand_names, competitor_names
        )

        # 5. Analyze sentiment
        sentiment_result = self._analyze_sentiment(response_text, brand_names)

        # 6. Calculate visibility scores
        scores = self._calculate_visibility_scores(
            mentions, citations, sentiment_result,
            project.domain, len(response_text)
        )

        # 7. Create analysis result
        analysis_result = {
            "llm_run_id": str(llm_run_id),
            "project_id": str(project_id),
            "keyword_id": str(keyword_id) if keyword_id else None,
            "provider": run.provider.value,
            "model_name": run.model_name,

            # Mentions
            "brand_mentioned": any(m["is_own_brand"] for m in mentions),
            "brand_position": next(
                (m["position"] for m in mentions if m["is_own_brand"]), None
            ),
            "mentions": mentions,
            "total_brands_mentioned": len(mentions),

            # Citations
            "citations": citations,
            "total_citations": len(citations),
            "our_domain_cited": any(c["is_own_domain"] for c in citations),
            "our_domain_citation_position": next(
                (c["position"] for c in citations if c["is_own_domain"]), None
            ),

            # Fan-out queries
            "fan_out_queries": fan_out_queries,
            "fan_out_queries_count": len(fan_out_queries),

            # Shopping
            "shopping_recommendations": shopping_recs,
            "has_shopping_recommendations": len(shopping_recs) > 0,
            "our_product_recommended": any(r["is_own_brand"] for r in shopping_recs),
            "product_recommendation_position": next(
                (r["position"] for r in shopping_recs if r["is_own_brand"]), None
            ),

            # Sentiment
            "overall_sentiment": sentiment_result["overall"],
            "brand_sentiment": sentiment_result["brand_sentiment"],
            "sentiment_score": sentiment_result["score"],

            # Visibility Scores
            "mention_score": scores["mention_score"],
            "position_score": scores["position_score"],
            "citation_score": scores["citation_score"],
            "sentiment_score_component": scores["sentiment_score"],
            "total_visibility_score": scores["total_score"],

            # Metadata
            "response_length": len(response_text),
            "response_format": self._detect_response_format(response_text),
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "analysis_version": "1.0.0",

            # AIO (AI Overview) tracking
            # For LLM responses, the response IS the AI overview
            "has_aio": True,  # Response exists, so there is an AIO
            "brand_in_aio": any(m["is_own_brand"] for m in mentions),  # Brand found in AIO
            "domain_in_aio": any(c["is_own_domain"] for c in citations),  # Domain cited in AIO
        }

        return analysis_result

    async def save_analysis_results(
        self,
        llm_run_id: UUID,
        response_id: UUID,
        analysis: Dict[str, Any]
    ) -> KeywordAnalysisResult:
        """Save analysis results to database"""

        # Create KeywordAnalysisResult
        result = KeywordAnalysisResult(
            llm_run_id=llm_run_id,
            keyword_id=UUID(analysis["keyword_id"]) if analysis.get("keyword_id") else None,
            response_id=response_id,
            provider=LLMProvider(analysis["provider"]),
            model_name=analysis.get("model_name"),

            brand_mentioned=analysis["brand_mentioned"],
            brand_position=analysis.get("brand_position"),
            mention_type=MentionType.DIRECT if analysis["brand_mentioned"] else None,
            mention_context=analysis["mentions"][0].get("context") if analysis["brand_mentioned"] else None,

            competitors_mentioned=[
                {"name": m["name"], "position": m["position"], "context": m.get("context")}
                for m in analysis["mentions"] if not m["is_own_brand"]
            ],
            total_brands_mentioned=analysis["total_brands_mentioned"],

            total_citations=analysis["total_citations"],
            our_domain_cited=analysis["our_domain_cited"],
            our_domain_citation_position=analysis.get("our_domain_citation_position"),
            competitor_domains_cited=[
                c["domain"] for c in analysis["citations"]
                if c.get("is_competitor_domain")
            ],
            citations_summary=analysis["citations"],

            fan_out_queries_count=analysis["fan_out_queries_count"],
            fan_out_queries=analysis["fan_out_queries"],

            has_shopping_recommendations=analysis["has_shopping_recommendations"],
            our_product_recommended=analysis["our_product_recommended"],
            product_recommendation_position=analysis.get("product_recommendation_position"),

            overall_sentiment=SentimentPolarity(analysis["overall_sentiment"]),
            brand_sentiment=SentimentPolarity(analysis["brand_sentiment"]) if analysis.get("brand_sentiment") else None,
            sentiment_score=analysis["sentiment_score"],

            mention_score=analysis["mention_score"],
            position_score=analysis["position_score"],
            citation_score=analysis["citation_score"],
            sentiment_score_component=analysis["sentiment_score_component"],
            total_visibility_score=analysis["total_visibility_score"],

            response_length=analysis["response_length"],
            response_format=analysis["response_format"],

            # AIO tracking
            has_aio=analysis.get("has_aio", True),
            brand_in_aio=analysis.get("brand_in_aio", False),
            domain_in_aio=analysis.get("domain_in_aio", False),

            analysis_version=analysis["analysis_version"],
        )

        self.db.add(result)

        # Save brand mentions
        for mention in analysis["mentions"]:
            brand_mention = BrandMention(
                response_id=response_id,
                mentioned_text=mention["matched_text"],
                normalized_name=mention["name"],
                is_own_brand=mention["is_own_brand"],
                brand_id=mention.get("brand_id"),
                competitor_id=mention.get("competitor_id"),
                mention_position=mention["position"],
                character_offset=mention.get("offset"),
                context_snippet=mention.get("context"),
                match_type=mention.get("match_type", "exact"),
                match_confidence=mention.get("confidence", 1.0),
                sentiment=SentimentPolarity(mention.get("sentiment", "neutral")),
                sentiment_score=mention.get("sentiment_score", 0.0),
            )
            self.db.add(brand_mention)

        # Save citations
        for citation_data in analysis["citations"]:
            # Get or create citation source
            source = await self._get_or_create_citation_source(citation_data["domain"])

            citation = Citation(
                response_id=response_id,
                source_id=source.id if source else None,
                cited_url=citation_data["url"],
                anchor_text=citation_data.get("anchor_text"),
                context_snippet=citation_data.get("context"),
                citation_position=citation_data["position"],
                is_valid_url=True,
            )
            self.db.add(citation)
            # Flush to get the citation.id before creating CitationDetail
            await self.db.flush()

            # Save citation detail
            citation_detail = CitationDetail(
                citation_id=citation.id,
                citation_purpose=CitationPurpose(citation_data.get("purpose", "authority")),
                context_before=citation_data.get("context_before"),
                context_after=citation_data.get("context_after"),
                full_sentence=citation_data.get("sentence"),
                brands_in_context=citation_data.get("brands_in_context", []),
                mentions_our_brand=citation_data.get("is_own_domain", False),
            )
            self.db.add(citation_detail)

        # Save fan-out queries
        for i, query in enumerate(analysis["fan_out_queries"]):
            fan_out = FanOutQuery(
                llm_run_id=llm_run_id,
                response_id=response_id,
                query_text=query["query"],
                query_hash=hashlib.sha256(query["query"].encode()).hexdigest(),
                query_position=i + 1,
                extracted_keywords=query.get("keywords", []),
            )
            self.db.add(fan_out)

        # Save shopping recommendations
        for rec in analysis["shopping_recommendations"]:
            shopping = ShoppingRecommendation(
                response_id=response_id,
                product_name=rec["product_name"],
                brand_name=rec.get("brand_name"),
                is_own_brand=rec.get("is_own_brand", False),
                recommendation_position=rec["position"],
                recommendation_type=rec.get("type"),
                context_snippet=rec.get("context"),
                price_mentioned=rec.get("price"),
                sentiment=SentimentPolarity(rec.get("sentiment", "positive")),
                recommendation_strength=rec.get("strength", 0.8),
            )
            self.db.add(shopping)

        # Create VisibilityScore record for dashboard queries
        visibility_score = VisibilityScore(
            project_id=UUID(analysis["project_id"]),
            llm_run_id=llm_run_id,
            keyword_id=UUID(analysis["keyword_id"]) if analysis.get("keyword_id") else None,
            provider=LLMProvider(analysis["provider"]),
            mention_score=analysis["mention_score"],
            position_score=analysis["position_score"],
            citation_score=analysis["citation_score"],
            sentiment_score=analysis["sentiment_score_component"],
            competitor_delta=0,  # Would need competitor comparison logic
            total_score=analysis["total_visibility_score"],
            llm_weight=1.0,  # Could be set from LLM_MARKET_WEIGHTS
            weighted_score=analysis["total_visibility_score"],  # Same as total for now
            score_explanation={
                "brand_mentioned": analysis["brand_mentioned"],
                "brand_position": analysis.get("brand_position"),
                "total_brands": analysis["total_brands_mentioned"],
                "citations_count": analysis["total_citations"],
                "our_domain_cited": analysis["our_domain_cited"],
                "sentiment": analysis["overall_sentiment"],
            },
            score_date=datetime.utcnow(),
        )
        self.db.add(visibility_score)

        await self.db.commit()
        return result

    async def _get_project_with_brands(self, project_id: UUID) -> Optional[Project]:
        """Get project with brands and competitors loaded"""
        result = await self.db.execute(
            select(Project)
            .options(
                selectinload(Project.brands),
                selectinload(Project.competitors)
            )
            .where(Project.id == project_id)
        )
        return result.scalar_one_or_none()

    # Common company/product patterns to extract
    ENTITY_PATTERNS = [
        # Numbered list items with brands (e.g., "1. Zoho People", "2. BambooHR")
        r'(?:^|\n)\s*\d+\.\s*\*?\*?([A-Z][A-Za-z0-9\s\-\.]+?)(?:\*?\*?)\s*[\-–:]\s',
        # Bold/emphasized brands (e.g., "**Zoho People**", "*BambooHR*")
        r'\*\*([A-Z][A-Za-z0-9\s\-\.]{2,30})\*\*',
        r'\*([A-Z][A-Za-z0-9\s\-\.]{2,30})\*',
        # Brands in headers (e.g., "### Zoho People")
        r'#{1,3}\s+([A-Z][A-Za-z0-9\s\-\.]{2,30})',
        # "Brand is..." or "Brand offers..." patterns
        r'\b([A-Z][A-Za-z0-9]{2,20}(?:\s[A-Z][A-Za-z0-9]+)?)\s+(?:is|offers|provides|has|features|includes)',
        # "such as Brand" or "like Brand"
        r'(?:such as|like|including|e\.g\.|for example)\s+([A-Z][A-Za-z0-9\s\-]+?)(?:[,\.]|\s+and)',
    ]

    def _extract_brand_mentions(
        self,
        text: str,
        brand_names: List[str],
        competitor_names: List[str],
        brands: List,
        competitors: List,
        project_domain: str = None
    ) -> List[Dict]:
        """Extract all brand mentions with positions and context"""
        mentions = []
        seen_names = set()  # Track unique names

        # Find all defined brands mentioned
        all_names = [(name, True, b.id) for b in brands for name in [b.name] + (b.aliases or [])]
        all_names += [(name, False, c.id) for c in competitors for name in [c.name] + (c.aliases or [])]

        # Also add project domain as a brand to detect
        if project_domain:
            domain_clean = project_domain.replace("www.", "")
            domain_name = domain_clean.split(".")[0]  # e.g., "factohr" from "factohr.com"
            if domain_name and len(domain_name) >= 3:
                # Add domain name as own brand (with None as entity_id since it's derived)
                all_names.append((domain_name, True, None))
                # Also check full domain
                all_names.append((domain_clean, True, None))

        for name, is_own, entity_id in all_names:
            pattern = re.compile(rf'\b{re.escape(name)}\b', re.IGNORECASE)
            for match in pattern.finditer(text):
                start = match.start()

                # Get context (50 chars before and after)
                context_start = max(0, start - 50)
                context_end = min(len(text), start + len(name) + 50)
                context = text[context_start:context_end]

                name_lower = name.lower()
                if name_lower not in seen_names:
                    seen_names.add(name_lower)
                    mentions.append({
                        "name": name,
                        "matched_text": match.group(),
                        "is_own_brand": is_own,
                        "brand_id": str(entity_id) if is_own else None,
                        "competitor_id": str(entity_id) if not is_own else None,
                        "position": 0,  # Will be set later
                        "offset": start,
                        "context": context,
                        "match_type": "exact",
                        "confidence": 1.0,
                        "sentiment": "neutral",
                        "sentiment_score": 0.0
                    })

        # Also extract unknown entities from the response
        unknown_entities = self._extract_unknown_entities(text, seen_names)
        for entity in unknown_entities:
            if entity["name"].lower() not in seen_names:
                seen_names.add(entity["name"].lower())
                mentions.append(entity)

        # Sort by position in text (offset)
        mentions.sort(key=lambda x: x["offset"])

        # Reassign positions based on order of appearance
        for i, mention in enumerate(mentions):
            mention["position"] = i + 1

        return mentions

    def _extract_unknown_entities(self, text: str, seen_names: set) -> List[Dict]:
        """Extract potential brand/company names that weren't predefined"""
        entities = []
        seen_lower = {n.lower() for n in seen_names}

        # Common words to exclude
        exclude_words = {
            'the', 'this', 'that', 'these', 'those', 'here', 'there', 'what', 'which',
            'when', 'where', 'how', 'why', 'can', 'will', 'would', 'should', 'could',
            'have', 'has', 'had', 'been', 'being', 'best', 'top', 'good', 'great',
            'software', 'system', 'platform', 'solution', 'tool', 'app', 'application',
            'service', 'company', 'business', 'enterprise', 'small', 'medium', 'large',
            'features', 'pricing', 'support', 'integration', 'management', 'human',
            'resources', 'employee', 'payroll', 'benefits', 'time', 'tracking',
            'recruitment', 'onboarding', 'performance', 'india', 'indian', 'global',
            'free', 'paid', 'premium', 'basic', 'advanced', 'pro', 'plus', 'standard',
            'some', 'many', 'most', 'all', 'any', 'each', 'every', 'both', 'few',
            'key', 'main', 'core', 'primary', 'secondary', 'additional', 'other',
            'however', 'therefore', 'moreover', 'furthermore', 'conclusion', 'summary',
        }

        for pattern in self.ENTITY_PATTERNS:
            for match in re.finditer(pattern, text, re.MULTILINE):
                name = match.group(1).strip()

                # Clean up the name
                name = re.sub(r'\s+', ' ', name)  # Normalize whitespace
                name = name.strip('*#:- ')

                # Skip if too short, too long, or common word
                if len(name) < 3 or len(name) > 40:
                    continue
                if name.lower() in exclude_words:
                    continue
                if name.lower() in seen_lower:
                    continue
                # Skip if mostly lowercase (likely not a brand)
                if name[0].islower():
                    continue
                # Skip if contains certain patterns
                if re.search(r'^\d|^[^A-Za-z]|www\.|\.com|http', name):
                    continue

                start = match.start(1) if match.lastindex else match.start()
                context_start = max(0, start - 50)
                context_end = min(len(text), start + len(name) + 50)
                context = text[context_start:context_end]

                seen_lower.add(name.lower())
                entities.append({
                    "name": name,
                    "matched_text": name,
                    "is_own_brand": False,
                    "brand_id": None,
                    "competitor_id": None,
                    "position": 0,
                    "offset": start,
                    "context": context,
                    "match_type": "extracted",
                    "confidence": 0.8,
                    "sentiment": "neutral",
                    "sentiment_score": 0.0
                })

        return entities

    def _extract_citations(self, text: str, our_domain: str) -> List[Dict]:
        """Extract all citations/URLs with context and classification"""
        citations = []
        our_domain_clean = our_domain.lower().replace("www.", "")

        # Find all URLs
        for i, match in enumerate(self.URL_PATTERN.finditer(text)):
            url = match.group()
            start = match.start()

            try:
                parsed = urlparse(url)
                domain = parsed.netloc.lower().replace("www.", "")
            except:
                domain = url

            # Get context
            context_start = max(0, start - 100)
            context_end = min(len(text), start + len(url) + 100)
            context = text[context_start:context_end]

            # Find anchor text (if markdown link)
            anchor_text = None
            anchor_match = re.search(rf'\[([^\]]+)\]\({re.escape(url)}\)', text)
            if anchor_match:
                anchor_text = anchor_match.group(1)

            # Determine purpose
            purpose = self._classify_citation_purpose(url, domain, context)

            citations.append({
                "url": url,
                "domain": domain,
                "position": i + 1,
                "anchor_text": anchor_text,
                "context": context,
                "is_own_domain": domain == our_domain_clean or our_domain_clean in domain,
                "is_competitor_domain": False,  # Would need competitor domain list
                "purpose": purpose,
                "context_before": text[context_start:start],
                "context_after": text[start + len(url):context_end],
            })

        return citations

    def _classify_citation_purpose(self, url: str, domain: str, context: str) -> str:
        """Classify the purpose of a citation"""
        url_lower = url.lower()
        context_lower = context.lower()

        if any(x in url_lower for x in ['/docs', '/documentation', '/api', '/reference']):
            return "documentation"
        if any(x in url_lower for x in ['/review', '/compare', '/vs']):
            return "review"
        if any(x in domain for x in ['news', 'techcrunch', 'wired', 'verge']):
            return "news"
        if any(x in url_lower for x in ['/tutorial', '/guide', '/how-to', '/learn']):
            return "tutorial"
        if any(x in domain for x in ['amazon', 'ebay', 'shop', 'store']):
            return "ecommerce"
        if any(x in url_lower for x in ['.edu', '/research', '/paper', '/study']):
            return "research"

        return "authority"

    def _extract_fan_out_queries(self, text: str) -> List[Dict]:
        """Extract web search queries that AI might have used"""
        queries = []

        # Look for patterns indicating search queries
        search_patterns = [
            r'(?:searching for|searched for|looking up|querying)[:\s]+"([^"]+)"',
            r'(?:web search|google search|search results for)[:\s]+"([^"]+)"',
            r'\[Search:\s*([^\]]+)\]',
        ]

        for pattern in search_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                query_text = match.group(1)
                queries.append({
                    "query": query_text,
                    "keywords": query_text.split()[:5],  # First 5 words as keywords
                })

        return queries

    def _extract_shopping_recommendations(
        self,
        text: str,
        brand_names: List[str],
        competitor_names: List[str]
    ) -> List[Dict]:
        """Extract product/shopping recommendations"""
        recommendations = []
        position = 0

        for pattern in self.SHOPPING_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                position += 1
                product_text = match.group(1).strip()

                # Check if any brand is mentioned
                is_own = any(b.lower() in product_text.lower() for b in brand_names)
                brand_name = next(
                    (b for b in brand_names if b.lower() in product_text.lower()),
                    None
                )
                if not brand_name:
                    brand_name = next(
                        (c for c in competitor_names if c.lower() in product_text.lower()),
                        None
                    )

                # Extract price if present
                price_match = re.search(r'\$[\d,]+(?:\.\d{2})?', product_text)
                price = price_match.group() if price_match else None

                recommendations.append({
                    "product_name": product_text,
                    "brand_name": brand_name,
                    "is_own_brand": is_own,
                    "position": position,
                    "type": self._classify_recommendation_type(match.group(0)),
                    "context": match.group(0),
                    "price": price,
                    "sentiment": "positive",
                    "strength": 0.8
                })

        return recommendations

    def _classify_recommendation_type(self, text: str) -> str:
        """Classify the type of recommendation"""
        text_lower = text.lower()
        if "best overall" in text_lower or "top pick" in text_lower:
            return "best_overall"
        if "budget" in text_lower:
            return "budget"
        if "premium" in text_lower:
            return "premium"
        if "runner" in text_lower or "alternative" in text_lower:
            return "runner_up"
        return "recommendation"

    def _analyze_sentiment(self, text: str, brand_names: List[str]) -> Dict:
        """Analyze overall and brand-specific sentiment"""
        # Simple keyword-based sentiment (in production, use ML model)
        positive_words = [
            'excellent', 'great', 'best', 'amazing', 'outstanding', 'superior',
            'recommended', 'favorite', 'love', 'perfect', 'innovative', 'leading'
        ]
        negative_words = [
            'poor', 'bad', 'worst', 'terrible', 'avoid', 'disappointing',
            'expensive', 'overpriced', 'lacking', 'limited', 'issues', 'problems'
        ]

        text_lower = text.lower()

        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)

        # Calculate sentiment score (-1 to 1)
        total = pos_count + neg_count
        if total == 0:
            score = 0
            sentiment = "neutral"
        else:
            score = (pos_count - neg_count) / total
            if score > 0.2:
                sentiment = "positive"
            elif score < -0.2:
                sentiment = "negative"
            else:
                sentiment = "neutral"

        # Brand-specific sentiment (check context around brand mentions)
        brand_sentiment = sentiment
        for brand in brand_names:
            pattern = rf'.{{0,50}}{re.escape(brand)}.{{0,50}}'
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                brand_context = " ".join(matches)
                brand_pos = sum(1 for w in positive_words if w in brand_context.lower())
                brand_neg = sum(1 for w in negative_words if w in brand_context.lower())
                if brand_pos > brand_neg:
                    brand_sentiment = "positive"
                elif brand_neg > brand_pos:
                    brand_sentiment = "negative"
                break

        return {
            "overall": sentiment,
            "brand_sentiment": brand_sentiment,
            "score": score,
            "positive_signals": pos_count,
            "negative_signals": neg_count
        }

    def _calculate_visibility_scores(
        self,
        mentions: List[Dict],
        citations: List[Dict],
        sentiment: Dict,
        our_domain: str,
        response_length: int
    ) -> Dict[str, float]:
        """Calculate component visibility scores"""

        # Mention score (0-100)
        own_mentions = [m for m in mentions if m["is_own_brand"]]
        if own_mentions:
            # Score based on position (first = 100, second = 80, etc.)
            best_position = min(m["position"] for m in own_mentions)
            mention_score = max(0, 100 - (best_position - 1) * 15)
        else:
            mention_score = 0

        # Position score (0-100)
        if own_mentions:
            total_mentions = len(mentions)
            own_positions = [m["position"] for m in own_mentions]
            avg_position = sum(own_positions) / len(own_positions)
            position_score = max(0, 100 - (avg_position / total_mentions) * 50)
        else:
            position_score = 0

        # Citation score (0-100)
        own_citations = [c for c in citations if c.get("is_own_domain")]
        if own_citations:
            best_citation_pos = min(c["position"] for c in own_citations)
            citation_score = max(0, 100 - (best_citation_pos - 1) * 10)
        elif citations:
            citation_score = 10  # Cited overall but not us
        else:
            citation_score = 0

        # Sentiment score (0-100)
        sentiment_map = {"positive": 100, "neutral": 50, "negative": 0}
        brand_sentiment = sentiment.get("brand_sentiment", "neutral")
        sentiment_score = sentiment_map.get(brand_sentiment, 50)

        # Total score (weighted average)
        weights = {
            "mention": 0.35,
            "position": 0.25,
            "citation": 0.25,
            "sentiment": 0.15
        }

        total_score = (
            mention_score * weights["mention"] +
            position_score * weights["position"] +
            citation_score * weights["citation"] +
            sentiment_score * weights["sentiment"]
        )

        return {
            "mention_score": round(mention_score, 2),
            "position_score": round(position_score, 2),
            "citation_score": round(citation_score, 2),
            "sentiment_score": round(sentiment_score, 2),
            "total_score": round(total_score, 2)
        }

    def _detect_response_format(self, text: str) -> str:
        """Detect the format of the response"""
        # Check for list patterns
        list_patterns = [
            r'^\s*[\d]+\.\s+',  # Numbered list
            r'^\s*[-*•]\s+',    # Bullet list
        ]

        lines = text.split('\n')
        list_lines = 0
        for line in lines:
            for pattern in list_patterns:
                if re.match(pattern, line):
                    list_lines += 1
                    break

        if list_lines >= 3:
            return "list"
        elif list_lines > 0:
            return "mixed"
        else:
            return "paragraph"

    async def _get_or_create_citation_source(self, domain: str) -> Optional[CitationSource]:
        """Get or create a citation source by domain"""
        result = await self.db.execute(
            select(CitationSource).where(CitationSource.domain == domain)
        )
        source = result.scalar_one_or_none()

        if not source:
            source = CitationSource(domain=domain)
            self.db.add(source)
            await self.db.flush()

        return source
