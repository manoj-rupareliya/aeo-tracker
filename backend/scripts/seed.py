"""
Database Seed Script
Creates sample data for development and testing
"""

import asyncio
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
import random

# Add parent directory to path
sys.path.insert(0, str(__file__).rsplit("/", 2)[0])

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Base, User, Project, Brand, Competitor, Keyword, PromptTemplate,
    Prompt, LLMRun, LLMResponse, BrandMention, Citation, CitationSource,
    VisibilityScore, AggregatedScore, PromptType, LLMProvider,
    LLMRunStatus, SentimentPolarity, SourceCategory, IndustryCategory
)
from app.utils.security import hash_password, generate_prompt_hash, generate_response_hash

settings = get_settings()


def create_sample_data(db: Session):
    """Create all sample data"""
    print("Creating sample data...")

    # Create user
    user = User(
        id=uuid4(),
        email="demo@llmrefs.com",
        password_hash=hash_password("Demo1234!"),
        full_name="Demo User",
        subscription_tier="professional",
        monthly_token_limit=500000,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    print(f"  Created user: {user.email}")

    # Create project
    project = Project(
        id=uuid4(),
        owner_id=user.id,
        name="Acme Analytics",
        description="Track visibility for our analytics platform",
        domain="acme-analytics.com",
        industry=IndustryCategory.TECHNOLOGY,
        enabled_llms=["openai", "anthropic", "google", "perplexity"],
        crawl_frequency_days=7,
        last_crawl_at=datetime.utcnow() - timedelta(days=1),
        next_crawl_at=datetime.utcnow() + timedelta(days=6),
        is_active=True,
    )
    db.add(project)
    db.flush()
    print(f"  Created project: {project.name}")

    # Create brands
    brands = [
        Brand(
            id=uuid4(),
            project_id=project.id,
            name="Acme Analytics",
            is_primary=True,
            aliases=["Acme", "AcmeAnalytics"],
        ),
        Brand(
            id=uuid4(),
            project_id=project.id,
            name="Acme Insights",
            is_primary=False,
            aliases=["Insights"],
        ),
    ]
    for brand in brands:
        db.add(brand)
    db.flush()
    print(f"  Created {len(brands)} brands")

    # Create competitors
    competitors = [
        Competitor(
            id=uuid4(),
            project_id=project.id,
            name="DataDog",
            domain="datadoghq.com",
            aliases=["Datadog", "DD"],
        ),
        Competitor(
            id=uuid4(),
            project_id=project.id,
            name="Mixpanel",
            domain="mixpanel.com",
            aliases=[],
        ),
        Competitor(
            id=uuid4(),
            project_id=project.id,
            name="Amplitude",
            domain="amplitude.com",
            aliases=["Amp"],
        ),
    ]
    for comp in competitors:
        db.add(comp)
    db.flush()
    print(f"  Created {len(competitors)} competitors")

    # Create prompt templates
    templates = [
        PromptTemplate(
            id=uuid4(),
            name="What Is Query",
            prompt_type=PromptType.INFORMATIONAL,
            template_text="What is {keyword}? Please provide a comprehensive overview including key features, benefits, and notable providers or solutions in this space.",
            version_major=1,
            version_minor=0,
            version_patch=0,
            is_active=True,
            expected_output_format="paragraph",
        ),
        PromptTemplate(
            id=uuid4(),
            name="Best Options Query",
            prompt_type=PromptType.COMPARATIVE,
            template_text="What are the best options for {keyword}? Compare the top solutions available and explain what makes each one stand out.",
            version_major=1,
            version_minor=0,
            version_patch=0,
            is_active=True,
            expected_output_format="list",
        ),
        PromptTemplate(
            id=uuid4(),
            name="Recommendation Query",
            prompt_type=PromptType.RECOMMENDATION,
            template_text="What {keyword} should I use? I'm looking for a reliable solution. What would you recommend and why?",
            version_major=1,
            version_minor=0,
            version_patch=0,
            is_active=True,
            expected_output_format="paragraph",
        ),
    ]
    for template in templates:
        db.add(template)
    db.flush()
    print(f"  Created {len(templates)} prompt templates")

    # Create keywords
    keywords_data = [
        "product analytics platform",
        "user behavior analytics",
        "web analytics tool",
        "data analytics software",
        "business intelligence tool",
        "customer analytics solution",
        "real-time analytics",
        "marketing analytics",
    ]

    keywords = []
    for kw_text in keywords_data:
        kw = Keyword(
            id=uuid4(),
            project_id=project.id,
            keyword=kw_text,
            priority="medium",
            is_active=True,
        )
        db.add(kw)
        keywords.append(kw)
    db.flush()
    print(f"  Created {len(keywords)} keywords")

    # Create citation sources
    sources = [
        CitationSource(
            id=uuid4(),
            domain="g2.com",
            category=SourceCategory.REVIEW_SITE,
            site_name="G2",
            total_citations=0,
        ),
        CitationSource(
            id=uuid4(),
            domain="techcrunch.com",
            category=SourceCategory.NEWS,
            site_name="TechCrunch",
            total_citations=0,
        ),
        CitationSource(
            id=uuid4(),
            domain="stackoverflow.com",
            category=SourceCategory.FORUM,
            site_name="Stack Overflow",
            total_citations=0,
        ),
        CitationSource(
            id=uuid4(),
            domain="docs.acme-analytics.com",
            category=SourceCategory.OFFICIAL_DOCS,
            site_name="Acme Docs",
            total_citations=0,
        ),
    ]
    for source in sources:
        db.add(source)
    db.flush()
    print(f"  Created {len(sources)} citation sources")

    # Create sample prompts, runs, responses, and scores
    providers = [LLMProvider.OPENAI, LLMProvider.ANTHROPIC, LLMProvider.GOOGLE, LLMProvider.PERPLEXITY]
    provider_models = {
        LLMProvider.OPENAI: "gpt-4-turbo",
        LLMProvider.ANTHROPIC: "claude-3-opus-20240229",
        LLMProvider.GOOGLE: "gemini-1.5-pro",
        LLMProvider.PERPLEXITY: "llama-3.1-sonar-large-128k-online",
    }

    total_runs = 0
    for keyword in keywords[:4]:  # First 4 keywords
        for template in templates[:2]:  # First 2 templates
            # Create prompt
            prompt_text = template.template_text.replace("{keyword}", keyword.keyword)
            prompt_hash = generate_prompt_hash(prompt_text, template.version)

            prompt = Prompt(
                id=uuid4(),
                keyword_id=keyword.id,
                template_id=template.id,
                prompt_type=template.prompt_type,
                prompt_text=prompt_text,
                prompt_hash=prompt_hash,
                injected_context={"keyword": keyword.keyword, "industry": "technology"},
            )
            db.add(prompt)
            db.flush()

            for provider in providers:
                # Create LLM run
                run = LLMRun(
                    id=uuid4(),
                    project_id=project.id,
                    prompt_id=prompt.id,
                    provider=provider,
                    model_name=provider_models[provider],
                    temperature=0.7,
                    max_tokens=2000,
                    status=LLMRunStatus.COMPLETED,
                    priority="medium",
                    queued_at=datetime.utcnow() - timedelta(hours=random.randint(1, 48)),
                    started_at=datetime.utcnow() - timedelta(hours=random.randint(1, 47)),
                    completed_at=datetime.utcnow() - timedelta(minutes=random.randint(1, 60)),
                    input_tokens=random.randint(50, 150),
                    output_tokens=random.randint(300, 800),
                    estimated_cost_usd=Decimal(str(round(random.uniform(0.01, 0.05), 4))),
                    is_cached_result=False,
                )
                db.add(run)
                db.flush()

                # Create sample response
                sample_response = f"""When looking for {keyword.keyword}, there are several strong options to consider.

Acme Analytics is a leading choice, offering comprehensive features for tracking user behavior and generating insights. Their platform is known for its real-time capabilities and intuitive dashboards.

DataDog provides excellent infrastructure monitoring with analytics capabilities. They're particularly strong in the DevOps space.

Mixpanel focuses specifically on product analytics, making it ideal for teams who want deep user journey analysis.

For more information, you can check reviews on G2 or the official documentation at docs.acme-analytics.com."""

                response = LLMResponse(
                    id=uuid4(),
                    llm_run_id=run.id,
                    raw_response=sample_response,
                    response_metadata={"finish_reason": "stop"},
                    parsed_response={},
                    response_hash=generate_response_hash(sample_response),
                )
                db.add(response)
                db.flush()

                # Create brand mentions
                mention_data = [
                    ("Acme Analytics", brands[0].id, True, 1, SentimentPolarity.POSITIVE),
                    ("DataDog", competitors[0].id, False, 2, SentimentPolarity.NEUTRAL),
                    ("Mixpanel", competitors[1].id, False, 3, SentimentPolarity.NEUTRAL),
                ]

                for mention_text, entity_id, is_own, position, sentiment in mention_data:
                    mention = BrandMention(
                        id=uuid4(),
                        response_id=response.id,
                        mentioned_text=mention_text,
                        normalized_name=mention_text,
                        is_own_brand=is_own,
                        brand_id=entity_id if is_own else None,
                        competitor_id=entity_id if not is_own else None,
                        mention_position=position,
                        match_type="exact",
                        match_confidence=1.0,
                        sentiment=sentiment,
                        sentiment_score=0.8 if sentiment == SentimentPolarity.POSITIVE else 0.0,
                    )
                    db.add(mention)

                # Create citations
                for i, source in enumerate(sources[:2]):
                    citation = Citation(
                        id=uuid4(),
                        response_id=response.id,
                        source_id=source.id,
                        cited_url=f"https://{source.domain}/analytics-guide",
                        citation_position=i + 1,
                        is_valid_url=True,
                        is_accessible=True,
                        is_hallucinated=False,
                    )
                    db.add(citation)
                    source.total_citations += 1

                db.flush()

                # Create visibility score
                mention_score = 30  # Brand mentioned
                position_score = 20  # In top 3
                citation_score = 15 if random.random() > 0.3 else 0  # Sometimes cited
                sentiment_score = random.randint(5, 10)
                competitor_delta = random.randint(-5, 5)

                total_raw = mention_score + position_score + citation_score + sentiment_score + competitor_delta
                llm_weight = {
                    LLMProvider.OPENAI: 1.0,
                    LLMProvider.ANTHROPIC: 0.9,
                    LLMProvider.GOOGLE: 0.8,
                    LLMProvider.PERPLEXITY: 1.1,
                }[provider]

                normalized = max(0, min(100, (total_raw + 15) / 90 * 100))

                score = VisibilityScore(
                    id=uuid4(),
                    project_id=project.id,
                    llm_run_id=run.id,
                    keyword_id=keyword.id,
                    provider=provider,
                    mention_score=mention_score,
                    position_score=position_score,
                    citation_score=citation_score,
                    sentiment_score=sentiment_score,
                    competitor_delta=competitor_delta,
                    total_score=normalized,
                    llm_weight=llm_weight,
                    weighted_score=normalized * llm_weight,
                    score_explanation={
                        "summary": "Brand mentioned in top position with positive sentiment"
                    },
                    score_date=run.completed_at,
                )
                db.add(score)

                total_runs += 1

    db.flush()
    print(f"  Created {total_runs} LLM runs with responses and scores")

    # Create aggregated scores for the last 14 days
    for days_ago in range(14):
        period_start = (datetime.utcnow() - timedelta(days=days_ago)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        period_end = period_start + timedelta(days=1)

        agg = AggregatedScore(
            id=uuid4(),
            project_id=project.id,
            period_type="daily",
            period_start=period_start,
            period_end=period_end,
            avg_visibility_score=random.uniform(55, 75),
            avg_mention_score=random.uniform(25, 30),
            avg_position_score=random.uniform(15, 20),
            avg_citation_score=random.uniform(10, 15),
            scores_by_llm={
                "openai": random.uniform(55, 75),
                "anthropic": random.uniform(50, 70),
                "google": random.uniform(45, 65),
                "perplexity": random.uniform(60, 80),
            },
            score_delta_vs_previous=random.uniform(-5, 5),
            total_queries=random.randint(10, 30),
            total_mentions=random.randint(20, 50),
            total_citations=random.randint(5, 20),
        )
        db.add(agg)

    db.commit()
    print("  Created 14 days of aggregated scores")

    print("\nSeed data created successfully!")
    print(f"\n  Login credentials:")
    print(f"    Email: demo@llmrefs.com")
    print(f"    Password: Demo1234!")


def main():
    """Main entry point"""
    print("Connecting to database...")
    engine = create_engine(settings.DATABASE_URL)

    print("Creating tables...")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        # Check if data already exists
        existing_user = db.query(User).filter(User.email == "demo@llmrefs.com").first()
        if existing_user:
            print("Sample data already exists. Skipping seed.")
            return

        create_sample_data(db)


if __name__ == "__main__":
    main()
