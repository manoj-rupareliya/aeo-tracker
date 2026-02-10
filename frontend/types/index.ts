/**
 * TypeScript type definitions
 */

// User types
export interface User {
  id: string;
  email: string;
  full_name: string;
  subscription_tier: "free" | "starter" | "professional" | "enterprise";
  monthly_token_limit: number;
  tokens_used_this_month: number;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  last_login_at: string | null;
}

// Project types
export interface Brand {
  id: string;
  name: string;
  is_primary: boolean;
  aliases: string[];
  created_at: string;
}

export interface Competitor {
  id: string;
  name: string;
  domain: string | null;
  aliases: string[];
  created_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string | null;
  domain: string;
  industry: string;
  enabled_llms: string[];
  crawl_frequency_days: number;
  last_crawl_at: string | null;
  next_crawl_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  brands: Brand[];
  competitors: Competitor[];
  keyword_count: number;
  total_runs: number;
}

// Keyword types
export interface Keyword {
  id: string;
  keyword: string;
  context: string | null;
  priority: "high" | "medium" | "low";
  is_active: boolean;
  created_at: string;
  updated_at: string;
  prompt_count: number;
  run_count: number;
  avg_visibility_score: number | null;
  last_run_at: string | null;
}

// LLM Run types
export interface LLMRun {
  id: string;
  project_id: string;
  prompt_id: string | null;
  provider: "openai" | "anthropic" | "google" | "perplexity";
  model_name: string;
  temperature: number;
  max_tokens: number;
  status: "pending" | "processing" | "executing" | "parsing" | "scoring" | "completed" | "failed" | "cached";
  priority: "high" | "medium" | "low";
  queued_at: string;
  started_at: string | null;
  completed_at: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  is_cached_result: boolean;
  retry_count: number;
  error_message: string | null;
  created_at: string;
}

export interface LLMResponse {
  id: string;
  llm_run_id: string;
  raw_response: string;
  response_metadata: Record<string, unknown>;
  parsed_response: Record<string, unknown>;
  response_hash: string;
  created_at: string;
}

// Analysis types
export interface BrandMention {
  id: string;
  response_id: string;
  mentioned_text: string;
  normalized_name: string;
  is_own_brand: boolean;
  brand_id: string | null;
  competitor_id: string | null;
  mention_position: number;
  character_offset: number | null;
  context_snippet: string | null;
  match_type: "exact" | "alias" | "fuzzy";
  match_confidence: number;
  sentiment: "positive" | "neutral" | "negative";
  sentiment_score: number | null;
  created_at: string;
}

export interface Citation {
  id: string;
  response_id: string;
  source_id: string | null;
  cited_url: string;
  anchor_text: string | null;
  context_snippet: string | null;
  citation_position: number | null;
  is_valid_url: boolean | null;
  is_accessible: boolean | null;
  http_status_code: number | null;
  is_hallucinated: boolean;
  last_validated_at: string | null;
  created_at: string;
}

export interface CitationSource {
  id: string;
  domain: string;
  category: string;
  site_name: string | null;
  description: string | null;
  domain_authority: number | null;
  total_citations: number;
  last_cited_at: string | null;
  created_at: string;
}

// Score types
export interface VisibilityScore {
  id: string;
  project_id: string;
  llm_run_id: string | null;
  keyword_id: string | null;
  provider: string | null;
  mention_score: number;
  position_score: number;
  citation_score: number;
  sentiment_score: number;
  competitor_delta: number;
  total_score: number;
  llm_weight: number;
  weighted_score: number;
  score_explanation: Record<string, unknown>;
  score_date: string;
  created_at: string;
}

export interface AggregatedScore {
  id: string;
  project_id: string;
  period_type: "daily" | "weekly" | "monthly";
  period_start: string;
  period_end: string;
  avg_visibility_score: number;
  avg_mention_score: number;
  avg_position_score: number;
  avg_citation_score: number;
  scores_by_llm: Record<string, number>;
  score_delta_vs_previous: number | null;
  total_queries: number;
  total_mentions: number;
  total_citations: number;
  created_at: string;
}

// Dashboard types
export interface DashboardMetric {
  label: string;
  value: number;
  format: "number" | "percent" | "score";
  trend: "up" | "down" | "stable";
  trend_delta: number | null;
  trend_period: string;
}

export interface DashboardOverview {
  project_id: string;
  project_name: string;
  last_updated: string;
  visibility_score: DashboardMetric;
  mention_rate: DashboardMetric;
  citation_rate: DashboardMetric;
  top3_rate: DashboardMetric;
  total_keywords: number;
  total_runs_this_period: number;
  active_llms: string[];
  best_keyword: string | null;
  worst_keyword: string | null;
  best_llm: string | null;
  worst_llm: string | null;
  recent_runs: number;
  pending_runs: number;
  failed_runs: number;
}

export interface LLMBreakdownData {
  provider: string;
  display_name: string;
  avg_score: number;
  mention_rate: number;
  top3_rate: number;
  citation_rate: number;
  total_runs: number;
  trend: "up" | "down" | "stable";
  trend_delta: number | null;
}

export interface KeywordBreakdownData {
  keyword_id: string;
  keyword: string;
  avg_score: number;
  mention_rate: number;
  top3_rate: number;
  best_llm: string;
  worst_llm: string;
  run_count: number;
  last_run_at: string | null;
}

export interface TimeSeriesPoint {
  date: string;
  value: number;
  label?: string;
}

// API Response types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}
