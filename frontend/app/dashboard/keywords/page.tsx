"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { keywordsApi, projectsApi, visibilityApi, llmApi } from "@/lib/api";
import { useProjectStore } from "@/lib/store";
import {
  Plus, Trash2, Search, Upload, ChevronDown, Check, Sparkles, Target,
  Award, TrendingUp, TrendingDown, Minus, X, BarChart3, Eye, Globe,
  CheckCircle, AlertCircle, RefreshCw, ExternalLink, Play, Zap, Filter,
  ArrowUpRight, ArrowDownRight, MoreHorizontal, Flag, Settings, Share2
} from "lucide-react";
import Link from "next/link";

interface KeywordAnalysisSummary {
  brand_mentioned: boolean;
  brand_position: number | null;
  total_brands_found: number;
  total_citations: number;
  our_domain_cited: boolean;
  visibility_score: number;
  top_brands: string[];
  provider: string | null;
  analyzed_at: string | null;
  has_aio: boolean;
  brand_in_aio: boolean;
  domain_in_aio: boolean;
}

interface Keyword {
  id: string;
  keyword: string;
  context: string | null;
  priority: string;
  is_active: boolean;
  created_at: string;
  avg_visibility_score: number | null;
  latest_analysis: KeywordAnalysisSummary | null;
}

interface Project {
  id: string;
  name: string;
  domain: string;
  industry?: string;
  country?: string;
  enabled_llms?: string[];
  brands?: { id: string; name: string; is_primary: boolean }[];
  competitors?: { id: string; name: string }[];
  keyword_count?: number;
  total_runs?: number;
  last_crawl_at?: string | null;
}

// LLM Provider Icons Component
const LLMProviderIcons = ({ providers }: { providers: string[] }) => {
  const providerConfig: Record<string, { color: string; icon: string }> = {
    openai: { color: "bg-green-500", icon: "O" },
    anthropic: { color: "bg-orange-500", icon: "A" },
    google: { color: "bg-blue-500", icon: "G" },
    perplexity: { color: "bg-purple-500", icon: "P" },
    gemini: { color: "bg-blue-400", icon: "G" },
    copilot: { color: "bg-cyan-500", icon: "C" },
    grok: { color: "bg-gray-800", icon: "X" },
    meta: { color: "bg-blue-600", icon: "M" },
  };

  return (
    <div className="flex items-center gap-0.5">
      {providers.slice(0, 4).map((provider, i) => {
        const config = providerConfig[provider.toLowerCase()] || { color: "bg-gray-400", icon: "?" };
        return (
          <div
            key={i}
            className={`w-5 h-5 rounded ${config.color} flex items-center justify-center text-white text-[10px] font-bold`}
            title={provider}
          >
            {config.icon}
          </div>
        );
      })}
      {providers.length > 4 && (
        <span className="text-xs text-gray-400 ml-1">+{providers.length - 4}</span>
      )}
    </div>
  );
};

// Top Brands Display
const TopBrandsDisplay = ({ brands }: { brands: Array<{ name: string; logo?: string }> }) => {
  if (!brands || brands.length === 0) return <span className="text-gray-400">-</span>;

  return (
    <div className="flex items-center gap-1">
      {brands.slice(0, 3).map((brand, i) => (
        <div
          key={i}
          className="w-6 h-6 rounded bg-gray-100 flex items-center justify-center text-xs font-medium text-gray-700 border"
          title={brand.name}
        >
          {brand.name.charAt(0).toUpperCase()}
        </div>
      ))}
      {brands.length > 3 && (
        <span className="text-xs text-gray-400">+{brands.length - 3}</span>
      )}
    </div>
  );
};

export default function KeywordsPage() {
  const queryClient = useQueryClient();
  const { currentProject, setCurrentProject, projects, setProjects } = useProjectStore();
  const [newKeyword, setNewKeyword] = useState("");
  const [bulkKeywords, setBulkKeywords] = useState("");
  const [showBulkAdd, setShowBulkAdd] = useState(false);
  const [showAddKeyword, setShowAddKeyword] = useState(false);
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [showProjectDropdown, setShowProjectDropdown] = useState(false);
  const [selectedProviders, setSelectedProviders] = useState<string[]>(["openai", "anthropic", "google", "perplexity"]);
  const [showProviderDropdown, setShowProviderDropdown] = useState(false);
  const [sortBy, setSortBy] = useState<"rank" | "sov" | "position" | "volume">("rank");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  // Country mapping for display
  const countryInfo: Record<string, { name: string; flag: string }> = {
    "in": { name: "India", flag: "🇮🇳" },
    "us": { name: "United States", flag: "🇺🇸" },
    "uk": { name: "United Kingdom", flag: "🇬🇧" },
    "au": { name: "Australia", flag: "🇦🇺" },
    "ca": { name: "Canada", flag: "🇨🇦" },
    "de": { name: "Germany", flag: "🇩🇪" },
    "fr": { name: "France", flag: "🇫🇷" },
    "jp": { name: "Japan", flag: "🇯🇵" },
    "sg": { name: "Singapore", flag: "🇸🇬" },
    "ae": { name: "UAE", flag: "🇦🇪" },
    "br": { name: "Brazil", flag: "🇧🇷" },
    "mx": { name: "Mexico", flag: "🇲🇽" },
    "nl": { name: "Netherlands", flag: "🇳🇱" },
    "es": { name: "Spain", flag: "🇪🇸" },
    "it": { name: "Italy", flag: "🇮🇹" },
  };

  // Get project's country info
  const projectCountry = currentProject?.country || "in";
  const projectCountryInfo = countryInfo[projectCountry] || { name: projectCountry.toUpperCase(), flag: "🌍" };

  const availableProviders = [
    { id: "openai", name: "OpenAI ChatGPT", color: "bg-green-500", icon: "O" },
    { id: "google_aio", name: "Google AI Overviews", color: "bg-blue-500", icon: "+" },
    { id: "google_mode", name: "Google AI Mode", color: "bg-green-600", icon: "G" },
    { id: "google", name: "Google Gemini", color: "bg-blue-400", icon: "+" },
    { id: "perplexity", name: "Perplexity AI", color: "bg-purple-500", icon: "P" },
    { id: "anthropic", name: "Anthropic Claude", color: "bg-orange-500", icon: "A" },
    { id: "grok", name: "xAI Grok", color: "bg-gray-800", icon: "X" },
    { id: "copilot", name: "Microsoft Copilot", color: "bg-cyan-500", icon: "C" },
    { id: "meta", name: "Meta AI", color: "bg-blue-600", icon: "M" },
  ];

  const toggleProvider = (providerId: string) => {
    setSelectedProviders(prev => {
      if (prev.includes(providerId)) {
        if (prev.length === 1) return prev;
        return prev.filter(p => p !== providerId);
      }
      return [...prev, providerId];
    });
  };

  // Fetch projects
  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const response = await projectsApi.list();
      return response.data;
    },
  });

  useEffect(() => {
    if (projectsData?.items) {
      setProjects(projectsData.items);
      // Auto-select first project if no project is currently selected
      // or if the current project is not in the list (was deleted)
      if (projectsData.items.length > 0) {
        const currentProjectExists = currentProject && projectsData.items.some(
          (p: Project) => p.id === currentProject.id
        );
        if (!currentProjectExists) {
          setCurrentProject(projectsData.items[0]);
        }
      }
    }
  }, [projectsData, currentProject, setCurrentProject, setProjects]);

  // Fetch keywords
  const { data: keywordsData, isLoading } = useQuery({
    queryKey: ["keywords", currentProject?.id, search],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      const response = await keywordsApi.list(currentProject.id, 1, 100, search || undefined);
      return response.data;
    },
    enabled: !!currentProject?.id,
  });

  // Mutations
  const createMutation = useMutation({
    mutationFn: async (keyword: string) => {
      if (!currentProject?.id) throw new Error("No project selected. Please select a project first.");
      console.log("Creating keyword for project:", currentProject.id, "keyword:", keyword);
      try {
        const response = await keywordsApi.create(currentProject.id, { keyword, priority: "medium" });
        return response;
      } catch (err) {
        console.error("API call failed:", err);
        throw err;
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["keywords", currentProject?.id] });
      setNewKeyword("");
      setShowAddKeyword(false);
      setError("");
    },
    onError: (err: unknown) => {
      console.error("Keyword creation error:", err);
      const error = err as { response?: { data?: { detail?: string }; status?: number; statusText?: string }; message?: string; code?: string };

      // Build detailed error message
      let errorMessage = "Failed to add keyword";
      if (error.code === "ERR_NETWORK") {
        errorMessage = "Cannot connect to server. Please ensure the backend is running on http://localhost:8000";
      } else if (error.response?.status === 401) {
        errorMessage = "Authentication failed. Please log in again.";
      } else if (error.response?.status === 404) {
        errorMessage = "Project not found. Please refresh and select a valid project.";
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.message) {
        errorMessage = error.message;
      } else if (error.response?.status) {
        errorMessage = `Server error: ${error.response.status} ${error.response.statusText || ""}`;
      }

      setError(errorMessage);
    },
  });

  const bulkCreateMutation = useMutation({
    mutationFn: async (keywords: string[]) => {
      if (!currentProject?.id) throw new Error("No project selected. Please select a project first.");
      console.log("Creating bulk keywords for project:", currentProject.id, "count:", keywords.length);
      return keywordsApi.createBulk(currentProject.id, { keywords, priority: "medium" });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["keywords", currentProject?.id] });
      setBulkKeywords("");
      setShowBulkAdd(false);
      setError("");
    },
    onError: (err: unknown) => {
      console.error("Bulk keyword creation error:", err);
      const error = err as { response?: { data?: { detail?: string }; status?: number }; message?: string };
      const errorMessage = error.response?.data?.detail
        || error.message
        || `Failed to add keywords (HTTP ${error.response?.status || "unknown"})`;
      setError(errorMessage);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (keywordId: string) => {
      if (!currentProject?.id) throw new Error("No project selected");
      return keywordsApi.delete(currentProject.id, keywordId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["keywords", currentProject?.id] });
    },
  });

  // Run analysis
  const [analysisStatus, setAnalysisStatus] = useState<string | null>(null);

  const runAnalysisMutation = useMutation({
    mutationFn: async (keywordIds?: string[]) => {
      if (!currentProject?.id) throw new Error("No project selected");
      setAnalysisStatus(`Analyzing with ${selectedProviders.length} LLMs for ${projectCountryInfo.name}...`);
      return llmApi.executeSync(currentProject.id, {
        keyword_ids: keywordIds,
        providers: selectedProviders.filter(p => ["openai", "anthropic", "google", "perplexity"].includes(p)),
        // Note: country is now set at project level, no need to pass it
      });
    },
    onSuccess: () => {
      setAnalysisStatus(null);
      queryClient.invalidateQueries({ queryKey: ["keywords", currentProject?.id] });
    },
    onError: (err: unknown) => {
      setAnalysisStatus(null);
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || "Failed to run analysis");
    },
  });

  const handleAddKeyword = (e: React.FormEvent) => {
    e.preventDefault();
    if (newKeyword.trim()) {
      createMutation.mutate(newKeyword.trim());
    }
  };

  const handleBulkAdd = () => {
    const keywords = bulkKeywords.split("\n").map(k => k.trim()).filter(k => k.length > 0);
    if (keywords.length > 0) {
      bulkCreateMutation.mutate(keywords);
    }
  };

  // Calculate mock data for display (will be replaced with real API data)
  const getKeywordMetrics = (keyword: Keyword) => {
    const analysis = keyword.latest_analysis;
    return {
      rank: analysis?.brand_position || null,
      shareOfVoice: analysis ? Math.round(analysis.visibility_score * 0.8) : null,
      position: analysis?.brand_position ? analysis.brand_position.toFixed(1) : null,
      searchVolume: null, // Will come from API
      topBrands: analysis?.top_brands?.map(name => ({ name })) || [],
      hasAIO: analysis?.has_aio || false,
      brandInAIO: analysis?.brand_in_aio || false,
    };
  };

  const allProjects = projects.length > 0 ? projects : (projectsData?.items || []);

  if (!allProjects.length) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-xl shadow-violet-500/30 mb-6">
          <Target className="h-10 w-10 text-white" />
        </div>
        <h2 className="text-xl font-bold text-gray-900 mb-2">No Projects Yet</h2>
        <p className="text-gray-500 mb-6">Create a project to start tracking keywords</p>
        <Link href="/dashboard/projects/new">
          <button className="btn-primary">
            <Plus className="h-4 w-4 mr-2" />
            Create Project
          </button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Keywords</h1>
            <p className="text-gray-500 mt-1">
              Setup your keywords for visibility tracking.
            </p>
          </div>
          {/* Project Selector */}
          <div className="relative">
            <button
              onClick={() => setShowProjectDropdown(!showProjectDropdown)}
              className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
            >
              <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold">
                {currentProject?.name?.charAt(0) || "?"}
              </div>
              <span className="font-medium text-gray-900">{currentProject?.name || "Select Project"}</span>
              <ChevronDown className="h-4 w-4 text-gray-400" />
            </button>

            {showProjectDropdown && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setShowProjectDropdown(false)} />
                <div className="absolute left-0 top-full mt-2 w-64 bg-white rounded-xl shadow-xl ring-1 ring-gray-100 py-2 z-50 max-h-80 overflow-y-auto">
                  {allProjects.map((project: Project) => (
                    <button
                      key={project.id}
                      onClick={() => {
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        setCurrentProject(project as any);
                        setShowProjectDropdown(false);
                      }}
                      className="w-full flex items-center gap-3 px-4 py-2 hover:bg-gray-50 transition-colors"
                    >
                      <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white text-xs font-bold">
                        {project.name.charAt(0)}
                      </div>
                      <div className="flex-1 text-left">
                        <span className="text-sm font-medium text-gray-900">{project.name}</span>
                        <span className="text-xs text-gray-400 block">{project.domain}</span>
                      </div>
                      {currentProject?.id === project.id && (
                        <Check className="w-4 h-4 text-green-500" />
                      )}
                    </button>
                  ))}
                  <div className="border-t border-gray-100 mt-2 pt-2">
                    <Link
                      href="/dashboard/projects/new"
                      className="w-full flex items-center gap-3 px-4 py-2 hover:bg-gray-50 transition-colors text-violet-600"
                      onClick={() => setShowProjectDropdown(false)}
                    >
                      <Plus className="w-4 h-4" />
                      <span className="text-sm font-medium">Create New Project</span>
                    </Link>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
        <button
          onClick={() => setShowAddKeyword(true)}
          className="btn-primary"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Keywords
        </button>
      </div>

      {/* Analysis Status */}
      {analysisStatus && (
        <div className="bg-violet-50 border border-violet-200 rounded-xl p-4 flex items-center gap-3">
          <RefreshCw className="h-5 w-5 text-violet-600 animate-spin" />
          <span className="text-violet-700 font-medium">{analysisStatus}</span>
        </div>
      )}

      {error && (
        <div className="bg-rose-50 text-rose-600 px-4 py-3 rounded-xl text-sm ring-1 ring-rose-200 flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError("")}><X className="w-4 h-4" /></button>
        </div>
      )}

      {/* Keywords Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {/* Table Header with Controls */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">
              {keywordsData?.total || 0} keywords
            </span>
          </div>
          <div className="flex items-center gap-3">
            {/* Project Country Display */}
            <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
              <Globe className="w-4 h-4 text-gray-400" />
              <span className="text-gray-600">
                {projectCountryInfo.flag} {projectCountryInfo.name}
              </span>
              <Link
                href={`/dashboard/projects/${currentProject?.id}`}
                className="text-violet-500 hover:text-violet-600 text-xs ml-1"
                title="Change country in project settings"
              >
                (edit)
              </Link>
            </div>

            {/* LLM Provider Filter */}
            <div className="relative">
              <button
                onClick={() => setShowProviderDropdown(!showProviderDropdown)}
                className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors text-sm"
              >
                <span className="text-gray-600">AI Search Engines</span>
                <div className="flex -space-x-1">
                  {selectedProviders.slice(0, 4).map(p => {
                    const provider = availableProviders.find(ap => ap.id === p);
                    return (
                      <div
                        key={p}
                        className={`w-5 h-5 rounded ${provider?.color || "bg-gray-400"} flex items-center justify-center text-white text-[10px] font-bold ring-1 ring-white`}
                      >
                        {provider?.icon || "?"}
                      </div>
                    );
                  })}
                </div>
                <ChevronDown className="h-4 w-4 text-gray-400" />
              </button>

              {showProviderDropdown && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setShowProviderDropdown(false)} />
                  <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-xl shadow-xl ring-1 ring-gray-100 py-2 z-50">
                    {availableProviders.map(provider => (
                      <button
                        key={provider.id}
                        onClick={() => toggleProvider(provider.id)}
                        className="w-full flex items-center gap-3 px-4 py-2 hover:bg-gray-50 transition-colors"
                      >
                        <div className={`w-5 h-5 rounded ${provider.color} flex items-center justify-center text-white text-[10px] font-bold`}>
                          {provider.icon}
                        </div>
                        <span className="flex-1 text-left text-sm text-gray-700">{provider.name}</span>
                        {selectedProviders.includes(provider.id) && (
                          <Check className="w-4 h-4 text-green-500" />
                        )}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {/* Run Analysis Button */}
            <button
              onClick={() => runAnalysisMutation.mutate(undefined)}
              disabled={runAnalysisMutation.isPending || !keywordsData?.items?.length}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors disabled:opacity-50 text-sm font-medium"
            >
              {runAnalysisMutation.isPending ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                <Zap className="h-4 w-4" />
              )}
              Run Analysis
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Keyword
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700" onClick={() => setSortBy("rank")}>
                  <div className="flex items-center justify-center gap-1">
                    Rank
                    {sortBy === "rank" && <ChevronDown className="w-3 h-3" />}
                  </div>
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700" onClick={() => setSortBy("sov")}>
                  <div className="flex items-center justify-center gap-1">
                    Share of Voice
                    {sortBy === "sov" && <ChevronDown className="w-3 h-3" />}
                  </div>
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider cursor-pointer hover:text-gray-700" onClick={() => setSortBy("position")}>
                  <div className="flex items-center justify-center gap-1">
                    Position
                    {sortBy === "position" && <ChevronDown className="w-3 h-3" />}
                  </div>
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Search Volume
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Top Brands
                </th>
                <th className="text-center px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-20">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    <td colSpan={7} className="px-6 py-4">
                      <div className="h-8 bg-gray-100 rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : keywordsData?.items?.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <Target className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                    <p className="text-gray-500 font-medium">No keywords yet</p>
                    <p className="text-gray-400 text-sm mt-1">Add your first keyword to start tracking</p>
                  </td>
                </tr>
              ) : (
                keywordsData?.items?.map((keyword: Keyword) => {
                  const metrics = getKeywordMetrics(keyword);
                  return (
                    <tr
                      key={keyword.id}
                      className="hover:bg-gray-50 cursor-pointer group"
                      onClick={() => window.location.href = `/dashboard/keywords/${keyword.id}`}
                    >
                      {/* Keyword */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <span className="font-medium text-gray-900">{keyword.keyword}</span>
                          {keyword.context && (
                            <span className="inline-flex items-center gap-1 text-xs text-gray-400">
                              <Flag className="w-3 h-3" />
                              {keyword.context.substring(0, 2).toUpperCase()}
                            </span>
                          )}
                          {metrics.hasAIO && (
                            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium ${
                              metrics.brandInAIO ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
                            }`}>
                              AIO
                              {metrics.brandInAIO ? (
                                <CheckCircle className="w-3 h-3" />
                              ) : (
                                <X className="w-3 h-3" />
                              )}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Rank */}
                      <td className="px-4 py-4 text-center">
                        {metrics.rank ? (
                          <span className={`inline-flex items-center justify-center w-8 h-8 rounded-lg font-bold text-sm ${
                            metrics.rank <= 3 ? "bg-green-100 text-green-700" :
                            metrics.rank <= 10 ? "bg-blue-100 text-blue-700" :
                            "bg-gray-100 text-gray-600"
                          }`}>
                            #{metrics.rank}
                          </span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>

                      {/* Share of Voice */}
                      <td className="px-4 py-4">
                        {metrics.shareOfVoice !== null ? (
                          <div className="flex items-center justify-center gap-2">
                            <span className={`font-semibold ${
                              metrics.shareOfVoice >= 50 ? "text-green-600" :
                              metrics.shareOfVoice >= 25 ? "text-amber-600" :
                              "text-gray-600"
                            }`}>
                              {metrics.shareOfVoice}%
                            </span>
                            <div className="w-16 bg-gray-200 rounded-full h-1.5 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  metrics.shareOfVoice >= 50 ? "bg-green-500" :
                                  metrics.shareOfVoice >= 25 ? "bg-amber-500" :
                                  "bg-gray-400"
                                }`}
                                style={{ width: `${metrics.shareOfVoice}%` }}
                              />
                            </div>
                          </div>
                        ) : (
                          <span className="text-gray-400 text-center block">-</span>
                        )}
                      </td>

                      {/* Position */}
                      <td className="px-4 py-4 text-center">
                        {metrics.position ? (
                          <span className="text-gray-700 font-medium">{metrics.position}</span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>

                      {/* Search Volume */}
                      <td className="px-4 py-4 text-center">
                        {metrics.searchVolume ? (
                          <span className="text-gray-700">{metrics.searchVolume}/mo</span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>

                      {/* Top Brands */}
                      <td className="px-4 py-4">
                        <div className="flex justify-center">
                          <TopBrandsDisplay brands={metrics.topBrands} />
                        </div>
                      </td>

                      {/* Actions */}
                      <td className="px-4 py-4">
                        <div className="flex items-center justify-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              runAnalysisMutation.mutate([keyword.id]);
                            }}
                            disabled={runAnalysisMutation.isPending}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-green-500 hover:bg-green-50 transition-colors"
                            title="Run Analysis"
                          >
                            <Play className="h-4 w-4" />
                          </button>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteMutation.mutate(keyword.id);
                            }}
                            className="p-1.5 rounded-lg text-gray-400 hover:text-rose-500 hover:bg-rose-50 transition-colors"
                            title="Delete"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Keyword Modal */}
      {showAddKeyword && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">Add Keywords</h2>
              <button onClick={() => setShowAddKeyword(false)} className="p-2 hover:bg-gray-100 rounded-lg">
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="p-6">
              {/* Single Keyword */}
              <form onSubmit={handleAddKeyword} className="mb-6">
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Add a keyword
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newKeyword}
                    onChange={(e) => setNewKeyword(e.target.value)}
                    placeholder="e.g., best hr software in india"
                    className="flex-1 px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                  />
                  <button
                    type="submit"
                    disabled={createMutation.isPending}
                    className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors disabled:opacity-50"
                  >
                    Add
                  </button>
                </div>
              </form>

              {/* Bulk Add */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Or add multiple keywords (one per line)
                </label>
                <textarea
                  value={bulkKeywords}
                  onChange={(e) => setBulkKeywords(e.target.value)}
                  placeholder="best hr software in india&#10;payroll software india&#10;employee management system"
                  className="w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent min-h-[150px] font-mono text-sm"
                />
                <button
                  onClick={handleBulkAdd}
                  disabled={bulkCreateMutation.isPending || !bulkKeywords.trim()}
                  className="mt-3 w-full px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors disabled:opacity-50"
                >
                  {bulkCreateMutation.isPending ? "Adding..." : "Add All Keywords"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Click outside to close dropdowns */}
      {showProjectDropdown && (
        <div className="fixed inset-0 z-40" onClick={() => setShowProjectDropdown(false)} />
      )}
    </div>
  );
}
