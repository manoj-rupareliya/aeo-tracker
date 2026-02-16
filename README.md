# llmscm.com

## LLM Visibility & GEO Intelligence Platform

A production-ready B2B SaaS platform for tracking how Large Language Models (ChatGPT, Claude, Gemini, Perplexity) mention your brand, which sources they cite, and measuring your visibility over time.

**Core Philosophy: GEO-First (Generative Engine Optimization)**

Unlike traditional SEO that optimizes for search rankings, llmscm.com helps you optimize for AI-generated responses. As LLMs become primary information interfaces, knowing how they perceive and recommend your brand is critical.

---

## What Makes This Defensible

### 1. Temporal Intelligence
We accumulate historical LLM behavior data that creates a compounding moat. Every day of data collected is a day competitors can never catch up to. This historical context enables:
- Trend analysis across months/years
- Model behavior change detection
- Seasonal pattern identification

### 2. LLM Preference Graph
A unique, proprietary dataset mapping relationships between:
- Which sources each LLM prefers to cite
- How brand affinities differ across models
- Authority hub identification for GEO targeting

### 3. Enterprise-Grade Audit Trail
Every insight is traceable to raw data. Enterprises require:
- Complete provenance chains
- Immutable response archives
- Confidence scoring with explainability

### 4. SAIV Metric (Share of AI Voice)
Industry-standard measurement for AI visibility:
```
SAIV = (Brand Mentions in AI Responses) / (Total Entity Mentions) × 100
```
First-mover advantage in defining this metric = category ownership.

### 5. Cost Efficiency at Scale
Caching infrastructure reduces operational costs over time. Each cached response is pure margin on subsequent queries.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [V2 Feature Set](#v2-feature-set)
3. [Tech Stack](#tech-stack)
4. [API Reference](#api-reference)
5. [Setup Instructions](#setup-instructions)
6. [Deployment](#deployment)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              LLMSCM.COM V2                                      │
│                   LLM Visibility & GEO Intelligence Platform                    │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│                              PRESENTATION LAYER                                  │
│                           Next.js 14 (App Router)                               │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌───────────┐ │
│  │  Dashboard  │ │  Drift      │ │  Preference │ │  GEO        │ │   Audit   │ │
│  │  + SAIV     │ │  Timeline   │ │  Graph      │ │  Advisor    │ │   Trail   │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └───────────┘ │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                         │
│                    FastAPI + JWT + Rate Limiting + Audit Logging                │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
    ┌───────────────┬───────────────┼───────────────┬───────────────┐
    │               │               │               │               │
    ▼               ▼               ▼               ▼               ▼
┌─────────┐   ┌─────────┐   ┌─────────────┐   ┌─────────┐   ┌─────────────┐
│  TRUST  │   │  DRIFT  │   │  PREFERENCE │   │   GEO   │   │    SAIV     │
│ & AUDIT │   │DETECTION│   │    GRAPH    │   │ ADVISOR │   │   ENGINE    │
│  LAYER  │   │ ENGINE  │   │   ENGINE    │   │ ENGINE  │   │             │
├─────────┤   ├─────────┤   ├─────────────┤   ├─────────┤   ├─────────────┤
│• Exec   │   │• Snapshot│  │• Node/Edge  │   │• Gap    │   │• Brand %    │
│  Logs   │   │  Storage │  │  Builder    │   │  Finder │   │• LLM SAIV   │
│• Raw    │   │• Diff    │  │• Authority  │   │• Source │   │• Keyword    │
│  Archive│   │  Engine  │  │  Scoring    │   │  Mapper │   │  Cluster    │
│• Parse  │   │• Severity│  │• Behavior   │   │• Action │   │• Time Delta │
│  Lineage│   │  Rating  │  │  Profiles   │   │  Gen    │   │             │
│• Confi- │   │• Alert   │  │• Cross-LLM  │   │• Explai-│   │             │
│  dence  │   │  System  │  │  Analysis   │   │  nability│  │             │
└─────────┘   └─────────┘   └─────────────┘   └─────────┘   └─────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COST & PERFORMANCE GOVERNANCE                          │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │  Prompt Hash    │ │  Smart          │ │  Rate Limit     │ │  Budget       │ │
│  │  Caching        │ │  Scheduling     │ │  Manager        │ │  Controls     │ │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘ └───────────────┘ │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                         PostgreSQL (Primary)                                ││
│  │  CORE:          │  AUDIT:           │  INTELLIGENCE:                        ││
│  │  Users          │  ExecutionLogs    │  PreferenceEdges                      ││
│  │  Projects       │  ResponseArchive  │  DriftRecords                         ││
│  │  Brands         │  ParseLineage     │  SAIVSnapshots                        ││
│  │  Keywords       │  ConfidenceScores │  Recommendations                      ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                           Redis (Cache/Queue)                               ││
│  │  • Response Cache (prompt_hash keyed, 7-day TTL)                            ││
│  │  • Rate Limit Counters (per-model, per-user)                                ││
│  │  • SAIV Cache (hourly refresh)                                              ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## V2 Feature Set

### 1. Trust & Audit Layer
**Purpose**: Every insight must be traceable to raw data

- **ExecutionLog**: Complete record of every LLM call (prompt, config, timing)
- **ResponseArchive**: Immutable storage of raw LLM outputs (never modified)
- **ParseLineage**: How each entity was extracted (regex, NLP, position)
- **ConfidenceScore**: How certain we are about each insight

**API Endpoints**:
```
GET /api/v1/audit/{run_id}/raw         → Raw LLM response
GET /api/v1/audit/{run_id}/parsed      → Parsed entities
GET /api/v1/audit/{run_id}/lineage     → Extraction methodology
GET /api/v1/audit/{run_id}/confidence  → Confidence breakdown
```

### 2. Change & Drift Detection Engine
**Purpose**: Track how LLM behavior changes over time

- **Snapshot Storage**: Point-in-time captures of responses
- **Diff Engine**: Compare snapshots for same prompt
- **Severity Scoring**: Classify changes (minor/moderate/major/critical)
- **Alert System**: Notify on significant drift

**Change Types**:
- Brand appearance change (appeared/disappeared)
- Position shift (promoted/demoted)
- Citation replacement (new source cited)
- Competitor displacement (you replaced/were replaced)
- Sentiment changes

### 3. LLM Preference Graph
**Purpose**: Understand which LLMs prefer which sources

**Node Types**:
- LLM (ChatGPT, Claude, Gemini, Perplexity)
- Domain (source websites)
- Brand (tracked entities)

**Edge Types**:
- CITES: LLM → Domain (frequency, recency)
- MENTIONS: LLM → Brand (frequency, position, sentiment)
- ASSOCIATED: Domain → Brand (co-occurrence)

**Derived Metrics**:
- Source Authority Score (per LLM)
- Brand Persistence Score (across LLMs)
- Authority Hub Detection (domains that dominate)

### 4. GEO Recommendation Engine
**Purpose**: Actionable, evidence-based recommendations

**Inputs**:
- Keywords where brand is missing
- Sources that LLMs cite for those keywords
- Competitor presence in those responses

**Outputs**:
- Gap Analysis: "You're absent from 60% of 'analytics platform' queries"
- Source Mapping: "ChatGPT cites G2, Gartner, TechCrunch for this topic"
- Action Items: "Get listed on G2, create content matching cited formats"

**Constraints**:
- No hallucinated recommendations
- All suggestions backed by observed LLM behavior
- Confidence level for each recommendation

### 5. Share of AI Voice (SAIV)
**Purpose**: Quantify brand presence in AI-generated content

**Formula**:
```
SAIV = (Brand Mentions in AI Responses) / (Total Entity Mentions) × 100
```

**Dimensions**:
- Overall SAIV (across all LLMs, keywords)
- LLM-specific SAIV (per ChatGPT, Claude, etc.)
- Keyword Cluster SAIV (by topic group)
- Time-series SAIV (daily, weekly, monthly)

**Properties**:
- Reproducible (same inputs = same output)
- Transparent (calculation visible)
- Comparable (relative to competitors)

### 6. Cost & Performance Governance
**Purpose**: Minimize spend without losing insight quality

**Mechanisms**:
- **Prompt Hash Caching**: SHA-256(prompt + model + temp) → cached response
- **Smart Scheduling**: Spread queries to avoid rate limits
- **Model-specific Limits**: Different quotas per LLM provider
- **Partial Results**: Accept incomplete data gracefully
- **Priority Queues**: User-initiated > scheduled > background

**Budget Controls**:
- Per-project token limits
- Daily/monthly cost caps
- Automatic pause on budget exceed

---

## Tech Stack

### Backend (Python)
- **Framework**: FastAPI (async, type-safe, OpenAPI docs)
- **ORM**: SQLAlchemy 2.0 with async support
- **Database**: PostgreSQL with JSONB
- **Queue**: Celery + Redis
- **Cache**: Redis

### Frontend
- **Framework**: Next.js 14 (App Router)
- **State Management**: Zustand + React Query
- **Styling**: Tailwind CSS
- **Charts**: Recharts

---

## API Reference

### Trust & Audit
```
GET  /api/v1/audit/{run_id}/raw          - Raw LLM response
GET  /api/v1/audit/{run_id}/parsed       - Parsed entities
GET  /api/v1/audit/{run_id}/lineage      - Extraction lineage
GET  /api/v1/audit/{run_id}/confidence   - Confidence breakdown
GET  /api/v1/audit/{run_id}/full         - Complete audit trail
GET  /api/v1/audit/project/{id}/executions - Project execution logs
GET  /api/v1/audit/project/{id}/cost-summary - Cost summary
```

### Drift Detection
```
POST /api/v1/drift/snapshots/{project_id}  - Create snapshot
GET  /api/v1/drift/snapshots/{project_id}/latest - Latest snapshots
POST /api/v1/drift/detect/{project_id}     - Run drift detection
GET  /api/v1/drift/records/{project_id}    - Get drift records
GET  /api/v1/drift/alerts/{project_id}     - Unalerted drifts
GET  /api/v1/drift/summary/{project_id}    - Drift summary
GET  /api/v1/drift/timeline/{project_id}   - Drift timeline
```

### Preference Graph
```
GET  /api/v1/graph/nodes/{project_id}      - Graph nodes
GET  /api/v1/graph/edges/{project_id}      - Graph edges
GET  /api/v1/graph/llm/{project_id}/{provider}/preferred-sources
GET  /api/v1/graph/brand/{project_id}/{brand}/affinity
GET  /api/v1/graph/hubs/{project_id}       - Authority hubs
GET  /api/v1/graph/visualization/{project_id} - Visualization data
```

### GEO Recommendations
```
GET  /api/v1/recommendations/{project_id}  - Get recommendations
POST /api/v1/recommendations/{project_id}/generate - Generate new
GET  /api/v1/recommendations/{project_id}/summary  - Summary
POST /api/v1/recommendations/{id}/dismiss  - Dismiss
POST /api/v1/recommendations/{id}/complete - Mark complete
GET  /api/v1/recommendations/{project_id}/gaps - Gap analyses
GET  /api/v1/recommendations/{id}/evidence - Evidence details
```

### SAIV (Share of AI Voice)
```
POST /api/v1/saiv/{project_id}/calculate   - Calculate SAIV
GET  /api/v1/saiv/{project_id}/current     - Current SAIV
GET  /api/v1/saiv/{project_id}/history     - SAIV history
GET  /api/v1/saiv/{project_id}/by-llm      - SAIV by LLM
GET  /api/v1/saiv/{project_id}/compare     - Period comparison
GET  /api/v1/saiv/{project_id}/vs-competitors - Competitor comparison
GET  /api/v1/saiv/{project_id}/insights    - SAIV insights
GET  /api/v1/saiv/{project_id}/trend       - Trend data
```

### Cost Governance
```
GET  /api/v1/cost/{project_id}/budget      - Get budget
PUT  /api/v1/cost/{project_id}/budget      - Update budget
POST /api/v1/cost/{project_id}/budget/unpause - Unpause
POST /api/v1/cost/{project_id}/budget/check - Check budget
GET  /api/v1/cost/{project_id}/rate-limits - Rate limit status
GET  /api/v1/cost/{project_id}/cache       - Cache metrics
GET  /api/v1/cost/{project_id}/summary     - Cost summary
GET  /api/v1/cost/{project_id}/estimate    - Estimate cost
```

---

## Setup Instructions

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Redis 7+

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python -c "from app.utils import init_db; import asyncio; asyncio.run(init_db())"

# Start API server
uvicorn app.main:app --reload --port 8000

# In another terminal, start Celery worker
celery -A app.workers.celery_app worker --loglevel=info
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env.local

# Start development server
npm run dev
```

---

## Deployment

### Vercel Deployment (Frontend)

1. Connect your GitHub repository to Vercel
2. Set environment variables:
   - `NEXT_PUBLIC_API_URL=https://your-api-domain.com`
3. Deploy

### Backend Deployment

Recommended: Docker + Railway/Render/Fly.io

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/llmscm
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  worker:
    build: ./backend
    command: celery -A app.workers.celery_app worker --loglevel=info
    depends_on:
      - db
      - redis

  db:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7

volumes:
  postgres_data:
```

---

## Philosophical Principles

1. **Intelligence, Not Optimization**: We observe and report, not manipulate
2. **Transparency Over Magic**: Every number has an explanation
3. **Evidence-Based Actions**: Recommendations cite observed behavior
4. **No False Promises**: We don't claim to improve rankings
5. **Audit Everything**: Trust requires verifiability

---

## License

Proprietary - All rights reserved.

---

## Support

For issues and feature requests, contact support@llmscm.com
