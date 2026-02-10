"""
Citation Extractor
Extracts and validates URLs from LLM responses
"""

import asyncio
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from urllib.parse import urlparse, urljoin

import httpx


@dataclass
class ExtractedCitation:
    """An extracted citation from LLM response"""
    url: str
    domain: str                  # Normalized domain
    anchor_text: Optional[str]   # Link text or context
    context_snippet: str         # Surrounding context
    position: int                # Order in response (1-indexed)
    is_valid_url: bool           # Syntactically valid
    is_accessible: Optional[bool] = None  # HTTP check result
    http_status_code: Optional[int] = None
    is_hallucinated: bool = False  # URL doesn't exist


class CitationExtractor:
    """
    Extracts URLs from LLM responses and validates them.
    Handles various URL formats and markdown links.
    """

    # Context window for snippets
    CONTEXT_WINDOW = 100

    # Timeout for URL validation
    VALIDATION_TIMEOUT = 10

    # URL patterns
    URL_PATTERNS = [
        # Standard URLs
        r'https?://[^\s<>"\')\]]+',
        # Markdown links [text](url)
        r'\[([^\]]+)\]\((https?://[^)]+)\)',
        # URLs without protocol (www.)
        r'(?<![/@])www\.[^\s<>"\')\]]+',
    ]

    # Domains that are commonly hallucinated
    SUSPICIOUS_DOMAINS = [
        "example.com",
        "placeholder.com",
        "yoursite.com",
        "company.com",
        "brandname.com",
    ]

    def __init__(self, validate_urls: bool = True):
        self.validate_urls = validate_urls

    def _normalize_domain(self, url: str) -> str:
        """Extract and normalize domain from URL"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()

            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]

            # Remove port
            if ":" in domain:
                domain = domain.split(":")[0]

            return domain
        except Exception:
            return ""

    def _get_context(self, text: str, start: int, end: int) -> str:
        """Extract context around a citation"""
        context_start = max(0, start - self.CONTEXT_WINDOW)
        context_end = min(len(text), end + self.CONTEXT_WINDOW)

        context = text[context_start:context_end]

        if context_start > 0:
            context = "..." + context
        if context_end < len(text):
            context = context + "..."

        return context.strip()

    def _clean_url(self, url: str) -> str:
        """Clean and normalize URL"""
        # Remove trailing punctuation that got caught
        url = re.sub(r'[.,;:!?\'")\]]+$', '', url)

        # Add protocol if missing
        if url.startswith("www."):
            url = "https://" + url

        return url

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is syntactically valid"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False

    def extract_citations(self, text: str) -> List[ExtractedCitation]:
        """
        Extract all citations from text.

        Args:
            text: LLM response text

        Returns:
            List of ExtractedCitation objects
        """
        citations = []
        found_urls = set()
        position = 0

        # Extract markdown links first
        markdown_pattern = r'\[([^\]]+)\]\((https?://[^)]+)\)'
        for match in re.finditer(markdown_pattern, text):
            anchor_text = match.group(1)
            url = self._clean_url(match.group(2))

            if url in found_urls:
                continue
            found_urls.add(url)

            position += 1
            domain = self._normalize_domain(url)

            citations.append(ExtractedCitation(
                url=url,
                domain=domain,
                anchor_text=anchor_text,
                context_snippet=self._get_context(text, match.start(), match.end()),
                position=position,
                is_valid_url=self._is_valid_url(url),
                is_hallucinated=domain in self.SUSPICIOUS_DOMAINS,
            ))

        # Extract plain URLs
        plain_url_pattern = r'https?://[^\s<>"\')\]]+|(?<![/@])www\.[^\s<>"\')\]]+'
        for match in re.finditer(plain_url_pattern, text):
            url = self._clean_url(match.group())

            if url in found_urls:
                continue
            found_urls.add(url)

            position += 1
            domain = self._normalize_domain(url)

            citations.append(ExtractedCitation(
                url=url,
                domain=domain,
                anchor_text=None,
                context_snippet=self._get_context(text, match.start(), match.end()),
                position=position,
                is_valid_url=self._is_valid_url(url),
                is_hallucinated=domain in self.SUSPICIOUS_DOMAINS,
            ))

        return citations

    async def validate_citation(self, citation: ExtractedCitation) -> ExtractedCitation:
        """
        Validate a citation by checking if the URL is accessible.

        Args:
            citation: The citation to validate

        Returns:
            Updated citation with validation results
        """
        if not citation.is_valid_url:
            citation.is_accessible = False
            citation.is_hallucinated = True
            return citation

        try:
            async with httpx.AsyncClient(
                timeout=self.VALIDATION_TIMEOUT,
                follow_redirects=True
            ) as client:
                response = await client.head(citation.url)
                citation.http_status_code = response.status_code
                citation.is_accessible = response.status_code < 400

                # Mark as hallucinated if 404 or similar
                if response.status_code == 404:
                    citation.is_hallucinated = True

        except httpx.TimeoutException:
            citation.is_accessible = None  # Unknown
        except httpx.RequestError:
            citation.is_accessible = False
            citation.is_hallucinated = True

        return citation

    async def validate_citations(
        self,
        citations: List[ExtractedCitation],
        max_concurrent: int = 5
    ) -> List[ExtractedCitation]:
        """
        Validate multiple citations concurrently.

        Args:
            citations: List of citations to validate
            max_concurrent: Maximum concurrent requests

        Returns:
            Updated citations with validation results
        """
        if not self.validate_urls:
            return citations

        semaphore = asyncio.Semaphore(max_concurrent)

        async def validate_with_semaphore(citation):
            async with semaphore:
                return await self.validate_citation(citation)

        tasks = [validate_with_semaphore(c) for c in citations]
        return await asyncio.gather(*tasks)

    def extract_perplexity_citations(
        self,
        text: str,
        citation_list: List[str]
    ) -> List[ExtractedCitation]:
        """
        Extract citations from Perplexity response.
        Perplexity provides citations in a separate list.

        Args:
            text: Response text
            citation_list: List of URLs from Perplexity

        Returns:
            List of ExtractedCitation objects
        """
        citations = []

        for i, url in enumerate(citation_list, 1):
            url = self._clean_url(url)
            domain = self._normalize_domain(url)

            # Try to find where this citation is referenced in text
            # Perplexity uses [1], [2], etc.
            ref_pattern = rf'\[{i}\]'
            ref_match = re.search(ref_pattern, text)

            context = ""
            if ref_match:
                context = self._get_context(text, ref_match.start(), ref_match.end())

            citations.append(ExtractedCitation(
                url=url,
                domain=domain,
                anchor_text=None,
                context_snippet=context,
                position=i,
                is_valid_url=self._is_valid_url(url),
                is_hallucinated=domain in self.SUSPICIOUS_DOMAINS,
            ))

        return citations
