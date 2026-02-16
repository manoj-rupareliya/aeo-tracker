"""
llmscm.com V2 - Extended Database Models
New tables for Trust & Audit, Drift Detection, Preference Graph, GEO Recommendations, SAIV
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import Optional, List
from uuid import uuid4

from sqlalchemy import (
    Column, String, Text, Integer, Float, Boolean, DateTime,
    ForeignKey, Enum, JSON, Numeric, Index, UniqueConstraint,
    CheckConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship

from .database import Base, LLMProvider, SourceCategory, SentimentPolarity


# ============================================================================
# NEW ENUMS FOR V2
# ============================================================================

class DriftSeverity(str, PyEnum):
    """Severity of detected drift"""
    MINOR = "minor"          # Small position changes
    MODERATE = "moderate"    # Notable visibility changes
    MAJOR = "major"          # Significant loss/gain
    CRITICAL = "critical"    # Complete appearance/disappearance


class DriftType(str, PyEnum):
    """Types of drift that can be detected"""
    BRAND_APPEARED = "brand_appeared"
    BRAND_DISAPPEARED = "brand_disappeared"
    POSITION_IMPROVED = "position_improved"
    POSITION_DECLINED = "position_declined"
    CITATION_ADDED = "citation_added"
    CITATION_REMOVED = "citation_removed"
    COMPETITOR_DISPLACED_US = "competitor_displaced_us"
    WE_DISPLACED_COMPETITOR = "we_displaced_competitor"
    SENTIMENT_IMPROVED = "sentiment_improved"
    SENTIMENT_DECLINED = "sentiment_declined"
    SOURCE_REPLACED = "source_replaced"


class RecommendationType(str, PyEnum):
    """Types of GEO recommendations"""
    GET_LISTED = "get_listed"            # Get listed on a source
    CREATE_CONTENT = "create_content"    # Create specific content type
    IMPROVE_PRESENCE = "improve_presence" # Enhance existing presence
    TARGET_KEYWORD = "target_keyword"    # Focus on specific keyword
    COMPETITOR_GAP = "competitor_gap"    # Address competitor advantage


class ConfidenceLevel(str, PyEnum):
    """Confidence levels for insights"""
    HIGH = "high"        # 90%+ confidence
    MEDIUM = "medium"    # 70-90% confidence
    LOW = "low"          # 50-70% confidence
    UNCERTAIN = "uncertain"  # <50% confidence


class GraphNodeType(str, PyEnum):
    """Types of nodes in preference graph"""
    LLM = "llm"
    DOMAIN = "domain"
    BRAND = "brand"
    KEYWORD = "keyword"


class GraphEdgeType(str, PyEnum):
    """Types of edges in preference graph"""
    CITES = "cites"              # LLM → Domain
    MENTIONS = "mentions"        # LLM → Brand
    ASSOCIATED = "associated"    # Domain → Brand
    RELATED = "related"          # Keyword → Keyword


# ============================================================================
# TRUST & AUDIT LAYER
# ============================================================================

class ExecutionLog(Base):
    """Complete record of every LLM execution for audit"""
    __tablename__ = "execution_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    llm_run_id = Column(UUID(as_uuid=True), ForeignKey("llm_runs.id", ondelete="CASCADE"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    # Execution context
    prompt_text = Column(Text, nullable=False)
    prompt_hash = Column(String(64), nullable=False)
    template_version = Column(String(20))

    # LLM configuration at execution time
    provider = Column(Enum(LLMProvider), nullable=False)
    model_name = Column(String(100), nullable=False)
    temperature = Column(Float, nullable=False)
    max_tokens = Column(Integer, nullable=False)

    # Timing
    execution_started_at = Column(DateTime, nullable=False)
    execution_completed_at = Column(DateTime)
    execution_duration_ms = Column(Integer)

    # Token usage
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    total_tokens = Column(Integer)

    # Cost
    estimated_cost_usd = Column(Numeric(10, 6))

    # Cache status
    was_cached = Column(Boolean, default=False)
    cache_key = Column(String(64))

    # Error tracking
    had_error = Column(Boolean, default=False)
    error_type = Column(String(100))
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)

    # Request metadata
    request_id = Column(String(64))  # For tracing
    user_agent = Column(Text)
    triggered_by = Column(String(50))  # "user", "schedule", "retry"

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_exec_log_project', 'project_id', 'created_at'),
        Index('idx_exec_log_run', 'llm_run_id'),
        Index('idx_exec_log_prompt_hash', 'prompt_hash'),
    )


class ResponseArchive(Base):
    """Immutable archive of raw LLM responses - never modified"""
    __tablename__ = "response_archives"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    llm_run_id = Column(UUID(as_uuid=True), ForeignKey("llm_runs.id", ondelete="CASCADE"), nullable=False)
    execution_log_id = Column(UUID(as_uuid=True), ForeignKey("execution_logs.id", ondelete="SET NULL"))

    # Raw response - THE IMMUTABLE TRUTH
    raw_response_text = Column(Text, nullable=False)

    # Response fingerprint
    response_hash = Column(String(64), nullable=False, index=True)
    content_length = Column(Integer, nullable=False)
    word_count = Column(Integer)

    # Metadata from LLM
    finish_reason = Column(String(50))
    response_metadata = Column(JSONB, default={})

    # Archive timestamp
    archived_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_archive_run', 'llm_run_id'),
        Index('idx_archive_hash', 'response_hash'),
    )


class ParseLineage(Base):
    """Records how each entity was extracted - full provenance"""
    __tablename__ = "parse_lineage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    response_archive_id = Column(UUID(as_uuid=True), ForeignKey("response_archives.id", ondelete="CASCADE"), nullable=False)

    # What was extracted
    entity_type = Column(String(50), nullable=False)  # "brand_mention", "citation", "sentiment"
    entity_id = Column(UUID(as_uuid=True))  # Reference to the extracted entity
    entity_value = Column(Text, nullable=False)  # The extracted value

    # How it was extracted
    extraction_method = Column(String(50), nullable=False)  # "exact_match", "fuzzy_match", "regex", "nlp"
    extraction_pattern = Column(Text)  # The pattern/rule used
    extraction_version = Column(String(20))  # Version of extraction logic

    # Where in the response
    start_offset = Column(Integer)
    end_offset = Column(Integer)
    context_before = Column(Text)  # 100 chars before
    context_after = Column(Text)   # 100 chars after

    # Quality indicators
    confidence = Column(Float, nullable=False)  # 0.0-1.0
    confidence_factors = Column(JSONB, default={})  # What contributed to confidence

    # Processing timestamp
    extracted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_lineage_archive', 'response_archive_id'),
        Index('idx_lineage_entity', 'entity_type', 'entity_id'),
    )


class InsightConfidence(Base):
    """Confidence scoring for every insight we surface"""
    __tablename__ = "insight_confidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    # What insight this refers to
    insight_type = Column(String(50), nullable=False)  # "visibility_score", "drift", "recommendation"
    insight_id = Column(UUID(as_uuid=True), nullable=False)

    # Confidence assessment
    confidence_level = Column(Enum(ConfidenceLevel), nullable=False)
    confidence_score = Column(Float, nullable=False)  # 0.0-1.0

    # Factors contributing to confidence
    data_completeness = Column(Float)  # How much data we had
    consistency_score = Column(Float)  # How consistent across runs
    sample_size = Column(Integer)       # Number of data points
    recency_factor = Column(Float)      # How recent the data is

    # Explanation
    confidence_explanation = Column(JSONB, default={})

    # Warnings/caveats
    caveats = Column(ARRAY(String), default=[])
    requires_more_data = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_confidence_project', 'project_id'),
        Index('idx_confidence_insight', 'insight_type', 'insight_id'),
    )


# ============================================================================
# CHANGE & DRIFT DETECTION
# ============================================================================

class ResponseSnapshot(Base):
    """Point-in-time snapshot for comparison"""
    __tablename__ = "response_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    prompt_hash = Column(String(64), nullable=False)

    # Snapshot for each LLM
    provider = Column(Enum(LLMProvider), nullable=False)
    llm_run_id = Column(UUID(as_uuid=True), ForeignKey("llm_runs.id", ondelete="SET NULL"))

    # Snapshot data (denormalized for fast comparison)
    response_hash = Column(String(64), nullable=False)
    brand_mentioned = Column(Boolean, default=False)
    brand_position = Column(Integer)  # Position if mentioned
    competitor_positions = Column(JSONB, default={})  # {competitor_name: position}
    citations = Column(ARRAY(String), default=[])  # List of cited domains
    sentiment = Column(Enum(SentimentPolarity))
    visibility_score = Column(Float)

    # Snapshot metadata
    snapshot_date = Column(DateTime, nullable=False)
    is_baseline = Column(Boolean, default=False)  # First snapshot for this combo

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index('idx_snapshot_project_keyword', 'project_id', 'keyword_id', 'provider'),
        Index('idx_snapshot_date', 'snapshot_date'),
        Index('idx_snapshot_prompt', 'prompt_hash', 'provider', 'snapshot_date'),
    )


class DriftRecord(Base):
    """Records detected changes between snapshots"""
    __tablename__ = "drift_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="CASCADE"))

    # Which snapshots are being compared
    baseline_snapshot_id = Column(UUID(as_uuid=True), ForeignKey("response_snapshots.id", ondelete="SET NULL"))
    current_snapshot_id = Column(UUID(as_uuid=True), ForeignKey("response_snapshots.id", ondelete="SET NULL"))

    # Drift details
    provider = Column(Enum(LLMProvider), nullable=False)
    drift_type = Column(Enum(DriftType), nullable=False)
    severity = Column(Enum(DriftSeverity), nullable=False)

    # What changed
    previous_value = Column(Text)
    current_value = Column(Text)
    change_description = Column(Text, nullable=False)

    # Quantified change
    score_delta = Column(Float)  # Change in visibility score
    position_delta = Column(Integer)  # Change in position

    # Context
    affected_entity = Column(String(255))  # Brand/competitor/source affected
    related_entities = Column(ARRAY(String), default=[])

    # Analysis
    probable_cause = Column(Text)  # Our best guess at why this happened
    recommended_action = Column(Text)

    # Alert status
    is_alerted = Column(Boolean, default=False)
    alerted_at = Column(DateTime)

    # Timestamps
    detected_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    baseline_date = Column(DateTime, nullable=False)
    current_date = Column(DateTime, nullable=False)

    __table_args__ = (
        Index('idx_drift_project', 'project_id', 'detected_at'),
        Index('idx_drift_severity', 'severity', 'detected_at'),
        Index('idx_drift_type', 'drift_type', 'detected_at'),
    )


# ============================================================================
# LLM PREFERENCE GRAPH
# ============================================================================

class PreferenceGraphNode(Base):
    """Nodes in the preference graph"""
    __tablename__ = "preference_graph_nodes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    node_type = Column(Enum(GraphNodeType), nullable=False)
    node_identifier = Column(String(255), nullable=False)  # domain, brand name, llm name
    display_name = Column(String(255))

    # Node properties
    properties = Column(JSONB, default={})

    # Computed metrics (updated periodically)
    authority_score = Column(Float, default=0)  # For domains
    persistence_score = Column(Float, default=0)  # For brands
    citation_count = Column(Integer, default=0)
    mention_count = Column(Integer, default=0)

    # Project scoping (null for global nodes like LLMs)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('node_type', 'node_identifier', 'project_id', name='uq_node_identity'),
        Index('idx_node_type', 'node_type'),
        Index('idx_node_project', 'project_id'),
    )


class PreferenceGraphEdge(Base):
    """Edges representing relationships in the preference graph"""
    __tablename__ = "preference_graph_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Edge endpoints
    source_node_id = Column(UUID(as_uuid=True), ForeignKey("preference_graph_nodes.id", ondelete="CASCADE"), nullable=False)
    target_node_id = Column(UUID(as_uuid=True), ForeignKey("preference_graph_nodes.id", ondelete="CASCADE"), nullable=False)

    edge_type = Column(Enum(GraphEdgeType), nullable=False)

    # Edge weight and metrics
    weight = Column(Float, default=1.0)  # Strength of relationship
    frequency = Column(Integer, default=1)  # How often this relationship appears
    recency_score = Column(Float, default=1.0)  # Decays over time

    # Context
    first_observed = Column(DateTime, default=datetime.utcnow)
    last_observed = Column(DateTime, default=datetime.utcnow)
    observation_count = Column(Integer, default=1)

    # Additional properties
    properties = Column(JSONB, default={})

    # Project scoping
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"))

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source_node = relationship("PreferenceGraphNode", foreign_keys=[source_node_id])
    target_node = relationship("PreferenceGraphNode", foreign_keys=[target_node_id])

    __table_args__ = (
        UniqueConstraint('source_node_id', 'target_node_id', 'edge_type', name='uq_edge_identity'),
        Index('idx_edge_source', 'source_node_id'),
        Index('idx_edge_target', 'target_node_id'),
        Index('idx_edge_type', 'edge_type'),
        Index('idx_edge_project', 'project_id'),
    )


class SourceAuthority(Base):
    """LLM-specific authority scores for sources"""
    __tablename__ = "source_authority"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    source_id = Column(UUID(as_uuid=True), ForeignKey("citation_sources.id", ondelete="CASCADE"), nullable=False)
    provider = Column(Enum(LLMProvider), nullable=False)

    # Authority metrics per LLM
    citation_count = Column(Integer, default=0)
    citation_frequency = Column(Float, default=0)  # Citations per 100 queries
    position_avg = Column(Float)  # Average position when cited
    recency_weighted_score = Column(Float, default=0)

    # Comparison
    relative_authority = Column(Float)  # Compared to other sources in same LLM

    # Category preferences
    category_affinity = Column(JSONB, default={})  # Which categories this source is cited for

    # Time-based metrics
    first_citation = Column(DateTime)
    last_citation = Column(DateTime)
    citation_trend = Column(String(20))  # "increasing", "stable", "decreasing"

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('source_id', 'provider', name='uq_source_llm_authority'),
        Index('idx_authority_source', 'source_id'),
        Index('idx_authority_provider', 'provider'),
    )


class LLMBehaviorProfile(Base):
    """Profile of how each LLM behaves"""
    __tablename__ = "llm_behavior_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    provider = Column(Enum(LLMProvider), nullable=False, unique=True)

    # Citation behavior
    avg_citations_per_response = Column(Float)
    citation_source_diversity = Column(Float)  # How varied the sources are
    preferred_source_categories = Column(JSONB, default={})  # {category: frequency}

    # Brand mention behavior
    avg_brands_mentioned = Column(Float)
    brand_mention_position_dist = Column(JSONB, default={})  # Distribution of positions

    # Content style
    avg_response_length = Column(Integer)
    list_format_frequency = Column(Float)  # How often uses lists
    comparison_frequency = Column(Float)  # How often compares brands

    # Consistency
    response_consistency_score = Column(Float)  # Same prompt, same response?

    # Sample size
    total_runs_analyzed = Column(Integer, default=0)
    analysis_period_days = Column(Integer)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# GEO RECOMMENDATION ENGINE
# ============================================================================

class GEORecommendation(Base):
    """Actionable GEO recommendations based on observed behavior"""
    __tablename__ = "geo_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    # Recommendation type and target
    recommendation_type = Column(Enum(RecommendationType), nullable=False)
    target_keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="SET NULL"))
    target_provider = Column(Enum(LLMProvider))  # Specific LLM or null for all

    # The recommendation
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    action_items = Column(ARRAY(String), default=[])

    # Evidence
    evidence_summary = Column(Text, nullable=False)
    supporting_data = Column(JSONB, default={})

    # Related entities
    target_sources = Column(ARRAY(String), default=[])  # Domains to target
    competitor_context = Column(JSONB, default={})  # Competitor activity

    # Priority and confidence
    priority_score = Column(Float, nullable=False)  # 0-100
    confidence = Column(Enum(ConfidenceLevel), nullable=False)
    confidence_score = Column(Float, nullable=False)

    # Impact estimation
    potential_visibility_gain = Column(Float)  # Estimated score improvement
    effort_level = Column(String(20))  # "low", "medium", "high"

    # Status tracking
    is_dismissed = Column(Boolean, default=False)
    is_completed = Column(Boolean, default=False)
    completed_at = Column(DateTime)

    # Validity
    valid_until = Column(DateTime)  # Recommendations can expire
    last_validated = Column(DateTime, default=datetime.utcnow)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_rec_project', 'project_id', 'created_at'),
        Index('idx_rec_type', 'recommendation_type'),
        Index('idx_rec_priority', 'priority_score'),
    )


class GapAnalysis(Base):
    """Analysis of where brand is absent"""
    __tablename__ = "gap_analyses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)

    # Analysis scope
    provider = Column(Enum(LLMProvider))  # Null for aggregate
    analysis_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Gap metrics
    brand_absent_rate = Column(Float, nullable=False)  # % of queries where brand missing
    competitor_present_rate = Column(Float)  # % where competitors appear

    # Source analysis
    sources_cited_when_absent = Column(JSONB, default={})  # {source: count}
    competitor_sources = Column(JSONB, default={})  # Sources that only cite competitors

    # Pattern analysis
    common_patterns = Column(JSONB, default={})  # What patterns lead to absence

    # Opportunities
    opportunity_score = Column(Float)  # How actionable is this gap
    suggested_actions = Column(ARRAY(String), default=[])

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_gap_project_keyword', 'project_id', 'keyword_id'),
        Index('idx_gap_date', 'analysis_date'),
    )


# ============================================================================
# SHARE OF AI VOICE (SAIV)
# ============================================================================

class SAIVSnapshot(Base):
    """Point-in-time SAIV calculation"""
    __tablename__ = "saiv_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    # Scope
    snapshot_date = Column(DateTime, nullable=False)
    period_type = Column(String(20), nullable=False)  # "daily", "weekly", "monthly"

    # Overall SAIV
    overall_saiv = Column(Float, nullable=False)  # 0-100%
    total_brand_mentions = Column(Integer, nullable=False)
    total_entity_mentions = Column(Integer, nullable=False)

    # LLM-specific SAIV
    saiv_by_llm = Column(JSONB, default={})  # {provider: saiv_value}

    # Keyword cluster SAIV
    saiv_by_keyword_cluster = Column(JSONB, default={})  # {cluster: saiv_value}

    # Competitor SAIV for comparison
    competitor_saiv = Column(JSONB, default={})  # {competitor: saiv_value}

    # Change metrics
    saiv_delta = Column(Float)  # Change from previous period
    trend_direction = Column(String(20))  # "up", "down", "stable"

    # Calculation metadata
    runs_analyzed = Column(Integer, nullable=False)
    calculation_method = Column(String(50), default="standard")

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_saiv_project_date', 'project_id', 'snapshot_date'),
        UniqueConstraint('project_id', 'snapshot_date', 'period_type', name='uq_saiv_snapshot'),
    )


class SAIVBreakdown(Base):
    """Detailed SAIV breakdown by dimension"""
    __tablename__ = "saiv_breakdowns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    saiv_snapshot_id = Column(UUID(as_uuid=True), ForeignKey("saiv_snapshots.id", ondelete="CASCADE"), nullable=False)

    # Breakdown dimension
    dimension_type = Column(String(50), nullable=False)  # "llm", "keyword", "prompt_type"
    dimension_value = Column(String(255), nullable=False)

    # SAIV for this dimension
    saiv_value = Column(Float, nullable=False)
    brand_mentions = Column(Integer, nullable=False)
    total_mentions = Column(Integer, nullable=False)

    # Context
    runs_analyzed = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_saiv_breakdown_snapshot', 'saiv_snapshot_id'),
        Index('idx_saiv_breakdown_dimension', 'dimension_type', 'dimension_value'),
    )


# ============================================================================
# COST & PERFORMANCE GOVERNANCE
# ============================================================================

class CostBudget(Base):
    """Budget controls for projects"""
    __tablename__ = "cost_budgets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Budget limits
    daily_token_limit = Column(Integer)
    daily_cost_limit_usd = Column(Numeric(10, 2))
    monthly_token_limit = Column(Integer)
    monthly_cost_limit_usd = Column(Numeric(10, 2))

    # Current usage
    tokens_used_today = Column(Integer, default=0)
    cost_today_usd = Column(Numeric(10, 2), default=0)
    tokens_used_this_month = Column(Integer, default=0)
    cost_this_month_usd = Column(Numeric(10, 2), default=0)

    # Status
    is_paused = Column(Boolean, default=False)  # Paused due to budget
    paused_at = Column(DateTime)
    pause_reason = Column(String(255))

    # Reset tracking
    last_daily_reset = Column(DateTime)
    last_monthly_reset = Column(DateTime)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RateLimitState(Base):
    """Track rate limits per provider"""
    __tablename__ = "rate_limit_states"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    provider = Column(Enum(LLMProvider), nullable=False)

    # Current state
    requests_this_minute = Column(Integer, default=0)
    requests_this_hour = Column(Integer, default=0)
    tokens_this_minute = Column(Integer, default=0)

    # Limits (can be customized per project)
    requests_per_minute_limit = Column(Integer, default=10)
    requests_per_hour_limit = Column(Integer, default=100)
    tokens_per_minute_limit = Column(Integer, default=40000)

    # Backoff state
    is_rate_limited = Column(Boolean, default=False)
    rate_limited_until = Column(DateTime)
    consecutive_429s = Column(Integer, default=0)

    # Reset tracking
    minute_window_start = Column(DateTime)
    hour_window_start = Column(DateTime)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('project_id', 'provider', name='uq_rate_limit_project_provider'),
    )


class CacheMetrics(Base):
    """Track cache effectiveness"""
    __tablename__ = "cache_metrics"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    # Time period
    date = Column(DateTime, nullable=False)

    # Hit/miss metrics
    cache_hits = Column(Integer, default=0)
    cache_misses = Column(Integer, default=0)
    hit_rate = Column(Float)

    # Savings
    tokens_saved = Column(Integer, default=0)
    estimated_cost_saved_usd = Column(Numeric(10, 4), default=0)

    # Cache inventory
    cached_responses_count = Column(Integer, default=0)
    cache_size_mb = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('project_id', 'date', name='uq_cache_metrics_project_date'),
    )
