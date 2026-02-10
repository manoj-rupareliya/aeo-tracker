"""
Brand Matching Engine
Detects brand mentions with exact and fuzzy matching
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from rapidfuzz import fuzz, process


@dataclass
class BrandMatch:
    """A detected brand mention"""
    mentioned_text: str          # Exact text found in response
    normalized_name: str         # Normalized brand name
    position: int                # Position in list of mentions (1-indexed)
    character_offset: int        # Character position in text
    context_snippet: str         # Surrounding context
    match_type: str              # "exact", "alias", "fuzzy"
    match_confidence: float      # 0.0 - 1.0
    is_own_brand: bool           # True if this is the tracked brand
    brand_id: Optional[str] = None
    competitor_id: Optional[str] = None


@dataclass
class BrandConfig:
    """Configuration for a brand to match"""
    id: str
    name: str
    aliases: List[str] = field(default_factory=list)
    is_own_brand: bool = True


class BrandMatcher:
    """
    Matches brand names in text using multiple strategies:
    1. Exact match (case-insensitive)
    2. Alias match
    3. Fuzzy match (for typos, variations)
    """

    # Minimum fuzzy match score to consider a match
    FUZZY_THRESHOLD = 85

    # Context window size (characters before/after match)
    CONTEXT_WINDOW = 100

    def __init__(
        self,
        own_brands: List[BrandConfig],
        competitor_brands: List[BrandConfig]
    ):
        self.own_brands = own_brands
        self.competitor_brands = competitor_brands
        self._build_match_index()

    def _build_match_index(self):
        """Build index for efficient matching"""
        self.exact_matches = {}  # lowercase -> BrandConfig
        self.all_brand_names = []  # For fuzzy matching

        for brand in self.own_brands + self.competitor_brands:
            # Add primary name
            self.exact_matches[brand.name.lower()] = brand
            self.all_brand_names.append((brand.name, brand))

            # Add aliases
            for alias in brand.aliases:
                self.exact_matches[alias.lower()] = brand
                self.all_brand_names.append((alias, brand))

    def _get_context(self, text: str, start: int, end: int) -> str:
        """Extract context around a match"""
        context_start = max(0, start - self.CONTEXT_WINDOW)
        context_end = min(len(text), end + self.CONTEXT_WINDOW)

        context = text[context_start:context_end]

        # Add ellipsis if truncated
        if context_start > 0:
            context = "..." + context
        if context_end < len(text):
            context = context + "..."

        return context.strip()

    def _find_exact_matches(self, text: str) -> List[Tuple[str, int, BrandConfig]]:
        """Find exact and alias matches"""
        matches = []
        text_lower = text.lower()

        for match_text, brand in self.exact_matches.items():
            # Find all occurrences
            start = 0
            while True:
                pos = text_lower.find(match_text, start)
                if pos == -1:
                    break

                # Check word boundaries
                before_ok = pos == 0 or not text_lower[pos - 1].isalnum()
                after_ok = (pos + len(match_text) >= len(text_lower) or
                           not text_lower[pos + len(match_text)].isalnum())

                if before_ok and after_ok:
                    # Get actual text (preserving case)
                    actual_text = text[pos:pos + len(match_text)]
                    matches.append((actual_text, pos, brand))

                start = pos + 1

        return matches

    def _find_fuzzy_matches(
        self,
        text: str,
        exclude_positions: List[Tuple[int, int]]
    ) -> List[Tuple[str, int, BrandConfig, float]]:
        """Find fuzzy matches for brand names"""
        matches = []

        # Extract potential brand mentions (capitalized words/phrases)
        pattern = r'\b[A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)*\b'
        potential_matches = re.finditer(pattern, text)

        for match in potential_matches:
            candidate = match.group()
            start, end = match.span()

            # Skip if overlaps with exact match
            if any(s <= start < e or s < end <= e for s, e in exclude_positions):
                continue

            # Try to match against brand names
            brand_names = [name for name, _ in self.all_brand_names]
            result = process.extractOne(
                candidate,
                brand_names,
                scorer=fuzz.ratio,
                score_cutoff=self.FUZZY_THRESHOLD
            )

            if result:
                matched_name, score, _ = result
                # Find the brand config
                for name, brand in self.all_brand_names:
                    if name == matched_name:
                        matches.append((candidate, start, brand, score / 100.0))
                        break

        return matches

    def find_mentions(self, text: str) -> List[BrandMatch]:
        """
        Find all brand mentions in text.

        Args:
            text: The LLM response text to analyze

        Returns:
            List of BrandMatch objects, ordered by position
        """
        mentions = []

        # Find exact matches first
        exact_matches = self._find_exact_matches(text)
        exact_positions = [(pos, pos + len(match_text)) for match_text, pos, _ in exact_matches]

        for match_text, pos, brand in exact_matches:
            # Determine match type
            if match_text.lower() == brand.name.lower():
                match_type = "exact"
            else:
                match_type = "alias"

            mentions.append(BrandMatch(
                mentioned_text=match_text,
                normalized_name=brand.name,
                position=0,  # Will be set after sorting
                character_offset=pos,
                context_snippet=self._get_context(text, pos, pos + len(match_text)),
                match_type=match_type,
                match_confidence=1.0,
                is_own_brand=brand.is_own_brand,
                brand_id=brand.id if brand.is_own_brand else None,
                competitor_id=brand.id if not brand.is_own_brand else None,
            ))

        # Find fuzzy matches
        fuzzy_matches = self._find_fuzzy_matches(text, exact_positions)

        for match_text, pos, brand, confidence in fuzzy_matches:
            mentions.append(BrandMatch(
                mentioned_text=match_text,
                normalized_name=brand.name,
                position=0,  # Will be set after sorting
                character_offset=pos,
                context_snippet=self._get_context(text, pos, pos + len(match_text)),
                match_type="fuzzy",
                match_confidence=confidence,
                is_own_brand=brand.is_own_brand,
                brand_id=brand.id if brand.is_own_brand else None,
                competitor_id=brand.id if not brand.is_own_brand else None,
            ))

        # Sort by position and assign position numbers
        mentions.sort(key=lambda m: m.character_offset)
        for i, mention in enumerate(mentions):
            mention.position = i + 1

        return mentions

    def get_own_brand_mentions(self, mentions: List[BrandMatch]) -> List[BrandMatch]:
        """Filter to only own brand mentions"""
        return [m for m in mentions if m.is_own_brand]

    def get_competitor_mentions(self, mentions: List[BrandMatch]) -> List[BrandMatch]:
        """Filter to only competitor mentions"""
        return [m for m in mentions if not m.is_own_brand]

    def get_first_mention(self, mentions: List[BrandMatch]) -> Optional[BrandMatch]:
        """Get the first mention (by position)"""
        if not mentions:
            return None
        return min(mentions, key=lambda m: m.position)

    def is_in_top_n(
        self,
        mentions: List[BrandMatch],
        brand_name: str,
        n: int = 3
    ) -> bool:
        """Check if a brand appears in top N mentions"""
        top_n = sorted(mentions, key=lambda m: m.position)[:n]
        return any(m.normalized_name.lower() == brand_name.lower() for m in top_n)
