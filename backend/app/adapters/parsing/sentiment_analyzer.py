"""
Sentiment Analyzer
Basic polarity detection for brand mentions
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from app.models import SentimentPolarity


@dataclass
class SentimentResult:
    """Result of sentiment analysis"""
    polarity: SentimentPolarity
    score: float  # -1.0 to 1.0
    confidence: float  # 0.0 to 1.0
    matched_indicators: List[str]  # Words/phrases that contributed


class SentimentAnalyzer:
    """
    Simple rule-based sentiment analyzer for brand mentions.
    Focused on accuracy over coverage for business-critical decisions.
    """

    # Positive indicators
    POSITIVE_WORDS = [
        # Strong positive
        "excellent", "outstanding", "exceptional", "best", "leading",
        "innovative", "powerful", "impressive", "remarkable", "superior",
        "recommended", "top-rated", "highly rated", "popular", "trusted",
        # Moderate positive
        "good", "great", "reliable", "effective", "efficient", "useful",
        "helpful", "solid", "strong", "quality", "professional", "robust",
        "comprehensive", "intuitive", "user-friendly", "easy to use",
        # Mild positive
        "nice", "decent", "adequate", "suitable", "capable", "competent",
    ]

    POSITIVE_PHRASES = [
        "market leader", "industry standard", "widely used", "well-known",
        "highly recommended", "top choice", "go-to solution", "best-in-class",
        "stands out", "excels at", "known for", "trusted by",
    ]

    # Negative indicators
    NEGATIVE_WORDS = [
        # Strong negative
        "terrible", "awful", "worst", "poor", "failing", "broken",
        "disappointing", "frustrating", "unreliable", "outdated",
        # Moderate negative
        "bad", "weak", "limited", "lacking", "difficult", "complicated",
        "expensive", "overpriced", "slow", "buggy", "problematic",
        # Mild negative
        "basic", "mediocre", "average", "inconsistent", "challenging",
    ]

    NEGATIVE_PHRASES = [
        "not recommended", "avoid", "stay away", "better alternatives",
        "falls short", "lacks", "struggles with", "fails to",
        "not the best", "losing market share", "outdated",
    ]

    # Neutral indicators (when present, often indicates neutral context)
    NEUTRAL_PHRASES = [
        "one of the", "among the", "similar to", "comparable to",
        "like other", "as with", "depending on",
    ]

    # Negation words that flip sentiment
    NEGATION_WORDS = ["not", "no", "never", "neither", "nor", "hardly", "barely", "doesn't", "don't", "isn't", "aren't"]

    def __init__(self):
        # Compile patterns for efficiency
        self._positive_pattern = self._build_pattern(self.POSITIVE_WORDS + self.POSITIVE_PHRASES)
        self._negative_pattern = self._build_pattern(self.NEGATIVE_WORDS + self.NEGATIVE_PHRASES)
        self._negation_pattern = self._build_pattern(self.NEGATION_WORDS)

    def _build_pattern(self, words: List[str]) -> re.Pattern:
        """Build regex pattern from word list"""
        escaped = [re.escape(w) for w in words]
        pattern = r'\b(' + '|'.join(escaped) + r')\b'
        return re.compile(pattern, re.IGNORECASE)

    def _check_negation(self, text: str, match_start: int, window: int = 30) -> bool:
        """Check if there's a negation word before the match"""
        context_start = max(0, match_start - window)
        context = text[context_start:match_start].lower()
        return bool(self._negation_pattern.search(context))

    def analyze(self, text: str) -> SentimentResult:
        """
        Analyze sentiment of text.

        Args:
            text: Text to analyze

        Returns:
            SentimentResult with polarity and score
        """
        if not text:
            return SentimentResult(
                polarity=SentimentPolarity.NEUTRAL,
                score=0.0,
                confidence=0.0,
                matched_indicators=[]
            )

        text_lower = text.lower()
        positive_score = 0.0
        negative_score = 0.0
        matched_indicators = []

        # Find positive matches
        for match in self._positive_pattern.finditer(text_lower):
            word = match.group()
            # Check for negation
            if self._check_negation(text_lower, match.start()):
                negative_score += 0.5  # Negated positive becomes mild negative
                matched_indicators.append(f"NOT {word}")
            else:
                # Weight strong indicators more
                if word in ["excellent", "outstanding", "best", "exceptional"]:
                    positive_score += 1.5
                elif word in ["good", "great", "reliable"]:
                    positive_score += 1.0
                else:
                    positive_score += 0.5
                matched_indicators.append(word)

        # Find negative matches
        for match in self._negative_pattern.finditer(text_lower):
            word = match.group()
            # Check for negation (double negative = positive)
            if self._check_negation(text_lower, match.start()):
                positive_score += 0.3  # Negated negative is mild positive
                matched_indicators.append(f"NOT {word}")
            else:
                # Weight strong indicators more
                if word in ["terrible", "awful", "worst", "poor"]:
                    negative_score += 1.5
                elif word in ["bad", "weak", "unreliable"]:
                    negative_score += 1.0
                else:
                    negative_score += 0.5
                matched_indicators.append(word)

        # Calculate final score (-1 to 1)
        total = positive_score + negative_score
        if total == 0:
            final_score = 0.0
            confidence = 0.0
        else:
            final_score = (positive_score - negative_score) / total
            # Scale to -1 to 1 range
            final_score = max(-1.0, min(1.0, final_score))
            # Confidence based on number of indicators
            confidence = min(1.0, len(matched_indicators) / 5.0)

        # Determine polarity
        if final_score > 0.2:
            polarity = SentimentPolarity.POSITIVE
        elif final_score < -0.2:
            polarity = SentimentPolarity.NEGATIVE
        else:
            polarity = SentimentPolarity.NEUTRAL

        return SentimentResult(
            polarity=polarity,
            score=final_score,
            confidence=confidence,
            matched_indicators=matched_indicators
        )

    def analyze_mention_context(
        self,
        full_text: str,
        mention_start: int,
        mention_end: int,
        context_window: int = 150
    ) -> SentimentResult:
        """
        Analyze sentiment specifically around a brand mention.

        Args:
            full_text: Full LLM response
            mention_start: Character offset of mention start
            mention_end: Character offset of mention end
            context_window: Characters to analyze around mention

        Returns:
            SentimentResult for the mention context
        """
        # Extract context around mention
        context_start = max(0, mention_start - context_window)
        context_end = min(len(full_text), mention_end + context_window)
        context = full_text[context_start:context_end]

        return self.analyze(context)
