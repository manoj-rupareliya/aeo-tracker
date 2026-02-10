"""
llmrefs.com Database Models
PostgreSQL with SQLAlchemy ORM
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
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, backref

Base = declarative_base()


# ============================================================================
# ENUMS
# ============================================================================

class UserRole(str, PyEnum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class SubscriptionTier(str, PyEnum):
    FREE = "free"
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class IndustryCategory(str, PyEnum):
    TECHNOLOGY = "technology"
    ECOMMERCE = "ecommerce"
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    MARKETING = "marketing"
    LEGAL = "legal"
    REAL_ESTATE = "real_estate"
    TRAVEL = "travel"
    FOOD_BEVERAGE = "food_beverage"
    OTHER = "other"


class PromptType(str, PyEnum):
    INFORMATIONAL = "informational"  # "What is X?", "How does X work?"
    COMPARATIVE = "comparative"       # "X vs Y", "Best X for Y"
    RECOMMENDATION = "recommendation" # "What X should I use?", "Recommend X"


class LLMProvider(str, PyEnum):
    OPENAI = "openai"        # ChatGPT
    ANTHROPIC = "anthropic"  # Claude
    GOOGLE = "google"        # Gemini
    PERPLEXITY = "perplexity"


class LLMRunStatus(str, PyEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    EXECUTING = "executing"
    PARSING = "parsing"
    SCORING = "scoring"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


class SentimentPolarity(str, PyEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class SourceCategory(str, PyEnum):
    OFFICIAL_DOCS = "official_docs"
    BLOG = "blog"
    NEWS = "news"
    REVIEW_SITE = "review_site"
    FORUM = "forum"
    SOCIAL_MEDIA = "social_media"
    ACADEMIC = "academic"
    ECOMMERCE = "ecommerce"
    UNKNOWN = "unknown"


class JobPriority(str, PyEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# ============================================================================
# USER & AUTHENTICATION
# ============================================================================

class User(Base):
    """User account with multi-tenant support"""
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)

    # Subscription & Limits
    subscription_tier = Column(Enum(SubscriptionTier), default=SubscriptionTier.FREE, nullable=False)
    monthly_token_limit = Column(Integer, default=100000)  # Tokens per month
    tokens_used_this_month = Column(Integer, default=0)

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)

    # Relationships
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    api_keys = relationship("UserAPIKey", back_populates="user", cascade="all, delete-orphan")


class UserAPIKey(Base):
    """User's personal API keys for LLM providers (optional BYOK)"""
    __tablename__ = "user_api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(Enum(LLMProvider), nullable=False)
    encrypted_key = Column(Text, nullable=False)  # AES-256 encrypted
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="api_keys")

    __table_args__ = (
        UniqueConstraint('user_id', 'provider', name='uq_user_provider_key'),
    )


# ============================================================================
# PROJECT & BRAND MANAGEMENT
# ============================================================================

class Project(Base):
    """A tracking project for a specific brand/domain"""
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Primary domain being tracked
    domain = Column(String(255), nullable=False)

    # Industry for prompt context
    industry = Column(Enum(IndustryCategory), default=IndustryCategory.OTHER)

    # LLM configuration
    enabled_llms = Column(ARRAY(String), default=["openai", "anthropic", "google", "perplexity"])

    # Scheduling
    crawl_frequency_days = Column(Integer, default=7)  # Re-crawl every N days
    last_crawl_at = Column(DateTime)
    next_crawl_at = Column(DateTime)

    # Status
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="projects")
    brands = relationship("Brand", back_populates="project", cascade="all, delete-orphan")
    competitors = relationship("Competitor", back_populates="project", cascade="all, delete-orphan")
    keywords = relationship("Keyword", back_populates="project", cascade="all, delete-orphan")
    llm_runs = relationship("LLMRun", back_populates="project", cascade="all, delete-orphan")
    visibility_scores = relationship("VisibilityScore", back_populates="project", cascade="all, delete-orphan")


class Brand(Base):
    """Brand names to track (primary + aliases)"""
    __tablename__ = "brands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    is_primary = Column(Boolean, default=False)  # Primary brand name

    # Alternative spellings, abbreviations, etc.
    aliases = Column(ARRAY(String), default=[])

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="brands")

    __table_args__ = (
        Index('idx_brand_project_name', 'project_id', 'name'),
    )


class Competitor(Base):
    """Competitor brands to track for comparison"""
    __tablename__ = "competitors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    name = Column(String(255), nullable=False)
    domain = Column(String(255))  # Optional competitor domain
    aliases = Column(ARRAY(String), default=[])

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="competitors")


# ============================================================================
# KEYWORDS & PROMPTS
# ============================================================================

class Keyword(Base):
    """Keywords to query LLMs about"""
    __tablename__ = "keywords"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    keyword = Column(String(500), nullable=False)

    # Optional context for better prompt generation
    context = Column(Text)

    # Priority for crawling
    priority = Column(Enum(JobPriority), default=JobPriority.MEDIUM)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="keywords")
    prompts = relationship("Prompt", back_populates="keyword", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_keyword_project', 'project_id', 'keyword'),
    )


class PromptTemplate(Base):
    """Versioned prompt templates"""
    __tablename__ = "prompt_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    name = Column(String(255), nullable=False)
    prompt_type = Column(Enum(PromptType), nullable=False)

    # The template with placeholders: {keyword}, {brand}, {industry}, etc.
    template_text = Column(Text, nullable=False)

    # Semantic versioning
    version_major = Column(Integer, default=1, nullable=False)
    version_minor = Column(Integer, default=0, nullable=False)
    version_patch = Column(Integer, default=0, nullable=False)

    # Whether this is the active version for its type
    is_active = Column(Boolean, default=True)

    # Template metadata
    description = Column(Text)
    expected_output_format = Column(String(50))  # e.g., "paragraph", "list", "structured"

    created_at = Column(DateTime, default=datetime.utcnow)

    prompts = relationship("Prompt", back_populates="template")

    @property
    def version(self) -> str:
        return f"{self.version_major}.{self.version_minor}.{self.version_patch}"

    __table_args__ = (
        Index('idx_template_type_active', 'prompt_type', 'is_active'),
    )


class Prompt(Base):
    """Generated prompts from templates + keywords"""
    __tablename__ = "prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="CASCADE"), nullable=False)
    template_id = Column(UUID(as_uuid=True), ForeignKey("prompt_templates.id", ondelete="SET NULL"))

    prompt_type = Column(Enum(PromptType), nullable=False)

    # The actual generated prompt text
    prompt_text = Column(Text, nullable=False)

    # Hash for caching: SHA-256(prompt_text + template_version)
    prompt_hash = Column(String(64), nullable=False, index=True)

    # Context injected into prompt
    injected_context = Column(JSONB, default={})

    created_at = Column(DateTime, default=datetime.utcnow)

    keyword = relationship("Keyword", back_populates="prompts")
    template = relationship("PromptTemplate", back_populates="prompts")
    llm_runs = relationship("LLMRun", back_populates="prompt")

    __table_args__ = (
        Index('idx_prompt_hash', 'prompt_hash'),
    )


# ============================================================================
# LLM EXECUTION & RESPONSES
# ============================================================================

class LLMRun(Base):
    """A single LLM query execution"""
    __tablename__ = "llm_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    prompt_id = Column(UUID(as_uuid=True), ForeignKey("prompts.id", ondelete="SET NULL"))

    # LLM Configuration
    provider = Column(Enum(LLMProvider), nullable=False)
    model_name = Column(String(100), nullable=False)  # e.g., "gpt-4-turbo", "claude-3-opus"
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2000)

    # Execution Status
    status = Column(Enum(LLMRunStatus), default=LLMRunStatus.PENDING, nullable=False)
    priority = Column(Enum(JobPriority), default=JobPriority.MEDIUM)

    # Timing
    queued_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Cost tracking
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    estimated_cost_usd = Column(Numeric(10, 6))

    # Cache info
    cache_key = Column(String(64), index=True)  # SHA-256(prompt_hash + model + temp)
    is_cached_result = Column(Boolean, default=False)
    cache_expires_at = Column(DateTime)

    # Error handling
    retry_count = Column(Integer, default=0)
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="llm_runs")
    prompt = relationship("Prompt", back_populates="llm_runs")
    response = relationship("LLMResponse", back_populates="llm_run", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_run_project_status', 'project_id', 'status'),
        Index('idx_run_cache_key', 'cache_key'),
        Index('idx_run_queued', 'status', 'queued_at'),
    )


class LLMResponse(Base):
    """Raw LLM response storage - THE SOURCE OF TRUTH"""
    __tablename__ = "llm_responses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    llm_run_id = Column(UUID(as_uuid=True), ForeignKey("llm_runs.id", ondelete="CASCADE"), nullable=False, unique=True)

    # Raw response - NEVER MODIFY, this is the audit trail
    raw_response = Column(Text, nullable=False)

    # Response metadata from LLM
    response_metadata = Column(JSONB, default={})

    # Parsed/structured version (can be re-generated from raw)
    parsed_response = Column(JSONB, default={})

    # Fingerprint for change detection
    response_hash = Column(String(64), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    llm_run = relationship("LLMRun", back_populates="response")
    brand_mentions = relationship("BrandMention", back_populates="response", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="response", cascade="all, delete-orphan")


# ============================================================================
# RESPONSE ANALYSIS
# ============================================================================

class BrandMention(Base):
    """Detected brand mentions in LLM responses"""
    __tablename__ = "brand_mentions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    response_id = Column(UUID(as_uuid=True), ForeignKey("llm_responses.id", ondelete="CASCADE"), nullable=False)

    # What was mentioned
    mentioned_text = Column(String(500), nullable=False)  # Exact text found
    normalized_name = Column(String(255), nullable=False)  # Normalized brand name

    # Whose brand
    is_own_brand = Column(Boolean, default=False)  # Our tracked brand vs competitor
    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"))
    competitor_id = Column(UUID(as_uuid=True), ForeignKey("competitors.id", ondelete="SET NULL"))

    # Position & Context
    mention_position = Column(Integer, nullable=False)  # 1st, 2nd, 3rd, etc.
    character_offset = Column(Integer)  # Position in raw text
    context_snippet = Column(Text)  # Surrounding text

    # Match quality
    match_type = Column(String(20), nullable=False)  # "exact", "fuzzy", "alias"
    match_confidence = Column(Float, default=1.0)  # 0.0-1.0

    # Sentiment
    sentiment = Column(Enum(SentimentPolarity), default=SentimentPolarity.NEUTRAL)
    sentiment_score = Column(Float)  # -1.0 to 1.0

    created_at = Column(DateTime, default=datetime.utcnow)

    response = relationship("LLMResponse", back_populates="brand_mentions")
    brand = relationship("Brand", foreign_keys=[brand_id])
    competitor = relationship("Competitor", foreign_keys=[competitor_id])

    __table_args__ = (
        Index('idx_mention_response', 'response_id'),
        Index('idx_mention_brand', 'brand_id'),
        Index('idx_mention_competitor', 'competitor_id'),
    )


class CitationSource(Base):
    """Normalized citation sources (global, shared across projects)"""
    __tablename__ = "citation_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Normalized domain
    domain = Column(String(255), nullable=False, unique=True, index=True)

    # Categorization
    category = Column(Enum(SourceCategory), default=SourceCategory.UNKNOWN)

    # Metadata
    site_name = Column(String(255))
    description = Column(Text)

    # Authority metrics (can be populated via external APIs)
    domain_authority = Column(Integer)  # 0-100

    # Stats
    total_citations = Column(Integer, default=0)
    last_cited_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    citations = relationship("Citation", back_populates="source")


class Citation(Base):
    """Individual citations found in LLM responses"""
    __tablename__ = "citations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    response_id = Column(UUID(as_uuid=True), ForeignKey("llm_responses.id", ondelete="CASCADE"), nullable=False)
    source_id = Column(UUID(as_uuid=True), ForeignKey("citation_sources.id", ondelete="SET NULL"))

    # The actual URL cited
    cited_url = Column(Text, nullable=False)

    # Link text or context
    anchor_text = Column(Text)
    context_snippet = Column(Text)

    # Position in response
    citation_position = Column(Integer)  # Order of appearance

    # Validation
    is_valid_url = Column(Boolean)  # Syntax check
    is_accessible = Column(Boolean)  # HTTP check performed
    http_status_code = Column(Integer)
    is_hallucinated = Column(Boolean, default=False)  # URL doesn't exist

    # Last checked
    last_validated_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)

    response = relationship("LLMResponse", back_populates="citations")
    source = relationship("CitationSource", back_populates="citations")

    __table_args__ = (
        Index('idx_citation_response', 'response_id'),
        Index('idx_citation_source', 'source_id'),
    )


# ============================================================================
# VISIBILITY SCORING
# ============================================================================

class VisibilityScore(Base):
    """Calculated visibility scores with full explainability"""
    __tablename__ = "visibility_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    # Scope of this score
    llm_run_id = Column(UUID(as_uuid=True), ForeignKey("llm_runs.id", ondelete="SET NULL"))
    keyword_id = Column(UUID(as_uuid=True), ForeignKey("keywords.id", ondelete="SET NULL"))

    # Which LLM
    provider = Column(Enum(LLMProvider))

    # Score breakdown (all values 0-100)
    mention_score = Column(Float, default=0)         # Brand mentioned at all
    position_score = Column(Float, default=0)        # Position in response
    citation_score = Column(Float, default=0)        # Brand cited as source
    sentiment_score = Column(Float, default=0)       # Sentiment of mention
    competitor_delta = Column(Float, default=0)      # Relative to competitors

    # Final calculated score
    total_score = Column(Float, default=0, nullable=False)

    # LLM weight applied
    llm_weight = Column(Float, default=1.0)
    weighted_score = Column(Float, default=0)

    # Explanation (human-readable)
    score_explanation = Column(JSONB, default={})

    # Time dimension
    score_date = Column(DateTime, default=datetime.utcnow, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="visibility_scores")
    llm_run = relationship("LLMRun", foreign_keys=[llm_run_id])
    keyword = relationship("Keyword", foreign_keys=[keyword_id])

    __table_args__ = (
        Index('idx_score_project_date', 'project_id', 'score_date'),
        Index('idx_score_keyword', 'keyword_id', 'score_date'),
        Index('idx_score_provider', 'provider', 'score_date'),
    )


class AggregatedScore(Base):
    """Daily/weekly aggregated scores for trending"""
    __tablename__ = "aggregated_scores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    # Aggregation period
    period_type = Column(String(20), nullable=False)  # "daily", "weekly", "monthly"
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)

    # Aggregated metrics
    avg_visibility_score = Column(Float, default=0)
    avg_mention_score = Column(Float, default=0)
    avg_position_score = Column(Float, default=0)
    avg_citation_score = Column(Float, default=0)

    # Per-LLM breakdown
    scores_by_llm = Column(JSONB, default={})

    # Comparison
    score_delta_vs_previous = Column(Float)  # Change from previous period

    # Counts
    total_queries = Column(Integer, default=0)
    total_mentions = Column(Integer, default=0)
    total_citations = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_agg_project_period', 'project_id', 'period_type', 'period_start'),
        UniqueConstraint('project_id', 'period_type', 'period_start', name='uq_project_period'),
    )


# ============================================================================
# AUDIT & JOBS
# ============================================================================

class AuditLog(Base):
    """Audit trail for all significant actions"""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"))

    action = Column(String(100), nullable=False)  # e.g., "llm_query", "project_created"
    resource_type = Column(String(100))  # e.g., "LLMRun", "Project"
    resource_id = Column(UUID(as_uuid=True))

    details = Column(JSONB, default={})

    ip_address = Column(String(45))
    user_agent = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index('idx_audit_user', 'user_id', 'created_at'),
        Index('idx_audit_project', 'project_id', 'created_at'),
    )


class ScheduledJob(Base):
    """Scheduled crawl jobs"""
    __tablename__ = "scheduled_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)

    job_type = Column(String(50), nullable=False)  # "full_crawl", "keyword_crawl", "validate_citations"

    # Scheduling
    scheduled_for = Column(DateTime, nullable=False, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    status = Column(String(20), default="pending")  # pending, running, completed, failed

    # Results
    result_summary = Column(JSONB, default={})
    error_message = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_job_scheduled', 'status', 'scheduled_for'),
    )
