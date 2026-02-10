# llmrefs.com V2 - Enterprise Architecture

## Evolution: From Response Tracker to Intelligence System

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              LLMREFS.COM V2                                      │
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
    │               │               │               │               │
    └───────────────┴───────────────┼───────────────┴───────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           COST & PERFORMANCE GOVERNANCE                          │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌───────────────┐ │
│  │  Prompt Hash    │ │  Smart          │ │  Rate Limit     │ │  Partial      │ │
│  │  Caching        │ │  Scheduling     │ │  Manager        │ │  Results      │ │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘ └───────────────┘ │
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              MESSAGE QUEUE                                       │
│                         Redis + Celery (Priority Queues)                        │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌───────────────────┐   │
│  │ llm_execution │ │ drift_detect  │ │ graph_update  │ │ recommendation    │   │
│  │ (rate-limited)│ │ (batch)       │ │ (incremental) │ │ (low-priority)    │   │
│  └───────────────┘ └───────────────┘ └───────────────┘ └───────────────────────┘│
└───────────────────────────────────┬─────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐         ┌───────────────┐
│     LLM       │         │   RESPONSE    │         │   SOURCE      │
│  EXECUTION    │         │   PARSING     │         │ INTELLIGENCE  │
│   SERVICE     │         │   SERVICE     │         │   SERVICE     │
├───────────────┤         ├───────────────┤         ├───────────────┤
│ Adapters:     │         │ • Brand Match │         │ • Domain Norm │
│ • OpenAI      │ ────────│ • Citation Ex │─────────│ • Categorize  │
│ • Anthropic   │         │ • Sentiment   │         │ • Authority   │
│ • Google      │         │ • Position    │         │ • Frequency   │
│ • Perplexity  │         │ • Confidence  │         │ • LLM Affinity│
└───────────────┘         └───────────────┘         └───────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                         PostgreSQL (Primary)                                ││
│  │  ┌─────────────────────────────────────────────────────────────────────┐   ││
│  │  │  CORE:          │  AUDIT:           │  INTELLIGENCE:                │   ││
│  │  │  Users          │  ExecutionLogs    │  PreferenceEdges              │   ││
│  │  │  Projects       │  ResponseArchive  │  DriftRecords                 │   ││
│  │  │  Brands         │  ParseLineage     │  SAIVSnapshots                │   ││
│  │  │  Keywords       │  ConfidenceScores │  Recommendations              │   ││
│  │  │  LLMRuns        │                   │  SourceAuthority              │   ││
│  │  └─────────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
│  ┌─────────────────────────────────────────────────────────────────────────────┐│
│  │                           Redis (Cache/Queue)                               ││
│  │  • Response Cache (prompt_hash keyed, 7-day TTL)                            ││
│  │  • Rate Limit Counters (per-model, per-user)                                ││
│  │  • SAIV Cache (hourly refresh)                                              ││
│  │  • Graph Cache (incremental updates)                                        ││
│  └─────────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────────┘
```

## New System Responsibilities

### 1. Trust & Audit Layer
**Purpose**: Every insight must be traceable to raw data

- **ExecutionLog**: Complete record of every LLM call (prompt, config, timing)
- **ResponseArchive**: Immutable storage of raw LLM outputs (never modified)
- **ParseLineage**: How each entity was extracted (regex, NLP, position)
- **ConfidenceScore**: How certain we are about each insight

**API Contracts**:
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
- **Severity Scoring**: Classify changes (minor/moderate/major)
- **Alert System**: Notify on significant drift

**Change Types**:
- Brand appearance change (appeared/disappeared)
- Position shift (promoted/demoted)
- Citation replacement (new source cited)
- Competitor displacement (you replaced/were replaced)

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

## Data Flow

### Query Execution Flow
```
1. User triggers analysis for keywords
2. PromptEngine generates versioned prompts
3. CostGovernance checks budget & rate limits
4. If cached: return cached response (mark as cached)
5. If not cached:
   a. Queue to appropriate LLM adapter
   b. Execute with retry logic
   c. Store raw response in ResponseArchive
   d. Parse and extract entities
   e. Store ParseLineage with confidence scores
   f. Cache for future use
6. TrustLayer records ExecutionLog
7. DriftEngine checks for changes vs previous snapshot
8. GraphEngine updates preference edges
9. SAIVEngine recalculates metrics
10. RecommendationEngine generates insights
```

### Audit Query Flow
```
1. User requests insight explanation
2. System retrieves:
   - Original ExecutionLog
   - Raw ResponseArchive entry
   - ParseLineage records
   - ConfidenceScores
3. Renders complete provenance chain
4. User can verify: raw → parsed → insight
```

---

## Defensibility Factors

1. **Temporal Intelligence**: Historical LLM behavior data creates moat
2. **Preference Graph**: Unique dataset of LLM-source relationships
3. **Audit Trail**: Enterprise compliance requirement
4. **SAIV Metric**: Industry-standard measurement (if adopted)
5. **Cost Efficiency**: Caching reduces operational cost over time

---

## Philosophical Principles

1. **Intelligence, Not Optimization**: We observe and report, not manipulate
2. **Transparency Over Magic**: Every number has an explanation
3. **Evidence-Based Actions**: Recommendations cite observed behavior
4. **No False Promises**: We don't claim to improve rankings
5. **Audit Everything**: Trust requires verifiability
