"""
Configuration management for llmscm.com
Environment-based settings with secure defaults
"""

from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "llmscm"
    APP_ENV: str = "development"  # development, staging, production
    DEBUG: bool = False
    API_VERSION: str = "v1"
    SECRET_KEY: str  # Required - no default for security

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 4

    # Database
    DATABASE_URL: str  # Required
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 604800  # 7 days in seconds

    # JWT Auth
    JWT_SECRET_KEY: str  # Required
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # LLM Provider API Keys (platform-level, can be overridden by user BYOK)
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    PERPLEXITY_API_KEY: Optional[str] = None

    # SERP API Keys (for Google AI Overview tracking)
    SERPER_API_KEY: Optional[str] = None  # serper.dev API key

    # LLM Default Models
    OPENAI_DEFAULT_MODEL: str = "gpt-4-turbo"
    ANTHROPIC_DEFAULT_MODEL: str = "claude-3-opus-20240229"
    GOOGLE_DEFAULT_MODEL: str = "gemini-1.5-pro"
    PERPLEXITY_DEFAULT_MODEL: str = "llama-3.1-sonar-large-128k-online"

    # LLM Execution Settings
    LLM_DEFAULT_TEMPERATURE: float = 0.7
    LLM_DEFAULT_MAX_TOKENS: int = 2000
    LLM_REQUEST_TIMEOUT: int = 60  # seconds
    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_DELAY: int = 2  # seconds

    # LLM Cost per 1K tokens (for estimation)
    OPENAI_COST_INPUT_PER_1K: float = 0.01
    OPENAI_COST_OUTPUT_PER_1K: float = 0.03
    ANTHROPIC_COST_INPUT_PER_1K: float = 0.015
    ANTHROPIC_COST_OUTPUT_PER_1K: float = 0.075
    GOOGLE_COST_INPUT_PER_1K: float = 0.00125
    GOOGLE_COST_OUTPUT_PER_1K: float = 0.005
    PERPLEXITY_COST_INPUT_PER_1K: float = 0.001
    PERPLEXITY_COST_OUTPUT_PER_1K: float = 0.001

    # LLM Weights for Scoring
    LLM_WEIGHT_OPENAI: float = 1.0
    LLM_WEIGHT_ANTHROPIC: float = 0.9
    LLM_WEIGHT_GOOGLE: float = 0.8
    LLM_WEIGHT_PERPLEXITY: float = 1.1

    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    RATE_LIMIT_LLM_CALLS_PER_MINUTE: int = 10

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Encryption (for user API keys)
    ENCRYPTION_KEY: str  # Required - 32 bytes base64 encoded

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # Citation Validation
    CITATION_VALIDATION_TIMEOUT: int = 10  # seconds
    CITATION_VALIDATION_BATCH_SIZE: int = 10

    # Scoring Thresholds
    SCORE_MENTION_BASE: int = 30
    SCORE_TOP3_BONUS: int = 20
    SCORE_CITATION_BONUS: int = 15
    SCORE_POSITIVE_SENTIMENT: int = 10
    SCORE_COMPETITOR_BEFORE_PENALTY: int = 5
    SCORE_NOT_MENTIONED_PENALTY: int = 10

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings loader"""
    return Settings()


# Scoring weights configuration
VISIBILITY_SCORE_WEIGHTS = {
    "mention_present": 30,
    "top_3_position": 20,
    "citation_present": 15,
    "positive_sentiment": 10,
    "competitor_before_penalty": -5,
    "not_mentioned_penalty": -10,
}

LLM_MARKET_WEIGHTS = {
    "openai": 1.0,      # Market leader
    "anthropic": 0.9,   # Growing adoption
    "google": 0.8,      # Newer entrant
    "perplexity": 1.1,  # Citation-focused, high value for GEO
}

# Default prompt template versions
DEFAULT_TEMPLATE_VERSION = "1.0.0"

# Industry-specific context hints
INDUSTRY_CONTEXT = {
    "technology": "software, SaaS, tech products, APIs, development tools",
    "ecommerce": "online shopping, retail, products, marketplace",
    "finance": "banking, fintech, investments, financial services",
    "healthcare": "medical, health tech, wellness, patient care",
    "education": "learning, EdTech, courses, training",
    "marketing": "advertising, SEO, content, digital marketing",
    "legal": "law, compliance, legal services, contracts",
    "real_estate": "property, housing, real estate services",
    "travel": "tourism, hospitality, bookings, travel services",
    "food_beverage": "restaurants, food delivery, F&B industry",
    "other": "general business",
}
