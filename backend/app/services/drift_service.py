"""
Change & Drift Detection Engine
Tracks how LLM behavior changes over time and alerts on significant drift
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import LLMProvider, SentimentPolarity, LLMRun, LLMResponse, BrandMention
from ..models.models_v2 import (
    ResponseSnapshot, DriftRecord, DriftType, DriftSeverity
)


class DriftDetectionEngine:
    """
    Engine for detecting and analyzing changes in LLM behavior over time.
    Compares snapshots to identify brand appearance changes, position shifts,
    citation replacements, and competitor displacements.
    """

    # Thresholds for severity classification
    POSITION_THRESHOLDS = {
        "minor": 1,      # 1 position change
        "moderate": 3,   # 2-3 position change
        "major": 5,      # 4-5 position change
        "critical": 6,   # 6+ position change
    }

    SCORE_THRESHOLDS = {
        "minor": 5,      # 5 point change
        "moderate": 15,  # 15 point change
        "major": 30,     # 30 point change
        "critical": 50,  # 50+ point change
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # SNAPSHOT MANAGEMENT
    # =========================================================================

    async def create_snapshot(
        self,
        project_id: UUID,
        keyword_id: UUID,
        prompt_hash: str,
        provider: LLMProvider,
        llm_run_id: UUID,
        response_hash: str,
        brand_mentioned: bool,
        brand_position: Optional[int] = None,
        competitor_positions: Optional[Dict[str, int]] = None,
        citations: Optional[List[str]] = None,
        sentiment: Optional[SentimentPolarity] = None,
        visibility_score: Optional[float] = None,
        snapshot_date: Optional[datetime] = None,
    ) -> ResponseSnapshot:
        """
        Create a point-in-time snapshot of a response for later comparison.
        """
        # Check if this is the first snapshot for this combination
        existing = await self.db.execute(
            select(ResponseSnapshot).where(
                and_(
                    ResponseSnapshot.project_id == project_id,
                    ResponseSnapshot.keyword_id == keyword_id,
                    ResponseSnapshot.provider == provider,
                )
            ).limit(1)
        )
        is_baseline = existing.scalar_one_or_none() is None

        snapshot = ResponseSnapshot(
            project_id=project_id,
            keyword_id=keyword_id,
            prompt_hash=prompt_hash,
            provider=provider,
            llm_run_id=llm_run_id,
            response_hash=response_hash,
            brand_mentioned=brand_mentioned,
            brand_position=brand_position,
            competitor_positions=competitor_positions or {},
            citations=citations or [],
            sentiment=sentiment,
            visibility_score=visibility_score,
            snapshot_date=snapshot_date or datetime.utcnow(),
            is_baseline=is_baseline,
        )

        self.db.add(snapshot)
        await self.db.flush()
        return snapshot

    async def get_latest_snapshot(
        self,
        project_id: UUID,
        keyword_id: UUID,
        provider: LLMProvider,
    ) -> Optional[ResponseSnapshot]:
        """Get the most recent snapshot for comparison."""
        result = await self.db.execute(
            select(ResponseSnapshot)
            .where(
                and_(
                    ResponseSnapshot.project_id == project_id,
                    ResponseSnapshot.keyword_id == keyword_id,
                    ResponseSnapshot.provider == provider,
                )
            )
            .order_by(ResponseSnapshot.snapshot_date.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_baseline_snapshot(
        self,
        project_id: UUID,
        keyword_id: UUID,
        provider: LLMProvider,
    ) -> Optional[ResponseSnapshot]:
        """Get the baseline (first) snapshot for comparison."""
        result = await self.db.execute(
            select(ResponseSnapshot)
            .where(
                and_(
                    ResponseSnapshot.project_id == project_id,
                    ResponseSnapshot.keyword_id == keyword_id,
                    ResponseSnapshot.provider == provider,
                    ResponseSnapshot.is_baseline == True,
                )
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_snapshot_history(
        self,
        project_id: UUID,
        keyword_id: UUID,
        provider: Optional[LLMProvider] = None,
        days: int = 30,
    ) -> List[ResponseSnapshot]:
        """Get snapshot history for trend analysis."""
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(ResponseSnapshot).where(
            and_(
                ResponseSnapshot.project_id == project_id,
                ResponseSnapshot.keyword_id == keyword_id,
                ResponseSnapshot.snapshot_date >= start_date,
            )
        )

        if provider:
            query = query.where(ResponseSnapshot.provider == provider)

        query = query.order_by(ResponseSnapshot.snapshot_date.asc())

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # DRIFT DETECTION
    # =========================================================================

    async def detect_drift(
        self,
        current_snapshot: ResponseSnapshot,
        baseline_snapshot: Optional[ResponseSnapshot] = None,
    ) -> List[DriftRecord]:
        """
        Compare current snapshot against baseline and detect all drifts.
        Returns a list of drift records for each detected change.
        """
        if baseline_snapshot is None:
            baseline_snapshot = await self.get_latest_snapshot(
                current_snapshot.project_id,
                current_snapshot.keyword_id,
                current_snapshot.provider,
            )

        if baseline_snapshot is None or baseline_snapshot.id == current_snapshot.id:
            return []  # No comparison possible

        drifts = []

        # Check brand appearance/disappearance
        brand_drift = await self._detect_brand_drift(current_snapshot, baseline_snapshot)
        if brand_drift:
            drifts.append(brand_drift)

        # Check position changes
        position_drift = await self._detect_position_drift(current_snapshot, baseline_snapshot)
        if position_drift:
            drifts.append(position_drift)

        # Check citation changes
        citation_drifts = await self._detect_citation_drift(current_snapshot, baseline_snapshot)
        drifts.extend(citation_drifts)

        # Check competitor displacements
        competitor_drifts = await self._detect_competitor_drift(current_snapshot, baseline_snapshot)
        drifts.extend(competitor_drifts)

        # Check sentiment changes
        sentiment_drift = await self._detect_sentiment_drift(current_snapshot, baseline_snapshot)
        if sentiment_drift:
            drifts.append(sentiment_drift)

        return drifts

    async def _detect_brand_drift(
        self,
        current: ResponseSnapshot,
        baseline: ResponseSnapshot,
    ) -> Optional[DriftRecord]:
        """Detect brand appearance or disappearance."""
        if current.brand_mentioned == baseline.brand_mentioned:
            return None

        if current.brand_mentioned and not baseline.brand_mentioned:
            drift_type = DriftType.BRAND_APPEARED
            severity = DriftSeverity.MAJOR
            description = "Brand appeared in LLM response"
            action = "Monitor for consistency; this is a positive development"
        else:
            drift_type = DriftType.BRAND_DISAPPEARED
            severity = DriftSeverity.CRITICAL
            description = "Brand disappeared from LLM response"
            action = "Investigate cause; consider GEO improvements"

        drift = DriftRecord(
            project_id=current.project_id,
            keyword_id=current.keyword_id,
            baseline_snapshot_id=baseline.id,
            current_snapshot_id=current.id,
            provider=current.provider,
            drift_type=drift_type,
            severity=severity,
            previous_value=str(baseline.brand_mentioned),
            current_value=str(current.brand_mentioned),
            change_description=description,
            recommended_action=action,
            baseline_date=baseline.snapshot_date,
            current_date=current.snapshot_date,
        )

        self.db.add(drift)
        await self.db.flush()
        return drift

    async def _detect_position_drift(
        self,
        current: ResponseSnapshot,
        baseline: ResponseSnapshot,
    ) -> Optional[DriftRecord]:
        """Detect changes in brand position within response."""
        if current.brand_position is None or baseline.brand_position is None:
            return None

        if current.brand_position == baseline.brand_position:
            return None

        delta = baseline.brand_position - current.brand_position  # Positive = improved
        abs_delta = abs(delta)

        # Determine severity
        if abs_delta <= self.POSITION_THRESHOLDS["minor"]:
            severity = DriftSeverity.MINOR
        elif abs_delta <= self.POSITION_THRESHOLDS["moderate"]:
            severity = DriftSeverity.MODERATE
        elif abs_delta <= self.POSITION_THRESHOLDS["major"]:
            severity = DriftSeverity.MAJOR
        else:
            severity = DriftSeverity.CRITICAL

        if delta > 0:
            drift_type = DriftType.POSITION_IMPROVED
            description = f"Brand position improved by {abs_delta} places (#{baseline.brand_position} → #{current.brand_position})"
            action = "Maintain current GEO strategy"
        else:
            drift_type = DriftType.POSITION_DECLINED
            description = f"Brand position declined by {abs_delta} places (#{baseline.brand_position} → #{current.brand_position})"
            action = "Review competitor activity and strengthen content"

        drift = DriftRecord(
            project_id=current.project_id,
            keyword_id=current.keyword_id,
            baseline_snapshot_id=baseline.id,
            current_snapshot_id=current.id,
            provider=current.provider,
            drift_type=drift_type,
            severity=severity,
            previous_value=str(baseline.brand_position),
            current_value=str(current.brand_position),
            change_description=description,
            position_delta=delta,
            recommended_action=action,
            baseline_date=baseline.snapshot_date,
            current_date=current.snapshot_date,
        )

        self.db.add(drift)
        await self.db.flush()
        return drift

    async def _detect_citation_drift(
        self,
        current: ResponseSnapshot,
        baseline: ResponseSnapshot,
    ) -> List[DriftRecord]:
        """Detect changes in cited sources."""
        drifts = []

        current_citations = set(current.citations or [])
        baseline_citations = set(baseline.citations or [])

        # New citations
        added = current_citations - baseline_citations
        for citation in added:
            drift = DriftRecord(
                project_id=current.project_id,
                keyword_id=current.keyword_id,
                baseline_snapshot_id=baseline.id,
                current_snapshot_id=current.id,
                provider=current.provider,
                drift_type=DriftType.CITATION_ADDED,
                severity=DriftSeverity.MODERATE,
                previous_value=None,
                current_value=citation,
                change_description=f"New source cited: {citation}",
                affected_entity=citation,
                recommended_action="Evaluate if this source is relevant for your content strategy",
                baseline_date=baseline.snapshot_date,
                current_date=current.snapshot_date,
            )
            self.db.add(drift)
            drifts.append(drift)

        # Removed citations
        removed = baseline_citations - current_citations
        for citation in removed:
            drift = DriftRecord(
                project_id=current.project_id,
                keyword_id=current.keyword_id,
                baseline_snapshot_id=baseline.id,
                current_snapshot_id=current.id,
                provider=current.provider,
                drift_type=DriftType.CITATION_REMOVED,
                severity=DriftSeverity.MODERATE,
                previous_value=citation,
                current_value=None,
                change_description=f"Source no longer cited: {citation}",
                affected_entity=citation,
                recommended_action="If this was a target source, investigate why it was removed",
                baseline_date=baseline.snapshot_date,
                current_date=current.snapshot_date,
            )
            self.db.add(drift)
            drifts.append(drift)

        await self.db.flush()
        return drifts

    async def _detect_competitor_drift(
        self,
        current: ResponseSnapshot,
        baseline: ResponseSnapshot,
    ) -> List[DriftRecord]:
        """Detect competitor displacement events."""
        drifts = []

        current_competitors = current.competitor_positions or {}
        baseline_competitors = baseline.competitor_positions or {}

        # Check each competitor
        all_competitors = set(current_competitors.keys()) | set(baseline_competitors.keys())

        for competitor in all_competitors:
            curr_pos = current_competitors.get(competitor)
            base_pos = baseline_competitors.get(competitor)

            # Competitor appeared
            if curr_pos is not None and base_pos is None:
                # Check if they took our position
                if current.brand_position and curr_pos < current.brand_position:
                    drift = DriftRecord(
                        project_id=current.project_id,
                        keyword_id=current.keyword_id,
                        baseline_snapshot_id=baseline.id,
                        current_snapshot_id=current.id,
                        provider=current.provider,
                        drift_type=DriftType.COMPETITOR_DISPLACED_US,
                        severity=DriftSeverity.MAJOR,
                        previous_value=None,
                        current_value=str(curr_pos),
                        change_description=f"{competitor} appeared and is now ranked above us",
                        affected_entity=competitor,
                        recommended_action=f"Analyze {competitor}'s content strategy and strengthen differentiation",
                        baseline_date=baseline.snapshot_date,
                        current_date=current.snapshot_date,
                    )
                    self.db.add(drift)
                    drifts.append(drift)

            # Competitor disappeared and we improved
            elif curr_pos is None and base_pos is not None:
                if current.brand_mentioned and current.brand_position:
                    if baseline.brand_position is None or current.brand_position < baseline.brand_position:
                        drift = DriftRecord(
                            project_id=current.project_id,
                            keyword_id=current.keyword_id,
                            baseline_snapshot_id=baseline.id,
                            current_snapshot_id=current.id,
                            provider=current.provider,
                            drift_type=DriftType.WE_DISPLACED_COMPETITOR,
                            severity=DriftSeverity.MAJOR,
                            previous_value=str(base_pos),
                            current_value=None,
                            change_description=f"We displaced {competitor} in the response",
                            affected_entity=competitor,
                            recommended_action="Continue current strategy - it's working",
                            baseline_date=baseline.snapshot_date,
                            current_date=current.snapshot_date,
                        )
                        self.db.add(drift)
                        drifts.append(drift)

        await self.db.flush()
        return drifts

    async def _detect_sentiment_drift(
        self,
        current: ResponseSnapshot,
        baseline: ResponseSnapshot,
    ) -> Optional[DriftRecord]:
        """Detect changes in sentiment toward the brand."""
        if current.sentiment is None or baseline.sentiment is None:
            return None

        if current.sentiment == baseline.sentiment:
            return None

        # Define sentiment order
        sentiment_order = {
            SentimentPolarity.NEGATIVE: 0,
            SentimentPolarity.NEUTRAL: 1,
            SentimentPolarity.POSITIVE: 2,
        }

        curr_val = sentiment_order.get(current.sentiment, 1)
        base_val = sentiment_order.get(baseline.sentiment, 1)

        if curr_val > base_val:
            drift_type = DriftType.SENTIMENT_IMPROVED
            severity = DriftSeverity.MODERATE
            description = f"Sentiment improved from {baseline.sentiment.value} to {current.sentiment.value}"
            action = "Maintain positive trajectory"
        else:
            drift_type = DriftType.SENTIMENT_DECLINED
            severity = DriftSeverity.MAJOR
            description = f"Sentiment declined from {baseline.sentiment.value} to {current.sentiment.value}"
            action = "Investigate cause of negative sentiment shift"

        drift = DriftRecord(
            project_id=current.project_id,
            keyword_id=current.keyword_id,
            baseline_snapshot_id=baseline.id,
            current_snapshot_id=current.id,
            provider=current.provider,
            drift_type=drift_type,
            severity=severity,
            previous_value=baseline.sentiment.value,
            current_value=current.sentiment.value,
            change_description=description,
            recommended_action=action,
            baseline_date=baseline.snapshot_date,
            current_date=current.snapshot_date,
        )

        self.db.add(drift)
        await self.db.flush()
        return drift

    # =========================================================================
    # DRIFT QUERIES
    # =========================================================================

    async def get_recent_drifts(
        self,
        project_id: UUID,
        days: int = 7,
        severity: Optional[DriftSeverity] = None,
        drift_type: Optional[DriftType] = None,
        limit: int = 100,
    ) -> List[DriftRecord]:
        """Get recent drift records for a project."""
        start_date = datetime.utcnow() - timedelta(days=days)

        query = select(DriftRecord).where(
            and_(
                DriftRecord.project_id == project_id,
                DriftRecord.detected_at >= start_date,
            )
        )

        if severity:
            query = query.where(DriftRecord.severity == severity)
        if drift_type:
            query = query.where(DriftRecord.drift_type == drift_type)

        query = query.order_by(DriftRecord.detected_at.desc()).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_unalerted_drifts(
        self,
        project_id: UUID,
        min_severity: DriftSeverity = DriftSeverity.MODERATE,
    ) -> List[DriftRecord]:
        """Get drift records that haven't been alerted yet."""
        severity_order = {
            DriftSeverity.MINOR: 0,
            DriftSeverity.MODERATE: 1,
            DriftSeverity.MAJOR: 2,
            DriftSeverity.CRITICAL: 3,
        }
        min_level = severity_order.get(min_severity, 1)

        result = await self.db.execute(
            select(DriftRecord).where(
                and_(
                    DriftRecord.project_id == project_id,
                    DriftRecord.is_alerted == False,
                )
            ).order_by(DriftRecord.detected_at.desc())
        )
        drifts = list(result.scalars().all())

        # Filter by severity level
        return [
            d for d in drifts
            if severity_order.get(d.severity, 0) >= min_level
        ]

    async def mark_drift_alerted(
        self,
        drift_id: UUID,
    ) -> None:
        """Mark a drift record as alerted."""
        result = await self.db.execute(
            select(DriftRecord).where(DriftRecord.id == drift_id)
        )
        drift = result.scalar_one()
        drift.is_alerted = True
        drift.alerted_at = datetime.utcnow()
        await self.db.flush()

    async def get_drift_summary(
        self,
        project_id: UUID,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get a summary of drift activity for a project."""
        start_date = datetime.utcnow() - timedelta(days=days)

        # Count by type
        result = await self.db.execute(
            select(
                DriftRecord.drift_type,
                func.count(DriftRecord.id),
            )
            .where(
                and_(
                    DriftRecord.project_id == project_id,
                    DriftRecord.detected_at >= start_date,
                )
            )
            .group_by(DriftRecord.drift_type)
        )
        by_type = {row[0].value: row[1] for row in result.all()}

        # Count by severity
        result = await self.db.execute(
            select(
                DriftRecord.severity,
                func.count(DriftRecord.id),
            )
            .where(
                and_(
                    DriftRecord.project_id == project_id,
                    DriftRecord.detected_at >= start_date,
                )
            )
            .group_by(DriftRecord.severity)
        )
        by_severity = {row[0].value: row[1] for row in result.all()}

        # Count by provider
        result = await self.db.execute(
            select(
                DriftRecord.provider,
                func.count(DriftRecord.id),
            )
            .where(
                and_(
                    DriftRecord.project_id == project_id,
                    DriftRecord.detected_at >= start_date,
                )
            )
            .group_by(DriftRecord.provider)
        )
        by_provider = {row[0].value: row[1] for row in result.all()}

        # Total
        result = await self.db.execute(
            select(func.count(DriftRecord.id)).where(
                and_(
                    DriftRecord.project_id == project_id,
                    DriftRecord.detected_at >= start_date,
                )
            )
        )
        total = result.scalar()

        return {
            "period_days": days,
            "total_drifts": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_provider": by_provider,
        }

    # =========================================================================
    # TREND ANALYSIS
    # =========================================================================

    async def analyze_visibility_trend(
        self,
        project_id: UUID,
        keyword_id: UUID,
        provider: Optional[LLMProvider] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Analyze visibility score trend from snapshots."""
        snapshots = await self.get_snapshot_history(
            project_id, keyword_id, provider, days
        )

        if not snapshots:
            return {"error": "No snapshots available for analysis"}

        scores = [s.visibility_score for s in snapshots if s.visibility_score is not None]

        if len(scores) < 2:
            return {"error": "Insufficient data for trend analysis"}

        # Calculate trend
        first_half = scores[:len(scores)//2]
        second_half = scores[len(scores)//2:]

        avg_first = sum(first_half) / len(first_half)
        avg_second = sum(second_half) / len(second_half)

        trend = avg_second - avg_first

        if trend > 5:
            direction = "improving"
        elif trend < -5:
            direction = "declining"
        else:
            direction = "stable"

        return {
            "snapshots_analyzed": len(snapshots),
            "period_days": days,
            "current_score": scores[-1] if scores else None,
            "average_score": sum(scores) / len(scores),
            "min_score": min(scores),
            "max_score": max(scores),
            "trend": trend,
            "direction": direction,
            "data_points": [
                {
                    "date": s.snapshot_date.isoformat(),
                    "score": s.visibility_score,
                    "brand_mentioned": s.brand_mentioned,
                    "position": s.brand_position,
                }
                for s in snapshots
            ],
        }
