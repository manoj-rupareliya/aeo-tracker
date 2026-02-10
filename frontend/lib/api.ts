/**
 * API Client for llmrefs.com
 */

import axios, { AxiosInstance, AxiosError } from "axios";
import Cookies from "js-cookie";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Create axios instance
const api: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    "Content-Type": "application/json",
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

export default api;
