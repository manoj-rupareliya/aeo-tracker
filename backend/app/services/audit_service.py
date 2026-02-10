"""
Trust & Audit Layer Service
Provides complete provenance and auditability for all LLM insights
"""

import hashlib
from datetime import datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.models_v2 import (
    ExecutionLog, ResponseArchive, ParseLineage, InsightConfidence,
    ConfidenceLevel
)
from ..models.database import LLMProvider


class AuditService:
    """
    Service for the Trust & Audit Layer.
    Every insight must be traceable to raw data.
    """

    # Cost per 1K tokens by provider (approximate)
    TOKEN_COSTS = {
        LLMProvider.OPENAI: {"input": 0.003, "output": 0.006},
        LLMProvider.ANTHROPIC: {"input": 0.003, "output": 0.015},
        LLMProvider.GOOGLE: {"input": 0.00025, "output": 0.0005},
        LLMProvider.PERPLEXITY: {"input": 0.0007, "output": 0.0028},
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # EXECUTION LOGGING
    # =========================================================================

    async def log_execution(
        self,
        llm_run_id: UUID,
        project_id: UUID,
        prompt_text: str,
        provider: LLMProvider,
        model_name: str,
        temperature: float,
        max_tokens: int,
        execution_started_at: datetime,
        triggered_by: str = "user",
        template_version: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ExecutionLog:
        """
        Create an execution log entry at the start of an LLM call.
        Returns the log entry so it can be updated when execution completes.
        """
        prompt_hash = self._hash_prompt(prompt_text)

        log = ExecutionLog(
            llm_run_id=llm_run_id,
            project_id=project_id,
            prompt_text=prompt_text,
            prompt_hash=prompt_hash,
            template_version=template_version,
            provider=provider,
            model_name=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            execution_started_at=execution_started_at,
            triggered_by=triggered_by,
            request_id=request_id,
            was_cached=False,
        )

        self.db.add(log)
        await self.db.flush()
        return log

    async def complete_execution_log(
        self,
        log_id: UUID,
        execution_completed_at: datetime,
        prompt_tokens: int,
        completion_tokens: int,
        was_cached: bool = False,
        cache_key: Optional[str] = None,
        had_error: bool = False,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> ExecutionLog:
        """
        Update execution log when LLM call completes.
        """
        result = await self.db.execute(
            select(ExecutionLog).where(ExecutionLog.id == log_id)
        )
        log = result.scalar_one()

        log.execution_completed_at = execution_completed_at
        log.execution_duration_ms = int(
            (execution_completed_at - log.execution_started_at).total_seconds() * 1000
        )
        log.prompt_tokens = prompt_tokens
        log.completion_tokens = completion_tokens
        log.total_tokens = prompt_tokens + completion_tokens
        log.was_cached = was_cached
        log.cache_key = cache_key
        log.had_error = had_error
        log.error_type = error_type
        log.error_message = error_message

        # Calculate estimated cost
        if not was_cached and prompt_tokens and completion_tokens:
            log.estimated_cost_usd = self._calculate_cost(
                log.provider, prompt_tokens, completion_tokens
            )

        await self.db.flush()
        return log

    async def log_execution_error(
        self,
        log_id: UUID,
        error_type: str,
        error_message: str,
        retry_count: int = 0,
    ) -> None:
        """Log an execution error."""
        result = await self.db.execute(
            select(ExecutionLog).where(ExecutionLog.id == log_id)
        )
        log = result.scalar_one()

        log.had_error = True
        log.error_type = error_type
        log.error_message = error_message
        log.retry_count = retry_count
        log.execution_completed_at = datetime.utcnow()

        await self.db.flush()

    # =========================================================================
    # RESPONSE ARCHIVAL
    # =========================================================================

    async def archive_response(
        self,
        llm_run_id: UUID,
        execution_log_id: UUID,
        raw_response_text: str,
        finish_reason: Optional[str] = None,
        response_metadata: Optional[Dict[str, Any]] = None,
    ) -> ResponseArchive:
        """
        Archive the raw LLM response. This is immutable - never modified.
        """
        response_hash = self._hash_response(raw_response_text)
        word_count = len(raw_response_text.split())

        archive = ResponseArchive(
            llm_run_id=llm_run_id,
            execution_log_id=execution_log_id,
            raw_response_text=raw_response_text,
            response_hash=response_hash,
            content_length=len(raw_response_text),
            word_count=word_count,
            finish_reason=finish_reason,
            response_metadata=response_metadata or {},
        )

        self.db.add(archive)
        await self.db.flush()
        return archive

    async def get_archived_response(
        self,
        llm_run_id: UUID
    ) -> Optional[ResponseArchive]:
        """Retrieve archived response for an LLM run."""
        result = await self.db.execute(
            select(ResponseArchive).where(ResponseArchive.llm_run_id == llm_run_id)
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # PARSE LINEAGE
    # =========================================================================

    async def record_parse_lineage(
        self,
        response_archive_id: UUID,
        entity_type: str,
        entity_value: str,
        extraction_method: str,
        confidence: float,
        entity_id: Optional[UUID] = None,
        extraction_pattern: Optional[str] = None,
        extraction_version: Optional[str] = None,
        start_offset: Optional[int] = None,
        end_offset: Optional[int] = None,
        context_before: Optional[str] = None,
        context_after: Optional[str] = None,
        confidence_factors: Optional[Dict[str, Any]] = None,
    ) -> ParseLineage:
        """
        Record how an entity was extracted from a response.
        Provides full provenance for any parsed data.
        """
        lineage = ParseLineage(
            response_archive_id=response_archive_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_value=entity_value,
            extraction_method=extraction_method,
            extraction_pattern=extraction_pattern,
            extraction_version=extraction_version,
            start_offset=start_offset,
            end_offset=end_offset,
            context_before=context_before,
            context_after=context_after,
            confidence=confidence,
            confidence_factors=confidence_factors or {},
        )

        self.db.add(lineage)
        await self.db.flush()
        return lineage

    async def record_batch_lineage(
        self,
        response_archive_id: UUID,
        entities: List[Dict[str, Any]],
    ) -> List[ParseLineage]:
        """
        Record lineage for multiple extracted entities at once.
        More efficient for bulk parsing operations.
        """
        lineages = []
        for entity in entities:
            lineage = ParseLineage(
                response_archive_id=response_archive_id,
                entity_type=entity["entity_type"],
                entity_id=entity.get("entity_id"),
                entity_value=entity["entity_value"],
                extraction_method=entity["extraction_method"],
                extraction_pattern=entity.get("extraction_pattern"),
                extraction_version=entity.get("extraction_version"),
                start_offset=entity.get("start_offset"),
                end_offset=entity.get("end_offset"),
                context_before=entity.get("context_before"),
                context_after=entity.get("context_after"),
                confidence=entity["confidence"],
                confidence_factors=entity.get("confidence_factors", {}),
            )
            self.db.add(lineage)
            lineages.append(lineage)

        await self.db.flush()
        return lineages

    async def get_lineage_for_response(
        self,
        response_archive_id: UUID
    ) -> List[ParseLineage]:
        """Get all parse lineage records for a response."""
        result = await self.db.execute(
            select(ParseLineage)
            .where(ParseLineage.response_archive_id == response_archive_id)
            .order_by(ParseLineage.start_offset)
        )
        return list(result.scalars().all())

    async def get_lineage_for_entity(
        self,
        entity_type: str,
        entity_id: UUID
    ) -> Optional[ParseLineage]:
        """Get the lineage for a specific extracted entity."""
        result = await self.db.execute(
            select(ParseLineage).where(
                and_(
                    ParseLineage.entity_type == entity_type,
                    ParseLineage.entity_id == entity_id
                )
            )
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # INSIGHT CONFIDENCE
    # =========================================================================

    async def record_insight_confidence(
        self,
        project_id: UUID,
        insight_type: str,
        insight_id: UUID,
        confidence_score: float,
        data_completeness: Optional[float] = None,
        consistency_score: Optional[float] = None,
        sample_size: Optional[int] = None,
        recency_factor: Optional[float] = None,
        confidence_explanation: Optional[Dict[str, Any]] = None,
        caveats: Optional[List[str]] = None,
    ) -> InsightConfidence:
        """
        Record confidence assessment for an insight.
        Every surfaced insight should have a confidence record.
        """
        confidence_level = self._determine_confidence_level(confidence_score)
        requires_more_data = sample_size is not None and sample_size < 5

        insight_conf = InsightConfidence(
            project_id=project_id,
            insight_type=insight_type,
            insight_id=insight_id,
            confidence_level=confidence_level,
            confidence_score=confidence_score,
            data_completeness=data_completeness,
            consistency_score=consistency_score,
            sample_size=sample_size,
            recency_factor=recency_factor,
            confidence_explanation=confidence_explanation or {},
            caveats=caveats or [],
            requires_more_data=requires_more_data,
        )

        self.db.add(insight_conf)
        await self.db.flush()
        return insight_conf

    async def get_insight_confidence(
        self,
        insight_type: str,
        insight_id: UUID
    ) -> Optional[InsightConfidence]:
        """Get confidence record for a specific insight."""
        result = await self.db.execute(
            select(InsightConfidence).where(
                and_(
                    InsightConfidence.insight_type == insight_type,
                    InsightConfidence.insight_id == insight_id
                )
            )
        )
        return result.scalar_one_or_none()

    # =========================================================================
    # AUDIT TRAIL QUERIES
    # =========================================================================

    async def get_full_audit_trail(
        self,
        llm_run_id: UUID
    ) -> Dict[str, Any]:
        """
        Get the complete audit trail for an LLM run.
        Returns: raw response, parsed entities, lineage, and confidence.
        """
        # Get execution log
        exec_result = await self.db.execute(
            select(ExecutionLog).where(ExecutionLog.llm_run_id == llm_run_id)
        )
        execution_log = exec_result.scalar_one_or_none()

        # Get archived response
        archive = await self.get_archived_response(llm_run_id)

        # Get parse lineage if archive exists
        lineage = []
        if archive:
            lineage = await self.get_lineage_for_response(archive.id)

        return {
            "execution": {
                "id": str(execution_log.id) if execution_log else None,
                "prompt_text": execution_log.prompt_text if execution_log else None,
                "prompt_hash": execution_log.prompt_hash if execution_log else None,
                "provider": execution_log.provider.value if execution_log else None,
                "model_name": execution_log.model_name if execution_log else None,
                "temperature": execution_log.temperature if execution_log else None,
                "execution_started_at": (
                    execution_log.execution_started_at.isoformat()
                    if execution_log and execution_log.execution_started_at else None
                ),
                "execution_duration_ms": (
                    execution_log.execution_duration_ms if execution_log else None
                ),
                "total_tokens": execution_log.total_tokens if execution_log else None,
                "estimated_cost_usd": (
                    float(execution_log.estimated_cost_usd)
                    if execution_log and execution_log.estimated_cost_usd else None
                ),
                "was_cached": execution_log.was_cached if execution_log else None,
                "had_error": execution_log.had_error if execution_log else None,
            },
            "raw_response": {
                "id": str(archive.id) if archive else None,
                "response_text": archive.raw_response_text if archive else None,
                "response_hash": archive.response_hash if archive else None,
                "word_count": archive.word_count if archive else None,
                "archived_at": (
                    archive.archived_at.isoformat() if archive else None
                ),
            },
            "parsed_entities": [
                {
                    "entity_type": l.entity_type,
                    "entity_value": l.entity_value,
                    "extraction_method": l.extraction_method,
                    "confidence": l.confidence,
                    "position": {
                        "start": l.start_offset,
                        "end": l.end_offset,
                    } if l.start_offset is not None else None,
                    "context": {
                        "before": l.context_before,
                        "after": l.context_after,
                    } if l.context_before or l.context_after else None,
                }
                for l in lineage
            ],
            "extraction_summary": {
                "total_entities": len(lineage),
                "entity_types": list(set(l.entity_type for l in lineage)),
                "avg_confidence": (
                    sum(l.confidence for l in lineage) / len(lineage)
                    if lineage else None
                ),
            },
        }

    async def get_execution_logs_for_project(
        self,
        project_id: UUID,
        limit: int = 100,
        offset: int = 0,
        include_errors: bool = True,
    ) -> List[ExecutionLog]:
        """Get execution logs for a project."""
        query = (
            select(ExecutionLog)
            .where(ExecutionLog.project_id == project_id)
        )

        if not include_errors:
            query = query.where(ExecutionLog.had_error == False)

        query = query.order_by(ExecutionLog.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # HELPER METHODS
    # =========================================================================

    def _hash_prompt(self, prompt: str) -> str:
        """Create a hash of the prompt for caching and deduplication."""
        return hashlib.sha256(prompt.encode()).hexdigest()

    def _hash_response(self, response: str) -> str:
        """Create a hash of the response for fingerprinting."""
        return hashlib.sha256(response.encode()).hexdigest()

    def _calculate_cost(
        self,
        provider: LLMProvider,
        prompt_tokens: int,
        completion_tokens: int
    ) -> Decimal:
        """Calculate the estimated cost of an LLM call."""
        costs = self.TOKEN_COSTS.get(provider, {"input": 0.003, "output": 0.006})
        input_cost = (prompt_tokens / 1000) * costs["input"]
        output_cost = (completion_tokens / 1000) * costs["output"]
        return Decimal(str(round(input_cost + output_cost, 6)))

    def _determine_confidence_level(self, score: float) -> ConfidenceLevel:
        """Determine the confidence level based on score."""
        if score >= 0.9:
            return ConfidenceLevel.HIGH
        elif score >= 0.7:
            return ConfidenceLevel.MEDIUM
        elif score >= 0.5:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.UNCERTAIN
