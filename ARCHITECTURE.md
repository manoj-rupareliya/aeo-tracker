# llmrefs.com - System Architecture

## Architecture Diagram (Text-Based)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   FRONTEND                                       │
│                              Next.js 14 (App Router)                            │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐ │
│  │  Dashboard  │ │  Projects   │ │  Keywords   │ │   Reports   │ │  Settings  │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘ │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │ REST API + WebSocket
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                API GATEWAY                                       │
│                         FastAPI + JWT Authentication                            │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │  Rate Limiting │ Auth Middleware │ Request Validation │ Response Caching   ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│    AUTH &     │         │    PROMPT     │         │   VISIBILITY  │
│   PROJECT     │         │  GENERATION   │         │    SCORING    │
│   SERVICE     │         │    ENGINE     │         │    ENGINE     │
├───────────────┤         ├───────────────┤         ├───────────────┤
│ - User CRUD   │         │ - Template    │         │ - Score Calc  │
│ - Project Mgmt│         │   Versioning  │         │ - Aggregation │
│ - Brand Mgmt  │         │ - Prompt Gen  │         │ - Time Series │
│ - Competitor  │         │ - Caching     │         │ - Comparison  │
└───────────────┘         └───────────────┘         └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              MESSAGE QUEUE                                       │
│                         Redis + Celery (Bull Alternative)                       │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐                   │
│  │  llm_execution  │ │ response_parse  │ │ score_calculate │                   │
│  │     queue       │ │     queue       │ │     queue       │                   │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘                   │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│     LLM       │         │   RESPONSE    │         │    SOURCE     │
│  EXECUTION    │         │   PARSING     │         │ INTELLIGENCE  │
│   SERVICE     │         │   SERVICE     │         │   SERVICE     │
├───────────────┤         ├───────────────┤         ├───────────────┤
│ Adapters:     │         │ - Brand Match │         │ - Domain Norm │
│ - OpenAI      │         │ - Citation Ex │         │ - Categorize  │
│ - Anthropic   │         │ - Sentiment   │         │ - Frequency   │
│ - Google      │         │ - Hallucinate │         │ - Competitor  │
│ - Perplexity  │         │   Detection   │         │   Analysis    │
└───────────────┘         └───────────────┘         └───────────────┘
        │                           │                           │
        └───────────────────────────┼───────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                         PostgreSQL (Primary)                                ││
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────┐ ││
│  │  │  Users  │ │Projects │ │Keywords │ │ Prompts │ │LLM Runs │ │ Citations │ ││
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘ └───────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                           Redis (Cache/Queue)                               ││
│  │  - Response Cache (prompt+model+version keyed)                              ││
│  │  - Rate Limit Counters                                                      ││
│  │  - Task Queue State                                                         ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Service Responsibilities

### 1. Auth & Project Service
- JWT-based authentication with refresh tokens
- Multi-tenant project isolation
- Brand name management (primary + aliases)
- Competitor brand tracking
- Industry categorization for prompt context

### 2. Prompt Generation Engine
- Template-based prompt generation
- Version control for all templates (semantic versioning)
- Three prompt types: Informational, Comparative, Recommendation
- Deterministic prompt hashing for cache keying
- Context injection (industry, brand aliases)

### 3. LLM Execution Service
- Adapter pattern for each LLM provider
- Unified interface: `execute(prompt, config) -> LLMResponse`
- Retry logic with exponential backoff
- Timeout handling (30s default, configurable)
- Full response storage (raw, tokens, timing)
- Cost tracking per request

### 4. Response Parsing Service
- Exact brand matching (case-insensitive)
- Fuzzy matching using Levenshtein distance
- Position tracking (1st, 2nd, 3rd mention)
- Basic sentiment analysis (positive/neutral/negative)
- URL extraction with validation
- Hallucination detection (HTTP HEAD check on citations)

### 5. Source Intelligence Service
- Domain normalization (www removal, path stripping)
- Source categorization via domain patterns
- Citation frequency aggregation
- Competitor-exclusive citation identification
- Source authority scoring (future: domain authority lookup)

### 6. Visibility Scoring Engine
Transparent, explainable scoring:
```
Base Score = 0

+30 points: Brand mentioned
+20 points: Brand in top-3 mentions
+15 points: Brand cited as source
+10 points: Positive sentiment
-5 points: Competitor mentioned before brand
-10 points: Brand not mentioned at all

LLM Weight Multiplier:
- ChatGPT: 1.0x (market leader)
- Claude: 0.9x (growing adoption)
- Gemini: 0.8x (newer entrant)
- Perplexity: 1.1x (citation-focused, high value)

Final Score = Sum(per_llm_score * llm_weight) / num_llms
```

### 7. Queue Architecture
```
Priority Levels:
- HIGH: User-initiated single queries
- MEDIUM: Scheduled batch runs
- LOW: Background re-crawls

Job Flow:
1. Job Created → PENDING
2. Worker Picks Up → PROCESSING
3. LLM Called → EXECUTING
4. Response Received → PARSING
5. Parsing Complete → SCORING
6. Score Saved → COMPLETED
```

## Data Flow

1. User adds keyword → Prompt Engine generates prompts
2. Prompts queued for each enabled LLM
3. LLM Execution Service processes queue
4. Raw responses stored immediately
5. Parsing Service extracts structured data
6. Source Intelligence enriches citations
7. Scoring Engine calculates visibility
8. Dashboard displays aggregated results

## Cost Control Strategy

1. **Prompt Caching**: SHA-256 hash of (prompt_text + model + template_version)
2. **TTL-based Expiry**: Cached responses valid for 7 days by default
3. **Batch Processing**: Group keywords into single LLM calls where possible
4. **Token Budgets**: Per-project monthly token limits
5. **Smart Scheduling**: Spread re-crawls across time to avoid rate limits

## Security Model

1. **API Key Isolation**: Each LLM provider key stored separately in env
2. **Project Scoping**: All queries filtered by project_id
3. **Row-Level Security**: PostgreSQL RLS policies
4. **Audit Logging**: All LLM calls logged with user context
5. **Rate Limiting**: Per-user, per-endpoint limits
