"""
Serper.dev API Service
Fetches Google Search results including AI Overview (AIO) data
"""

import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime
import re
from urllib.parse import urlparse


class SerperService:
    """
    Service to interact with Serper.dev API for Google SERP data
    including AI Overviews (SGE/AIO)
    """

    BASE_URL = "https://google.serper.dev/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(
        self,
        query: str,
        country: str = "in",  # Default to India
        language: str = "en",
        num_results: int = 10
    ) -> Dict[str, Any]:
        """
        Perform a Google search and return results including AI Overview

        Args:
            query: Search query
            country: Country code (e.g., 'us', 'in', 'uk')
            language: Language code (e.g., 'en')
            num_results: Number of organic results to return

        Returns:
            Dict containing search results, AI overview, and metadata
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self.BASE_URL,
                headers={
                    "X-API-KEY": self.api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "q": query,
                    "gl": country,
                    "hl": language,
                    "num": num_results,
                    "autocorrect": True
                }
            )

            if response.status_code != 200:
                raise Exception(f"Serper API error: {response.status_code} - {response.text}")

            return response.json()

    async def get_ai_overview(
        self,
        query: str,
        brand_name: str,
        brand_domain: str,
        competitors: List[str] = None,
        country: str = "in"
    ) -> Dict[str, Any]:
        """
        Get AI Overview data for a search query and analyze brand presence

        Args:
            query: Search query (keyword)
            brand_name: The brand name to look for
            brand_domain: The brand's domain (e.g., 'factohr.com')
            competitors: List of competitor names to track
            country: Country code for search

        Returns:
            Dict containing AIO analysis results
        """
        # Perform search
        search_results = await self.search(query, country=country)

        # Extract AI Overview if present
        ai_overview = search_results.get("aiOverview") or search_results.get("answerBox")
        knowledge_graph = search_results.get("knowledgeGraph")
        organic_results = search_results.get("organic", [])

        # Analyze AI Overview
        aio_analysis = self._analyze_ai_overview(
            ai_overview=ai_overview,
            knowledge_graph=knowledge_graph,
            organic_results=organic_results,
            brand_name=brand_name,
            brand_domain=brand_domain,
            competitors=competitors or []
        )

        return {
            "query": query,
            "search_timestamp": datetime.utcnow().isoformat(),
            "country": country,
            "has_ai_overview": ai_overview is not None,
            "has_knowledge_graph": knowledge_graph is not None,
            "ai_overview_raw": ai_overview,
            "knowledge_graph": knowledge_graph,
            "organic_results_count": len(organic_results),
            "organic_results": organic_results[:5],  # Top 5 organic results
            **aio_analysis
        }

    def _analyze_ai_overview(
        self,
        ai_overview: Optional[Dict],
        knowledge_graph: Optional[Dict],
        organic_results: List[Dict],
        brand_name: str,
        brand_domain: str,
        competitors: List[str]
    ) -> Dict[str, Any]:
        """Analyze AI Overview for brand and competitor presence"""

        result = {
            "brand_in_aio": False,
            "brand_aio_position": None,
            "brand_aio_context": None,
            "domain_in_aio": False,
            "domain_aio_position": None,
            "aio_sources": [],
            "aio_mentions": [],
            "competitors_in_aio": [],
            "aio_text": None,
            "aio_type": None,
            # Organic results analysis
            "brand_in_organic": False,
            "brand_organic_position": None,
            "competitors_in_organic": []
        }

        brand_name_lower = brand_name.lower()
        brand_domain_clean = brand_domain.lower().replace("www.", "")

        # Analyze AI Overview content
        if ai_overview:
            aio_text = ""
            aio_type = "unknown"

            # Handle different AI Overview formats from Serper
            if isinstance(ai_overview, dict):
                # Check for snippet/answer
                if "snippet" in ai_overview:
                    aio_text = ai_overview.get("snippet", "")
                    aio_type = "snippet"
                elif "answer" in ai_overview:
                    aio_text = ai_overview.get("answer", "")
                    aio_type = "answer"
                elif "text" in ai_overview:
                    aio_text = ai_overview.get("text", "")
                    aio_type = "text"
                elif "description" in ai_overview:
                    aio_text = ai_overview.get("description", "")
                    aio_type = "description"

                # Check for list items
                if "items" in ai_overview:
                    items = ai_overview.get("items", [])
                    aio_text += " " + " ".join([str(item) for item in items])
                    aio_type = "list"

                # Check for sources/citations in AI Overview
                sources = ai_overview.get("sources", []) or ai_overview.get("citations", [])
                if sources:
                    result["aio_sources"] = sources
                    # Check if our domain is in sources
                    for i, source in enumerate(sources):
                        source_url = source.get("link", "") or source.get("url", "") or str(source)
                        if brand_domain_clean in source_url.lower():
                            result["domain_in_aio"] = True
                            result["domain_aio_position"] = i + 1

            elif isinstance(ai_overview, str):
                aio_text = ai_overview
                aio_type = "text"

            result["aio_text"] = aio_text
            result["aio_type"] = aio_type

            # Check for brand mention in AI Overview text
            if aio_text:
                aio_text_lower = aio_text.lower()

                # Check brand name
                if brand_name_lower in aio_text_lower:
                    result["brand_in_aio"] = True
                    # Find position (which mention number)
                    position = self._find_mention_position(aio_text_lower, brand_name_lower)
                    result["brand_aio_position"] = position
                    # Get context
                    result["brand_aio_context"] = self._get_context(aio_text, brand_name_lower)

                # Check domain
                if brand_domain_clean in aio_text_lower:
                    result["domain_in_aio"] = True
                    if not result["domain_aio_position"]:
                        result["domain_aio_position"] = self._find_mention_position(aio_text_lower, brand_domain_clean)

                # Extract all brand/company mentions
                result["aio_mentions"] = self._extract_mentions(aio_text)

                # Check competitors
                for competitor in competitors:
                    if competitor.lower() in aio_text_lower:
                        position = self._find_mention_position(aio_text_lower, competitor.lower())
                        result["competitors_in_aio"].append({
                            "name": competitor,
                            "position": position,
                            "context": self._get_context(aio_text, competitor.lower())
                        })

        # Analyze Knowledge Graph
        if knowledge_graph:
            kg_title = knowledge_graph.get("title", "").lower()
            kg_description = knowledge_graph.get("description", "").lower()

            if brand_name_lower in kg_title or brand_name_lower in kg_description:
                result["brand_in_aio"] = True
                result["aio_type"] = "knowledge_graph"

        # Analyze Organic Results
        for i, item in enumerate(organic_results):
            link = item.get("link", "").lower()
            title = item.get("title", "").lower()
            snippet = item.get("snippet", "").lower()

            # Check if our domain is in organic results
            if brand_domain_clean in link:
                result["brand_in_organic"] = True
                if result["brand_organic_position"] is None:
                    result["brand_organic_position"] = i + 1

            # Check competitors in organic
            for competitor in competitors:
                comp_lower = competitor.lower()
                if comp_lower in title or comp_lower in snippet:
                    # Check if already added
                    existing = next((c for c in result["competitors_in_organic"] if c["name"] == competitor), None)
                    if not existing:
                        result["competitors_in_organic"].append({
                            "name": competitor,
                            "position": i + 1,
                            "url": item.get("link", "")
                        })

        return result

    def _find_mention_position(self, text: str, term: str) -> int:
        """Find which position (1st, 2nd, etc.) a term appears among all brand mentions"""
        # Simple implementation - find all capitalized words/phrases and count position
        words = re.findall(r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b', text, re.IGNORECASE)
        for i, word in enumerate(words):
            if term in word.lower():
                return i + 1
        return 1

    def _get_context(self, text: str, term: str, context_chars: int = 100) -> str:
        """Get surrounding context for a term"""
        text_lower = text.lower()
        pos = text_lower.find(term)
        if pos == -1:
            return ""

        start = max(0, pos - context_chars)
        end = min(len(text), pos + len(term) + context_chars)
        return text[start:end]

    def _extract_mentions(self, text: str) -> List[Dict]:
        """Extract all potential brand/company mentions from text"""
        mentions = []
        seen = set()

        # Pattern for capitalized words/phrases (potential brands)
        patterns = [
            r'\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b',  # Single or two word brands
            r'\b([A-Z][a-zA-Z]+(?:HR|AI|CRM|ERP))\b',  # Tech product patterns
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text):
                name = match.group(1).strip()
                name_lower = name.lower()

                # Skip common words
                skip_words = {'the', 'this', 'that', 'these', 'with', 'from', 'they', 'their',
                             'have', 'been', 'will', 'would', 'could', 'should', 'here', 'there',
                             'what', 'when', 'where', 'which', 'how', 'why', 'can', 'may'}
                if name_lower in skip_words:
                    continue

                if len(name) >= 3 and name_lower not in seen:
                    seen.add(name_lower)
                    mentions.append({
                        "name": name,
                        "position": match.start()
                    })

        # Sort by position
        mentions.sort(key=lambda x: x["position"])

        # Re-index positions
        for i, m in enumerate(mentions):
            m["position"] = i + 1

        return mentions[:10]  # Return top 10 mentions


async def test_serper_api(api_key: str):
    """Test the Serper API connection"""
    service = SerperService(api_key)
    try:
        result = await service.search("best HR software", num_results=3)
        return {
            "success": True,
            "has_ai_overview": "aiOverview" in result or "answerBox" in result,
            "organic_count": len(result.get("organic", [])),
            "credits_remaining": result.get("credits", "unknown")
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
