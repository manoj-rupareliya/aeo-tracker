/**
 * API Client for llmscm.com
 */

import axios, { AxiosInstance, AxiosError } from "axios";
import Cookies from "js-cookie";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
    "bypass-tunnel-reminder": "true", // For localtunnel
  },
});

// Request interceptor for auth
api.interceptors.request.use(
  (config) => {
    const token = Cookies.get("access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && originalRequest) {
      const refreshToken = Cookies.get("refresh_token");

      if (refreshToken) {
        try {
          const response = await axios.post(
            `${API_BASE_URL}/api/v1/auth/refresh`,
            { refresh_token: refreshToken }
          );

          const { access_token, refresh_token } = response.data;
          Cookies.set("access_token", access_token, { expires: 1 });
          Cookies.set("refresh_token", refresh_token, { expires: 7 });

          originalRequest.headers.Authorization = `Bearer ${access_token}`;
          return api(originalRequest);
        } catch (refreshError) {
          // Refresh failed, redirect to login
          Cookies.remove("access_token");
          Cookies.remove("refresh_token");
          window.location.href = "/auth/login";
        }
      }
    }

    return Promise.reject(error);
  }
);

// Auth API
export const authApi = {
  register: (data: { email: string; password: string; full_name: string }) =>
    api.post("/auth/register", data),

  login: (data: { email: string; password: string }) =>
    api.post("/auth/login", data),

  refresh: (refreshToken: string) =>
    api.post("/auth/refresh", { refresh_token: refreshToken }),

  getMe: () => api.get("/auth/me"),

  // API Key management
  listApiKeys: () => api.get("/auth/api-keys"),

  saveApiKey: (data: { provider: string; api_key: string }) =>
    api.post("/auth/api-keys", data),

  deleteApiKey: (provider: string) =>
    api.delete(`/auth/api-keys/${provider}`),
};

// Projects API
export const projectsApi = {
  list: (page = 1, pageSize = 20) =>
    api.get("/projects", { params: { page, page_size: pageSize } }),

  get: (projectId: string) => api.get(`/projects/${projectId}`),

  create: (data: {
    name: string;
    domain: string;
    industry: string;
    country?: string;
    brands?: { name: string; is_primary?: boolean; aliases?: string[] }[];
    competitors?: { name: string; domain?: string }[];
  }) => api.post("/projects", data),

  update: (projectId: string, data: Record<string, unknown>) =>
    api.put(`/projects/${projectId}`, data),

  delete: (projectId: string) => api.delete(`/projects/${projectId}`),

  addBrand: (projectId: string, data: { name: string; is_primary?: boolean; aliases?: string[] }) =>
    api.post(`/projects/${projectId}/brands`, data),

  deleteBrand: (projectId: string, brandId: string) =>
    api.delete(`/projects/${projectId}/brands/${brandId}`),

  addCompetitor: (projectId: string, data: { name: string; domain?: string }) =>
    api.post(`/projects/${projectId}/competitors`, data),

  deleteCompetitor: (projectId: string, competitorId: string) =>
    api.delete(`/projects/${projectId}/competitors/${competitorId}`),
};

// Keywords API
export const keywordsApi = {
  list: (projectId: string, page = 1, pageSize = 50, search?: string) =>
    api.get(`/keywords/${projectId}`, { params: { page, page_size: pageSize, search } }),

  get: (projectId: string, keywordId: string) =>
    api.get(`/keywords/${projectId}/${keywordId}`),

  create: (projectId: string, data: { keyword: string; context?: string; priority?: string }) =>
    api.post(`/keywords/${projectId}`, data),

  createBulk: (projectId: string, data: { keywords: string[]; priority?: string }) =>
    api.post(`/keywords/${projectId}/bulk`, data),

  update: (projectId: string, keywordId: string, data: Record<string, unknown>) =>
    api.put(`/keywords/${projectId}/${keywordId}`, data),

  delete: (projectId: string, keywordId: string) =>
    api.delete(`/keywords/${projectId}/${keywordId}`),
};

// Prompts API
export const promptsApi = {
  listTemplates: (promptType?: string) =>
    api.get("/prompts/templates", { params: { prompt_type: promptType } }),

  generate: (projectId: string, data: { keyword_ids: string[]; prompt_types?: string[] }) =>
    api.post(`/prompts/${projectId}/generate`, data),

  getForKeyword: (projectId: string, keywordId: string) =>
    api.get(`/prompts/${projectId}/keyword/${keywordId}`),
};

// LLM Execution API
export const llmApi = {
  execute: (projectId: string, data: {
    keyword_ids?: string[];
    providers?: string[];
    prompt_types?: string[];
    force_refresh?: boolean;
  }) => api.post(`/llm/${projectId}/execute`, data),

  // Synchronous execution for local development (no Celery/Redis required)
  // Note: Country is now set at project level, no need to pass it
  executeSync: (projectId: string, data: {
    keyword_ids?: string[];
    provider?: string;
    providers?: string[];  // Multiple providers for parallel analysis
  }) => api.post(`/llm/${projectId}/execute-sync`, data, { timeout: 180000 }),  // 3 min timeout for multiple providers

  listRuns: (projectId: string, params?: { status?: string; provider?: string; page?: number }) =>
    api.get(`/llm/${projectId}/runs`, { params }),

  getRunDetail: (projectId: string, runId: string) =>
    api.get(`/llm/${projectId}/runs/${runId}`),

  getStatus: (projectId: string) => api.get(`/llm/${projectId}/status`),

  retryRun: (projectId: string, runId: string) =>
    api.post(`/llm/${projectId}/runs/${runId}/retry`),
};

// Analysis API
export const analysisApi = {
  getScores: (projectId: string, params?: {
    keyword_id?: string;
    provider?: string;
    start_date?: string;
    end_date?: string;
    page?: number;
  }) => api.get(`/analysis/${projectId}/scores`, { params }),

  getAggregated: (projectId: string, periodType = "daily", limit = 30) =>
    api.get(`/analysis/${projectId}/aggregated`, { params: { period_type: periodType, limit } }),

  getMentions: (projectId: string, params?: {
    is_own_brand?: boolean;
    page?: number;
  }) => api.get(`/analysis/${projectId}/mentions`, { params }),

  getCitations: (projectId: string, params?: {
    is_hallucinated?: boolean;
    page?: number;
  }) => api.get(`/analysis/${projectId}/citations`, { params }),

  getSources: (projectId: string, limit = 50) =>
    api.get(`/analysis/${projectId}/sources`, { params: { limit } }),

  getReport: (projectId: string, days = 30) =>
    api.get(`/analysis/${projectId}/report`, { params: { days } }),
};

// Dashboard API
export const dashboardApi = {
  getOverview: (projectId: string) =>
    api.get(`/dashboard/${projectId}/overview`),

  getLLMBreakdown: (projectId: string, days = 30) =>
    api.get(`/dashboard/${projectId}/llm-breakdown`, { params: { days } }),

  getKeywordBreakdown: (projectId: string, days = 30, limit = 20) =>
    api.get(`/dashboard/${projectId}/keyword-breakdown`, { params: { days, limit } }),

  getTimeSeries: (projectId: string, metric = "visibility_score", granularity = "daily", days = 30) =>
    api.get(`/dashboard/${projectId}/time-series`, { params: { metric, granularity, days } }),
};

// Visibility Analytics API
export const visibilityApi = {
  // Dashboard
  getDashboard: (projectId: string, days = 30) =>
    api.get(`/visibility/dashboard/${projectId}`, { params: { days } }),

  // Share of Voice
  getShareOfVoice: (projectId: string, days = 30) =>
    api.get(`/visibility/sov/${projectId}`, { params: { days } }),

  getSovByKeyword: (projectId: string, days = 30) =>
    api.get(`/visibility/sov/${projectId}/by-keyword`, { params: { days } }),

  getSovByLlm: (projectId: string, days = 30) =>
    api.get(`/visibility/sov/${projectId}/by-llm`, { params: { days } }),

  // Position Tracking
  getPositionSummary: (projectId: string, days = 30) =>
    api.get(`/visibility/positions/${projectId}`, { params: { days } }),

  getEntityRanking: (projectId: string, days = 30) =>
    api.get(`/visibility/positions/${projectId}/ranking`, { params: { days } }),

  // Citations
  getCitationSummary: (projectId: string, days = 30) =>
    api.get(`/visibility/citations/${projectId}`, { params: { days } }),

  getCitationSources: (projectId: string, limit = 20) =>
    api.get(`/visibility/citations/${projectId}/sources`, { params: { limit } }),

  // Keyword Analysis
  getKeywordAnalyses: (projectId: string, limit = 50) =>
    api.get(`/visibility/analysis/${projectId}/keywords`, { params: { limit } }),

  getKeywordAnalysisDetail: (projectId: string, keywordId: string) =>
    api.get(`/visibility/analysis/${projectId}/keyword/${keywordId}`),

  // Outreach Opportunities
  getOutreachOpportunities: (projectId: string, status?: string, limit = 20) =>
    api.get(`/visibility/opportunities/${projectId}`, { params: { status, limit } }),

  generateOpportunities: (projectId: string, minCitations = 3) =>
    api.post(`/visibility/opportunities/${projectId}/generate`, {}, { params: { min_citations: minCitations } }),

  updateOpportunityStatus: (opportunityId: string, status: string, notes?: string) =>
    api.patch(`/visibility/opportunities/${opportunityId}/status`, { status, notes }),

  // Content Gaps
  getContentGaps: (projectId: string, priority?: string, addressed = false, limit = 20) =>
    api.get(`/visibility/gaps/${projectId}`, { params: { priority, addressed, limit } }),

  detectContentGaps: (projectId: string) =>
    api.post(`/visibility/gaps/${projectId}/detect`),

  markGapAddressed: (gapId: string, addressedUrl: string) =>
    api.patch(`/visibility/gaps/${gapId}/address`, { addressed_url: addressedUrl }),

  // AI Prompt Volume
  getPromptVolume: (projectId: string) =>
    api.get(`/visibility/volume/${projectId}`),

  generateVolumeEstimates: (projectId: string) =>
    api.post(`/visibility/volume/${projectId}/estimate`),

  getVolumeSummary: (projectId: string) =>
    api.get(`/visibility/volume/${projectId}/summary`),

  // Keyword Rankings
  getKeywordRankings: (projectId: string, days = 30) =>
    api.get(`/visibility/rankings/${projectId}`, { params: { days } }),

  getKeywordRankingDetail: (projectId: string, keywordId: string, days = 30) =>
    api.get(`/visibility/rankings/${projectId}/keyword/${keywordId}`, { params: { days } }),

  // Keyword Ranking Results (who ranked in top positions with citations)
  getKeywordRankingResults: (projectId: string, keywordId: string, days = 30) =>
    api.get(`/visibility/ranking-results/${projectId}/keyword/${keywordId}`, { params: { days } }),

  getAllRankingResults: (projectId: string, days = 30, limit = 50) =>
    api.get(`/visibility/ranking-results/${projectId}`, { params: { days, limit } }),
};

// Google AI Overview (AIO) API
export const aioApi = {
  // Test API connection
  testConnection: () => api.get("/aio/test"),

  // Get AIO data for a specific keyword
  // Note: Country is now set at project level
  getForKeyword: (projectId: string, keywordId: string, forceRefresh = false) =>
    api.get(`/aio/${projectId}/keyword/${keywordId}`, {
      params: { force_refresh: forceRefresh }
    }),

  // Analyze multiple keywords for AIO
  // Note: Country is now set at project level
  analyzeBulk: (projectId: string, data: { keyword_ids?: string[] }) =>
    api.post(`/aio/${projectId}/analyze-bulk`, data),

  // Get AIO history for a keyword
  getHistory: (projectId: string, keywordId: string, days = 30) =>
    api.get(`/aio/${projectId}/history/${keywordId}`, { params: { days } }),

  // Get AIO summary for project
  getSummary: (projectId: string) =>
    api.get(`/aio/${projectId}/summary`),
};

export default api;
