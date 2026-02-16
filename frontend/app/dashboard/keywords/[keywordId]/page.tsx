"use client";

import React, { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { keywordsApi, visibilityApi, analysisApi, aioApi } from "@/lib/api";
import { useProjectStore } from "@/lib/store";
import {
  ArrowLeft, Download, Share2, ChevronDown, Check, ExternalLink,
  TrendingUp, TrendingDown, Minus, RefreshCw, Settings, ShoppingCart,
  FileText, Link2, BarChart3, CheckCircle, AlertCircle, Globe, AlertTriangle,
  Search, Sparkles, Eye
} from "lucide-react";
import Link from "next/link";

// LLM Provider Configuration
const llmProviders = [
  { id: "openai", name: "OpenAI ChatGPT", color: "bg-green-500", lineColor: "#22c55e" },
  { id: "google_aio", name: "Google AI Overviews", color: "bg-blue-500", lineColor: "#3b82f6" },
  { id: "google_mode", name: "Google AI Mode", color: "bg-green-600", lineColor: "#16a34a" },
  { id: "google", name: "Google Gemini", color: "bg-blue-400", lineColor: "#60a5fa" },
  { id: "perplexity", name: "Perplexity AI", color: "bg-purple-500", lineColor: "#a855f7" },
  { id: "anthropic", name: "Anthropic Claude", color: "bg-orange-500", lineColor: "#f97316" },
  { id: "grok", name: "xAI Grok", color: "bg-gray-800", lineColor: "#1f2937" },
  { id: "copilot", name: "Microsoft Copilot", color: "bg-cyan-500", lineColor: "#06b6d4" },
  { id: "meta", name: "Meta AI", color: "bg-blue-600", lineColor: "#2563eb" },
];

// Position Trend Chart Component
const PositionTrendChart = ({ data, providers }: {
  data: { date: string; positions: Record<string, number | null> }[];
  providers: typeof llmProviders;
}) => {
  const width = 800;
  const height = 250;
  const padding = { top: 20, right: 20, bottom: 40, left: 50 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  // Generate mock data if none provided
  const chartData = data.length > 0 ? data : Array.from({ length: 12 }, (_, i) => ({
    date: new Date(2025, 10 - i, 1).toLocaleDateString("en-US", { month: "short", day: "numeric" }),
    positions: {
      openai: Math.floor(Math.random() * 5) + 2,
      anthropic: Math.floor(Math.random() * 6) + 3,
      google: Math.floor(Math.random() * 7) + 4,
      perplexity: Math.floor(Math.random() * 8) + 5,
    }
  })).reverse();

  const maxPosition = 15;
  const minPosition = 1;

  const getY = (position: number) => {
    return padding.top + ((position - minPosition) / (maxPosition - minPosition)) * chartHeight;
  };

  const getX = (index: number) => {
    return padding.left + (index / (chartData.length - 1)) * chartWidth;
  };

  const createPath = (providerId: string) => {
    const points = chartData
      .map((d, i) => {
        const pos = (d.positions as Record<string, number | null>)[providerId];
        if (pos === null || pos === undefined) return null;
        return `${i === 0 ? "M" : "L"} ${getX(i)} ${getY(pos)}`;
      })
      .filter(Boolean)
      .join(" ");
    return points;
  };

  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[600px]">
        {/* Grid lines */}
        {[1, 3, 5, 7, 10, 15].map((pos) => (
          <g key={pos}>
            <line
              x1={padding.left}
              y1={getY(pos)}
              x2={width - padding.right}
              y2={getY(pos)}
              stroke="#e5e7eb"
              strokeDasharray="4"
            />
            <text
              x={padding.left - 10}
              y={getY(pos)}
              textAnchor="end"
              dominantBaseline="middle"
              className="text-xs fill-gray-400"
            >
              #{pos}
            </text>
          </g>
        ))}

        {/* X-axis labels */}
        {chartData.map((d, i) => (
          i % 2 === 0 && (
            <text
              key={i}
              x={getX(i)}
              y={height - 10}
              textAnchor="middle"
              className="text-xs fill-gray-400"
            >
              {d.date}
            </text>
          )
        ))}

        {/* Lines */}
        {providers.slice(0, 4).map((provider) => (
          <path
            key={provider.id}
            d={createPath(provider.id)}
            fill="none"
            stroke={provider.lineColor}
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ))}

        {/* Data points */}
        {providers.slice(0, 4).map((provider) => (
          chartData.map((d, i) => {
            const pos = (d.positions as Record<string, number | null>)[provider.id];
            if (pos === null || pos === undefined) return null;
            return (
              <circle
                key={`${provider.id}-${i}`}
                cx={getX(i)}
                cy={getY(pos)}
                r="4"
                fill={provider.lineColor}
                stroke="white"
                strokeWidth="2"
              />
            );
          })
        ))}
      </svg>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-4">
        {providers.slice(0, 4).map((provider) => (
          <div key={provider.id} className="flex items-center gap-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: provider.lineColor }}
            />
            <span className="text-sm text-gray-600">{provider.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

// Interfaces for API response data
interface ApiRankedEntity {
  position: number;
  name: string;
  mentioned_text: string;
  is_own_brand: boolean;
  context?: string;
  sentiment: string;
  sentiment_score?: number;
  match_type?: string;
  match_confidence?: number;
}

interface ApiCitation {
  position: number;
  url: string;
  domain?: string;
  category?: string;
  domain_authority?: number;
  anchor_text?: string;
  context?: string;
  is_valid?: boolean;
  is_accessible?: boolean;
  is_hallucinated?: boolean;
  is_our_domain?: boolean;
}

interface ApiLlmResult {
  provider: string;
  model: string;
  last_run: string;
  raw_response?: string;
  ranked_entities: ApiRankedEntity[];
  citations: ApiCitation[];
  our_brand_position?: number;
  our_brand_mentioned: boolean;
  total_brands_mentioned: number;
  visibility_score?: number;
  mention_type?: string;
  competitors_mentioned?: Array<{ name: string; position?: number }>;
  fan_out_queries?: string[];
  has_shopping_recommendations?: boolean;
}

interface ApiRankingResponse {
  keyword_id: string;
  keyword: string;
  project_domain: string;
  analysis_period_days: number;
  results_by_llm: Record<string, ApiLlmResult>;
  summary: {
    total_llms_analyzed: number;
    llms_mentioning_us: number;
    best_position?: number;
    total_citations_across_llms: number;
  };
}

// UI display interfaces
interface BrandCitation {
  url: string;
  fullUrl: string;
  domain: string;
  pageTitle: string;
  contentType: string;
  httpStatus: number;
  isAccessible: boolean;
  anchorText?: string;
  citedBy: string[];
  position: number;
  mentionContext?: string;
  sentiment?: "positive" | "neutral" | "negative";
  lastCrawled?: string;
}

interface BrandRanking {
  rank: number;
  trend: number;
  name: string;
  domain: string;
  shareOfVoice: number;
  position: number;
  citations: number;
  logo?: string;
  isOwnBrand?: boolean;
  citationDetails?: BrandCitation[];
}

interface SourceData {
  rank: number;
  name: string;
  url: string;
  fullUrl: string;
  mentionRate: number;
  position: number;
  brandsCount: number;
  logo?: string;
  pageTitle?: string;
  domain?: string;
  lastCrawled?: string;
  isAccessible?: boolean;
  httpStatus?: number;
  contentType?: string;
  anchorText?: string;
  citedBy?: string[];
}

export default function KeywordDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const keywordId = params.keywordId as string;
  const { currentProject } = useProjectStore();

  const [activeTab, setActiveTab] = useState<"rankings" | "prompts" | "sources" | "google_aio" | "shopping" | "settings">("rankings");
  const [selectedProviders, setSelectedProviders] = useState<string[]>(llmProviders.map(p => p.id));
  const [showProviderDropdown, setShowProviderDropdown] = useState(false);
  const [expandedPrompts, setExpandedPrompts] = useState<number[]>([]);
  const [expandedBrands, setExpandedBrands] = useState<number[]>([]);
  const [sourcesLimit, setSourcesLimit] = useState(20);
  const [brandsLimit, setBrandsLimit] = useState(20);
  const [isLoadingAio, setIsLoadingAio] = useState(false);

  // Country mapping for display (country is set at project level)
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
  };

  // Get project's country info
  const projectCountry = (currentProject as { country?: string })?.country || "in";
  const projectCountryInfo = countryInfo[projectCountry] || { name: projectCountry.toUpperCase(), flag: "🌍" };

  // Fetch keyword details
  const { data: keywordData, isLoading: keywordLoading } = useQuery({
    queryKey: ["keyword", currentProject?.id, keywordId],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      const response = await keywordsApi.get(currentProject.id, keywordId);
      return response.data;
    },
    enabled: !!currentProject?.id && !!keywordId,
  });

  // Fetch ranking results from API - this contains real data from LLM responses
  const { data: rankingData, isLoading: rankingLoading, error: rankingError } = useQuery({
    queryKey: ["keyword-ranking-results", currentProject?.id, keywordId],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      const response = await visibilityApi.getKeywordRankingResults(currentProject.id, keywordId);
      return response.data as ApiRankingResponse;
    },
    enabled: !!currentProject?.id && !!keywordId,
  });

  // Fetch citation sources for this project
  const { data: citationSourcesData } = useQuery({
    queryKey: ["citation-sources", currentProject?.id],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      const response = await visibilityApi.getCitationSources(currentProject.id, 100);
      return response.data;
    },
    enabled: !!currentProject?.id,
  });

  // Fetch Google AI Overview data (uses project country)
  const { data: aioData, isLoading: aioLoading, refetch: refetchAio } = useQuery({
    queryKey: ["aio-data", currentProject?.id, keywordId, projectCountry],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      try {
        const response = await aioApi.getForKeyword(currentProject.id, keywordId, false);
        return response.data;
      } catch (error: unknown) {
        // Return null if no data yet
        if ((error as { response?: { status?: number } })?.response?.status === 400) {
          return null;
        }
        throw error;
      }
    },
    enabled: !!currentProject?.id && !!keywordId && activeTab === "google_aio",
    retry: false,
  });

  // Function to fetch fresh AIO data (uses project country)
  const fetchFreshAio = async () => {
    if (!currentProject?.id) return;
    setIsLoadingAio(true);
    try {
      await aioApi.getForKeyword(currentProject.id, keywordId, true);
      await refetchAio();
    } catch (error) {
      console.error("Error fetching AIO:", error);
    } finally {
      setIsLoadingAio(false);
    }
  };

  // Get project domain for own brand detection
  const projectDomain = currentProject?.domain?.replace("www.", "").toLowerCase() || "";
  const projectBrandName = currentProject?.name || projectDomain.split(".")[0] || "";

  // Transform API data to UI display format
  const { displayRankings, allCitations, allSources } = useMemo(() => {
    if (!rankingData?.results_by_llm) {
      return { displayRankings: [], allCitations: [], allSources: [] };
    }

    // Collect all entities (brands) mentioned across all LLMs
    const entityMap = new Map<string, {
      name: string;
      positions: number[];
      isOwnBrand: boolean;
      citations: BrandCitation[];
      llmsCiting: string[];
      sentiments: string[];
      contexts: string[];
    }>();

    // Collect all citations across all LLMs
    const citationMap = new Map<string, {
      url: string;
      domain: string;
      category: string;
      isAccessible: boolean;
      isOurDomain: boolean;
      anchorText?: string;
      context?: string;
      citedBy: string[];
      positions: number[];
    }>();

    // Process each LLM's results
    Object.entries(rankingData.results_by_llm).forEach(([provider, result]) => {
      // Process ranked entities (brands)
      result.ranked_entities.forEach((entity) => {
        const key = entity.name.toLowerCase();
        if (!entityMap.has(key)) {
          entityMap.set(key, {
            name: entity.name,
            positions: [],
            isOwnBrand: entity.is_own_brand,
            citations: [],
            llmsCiting: [],
            sentiments: [],
            contexts: [],
          });
        }
        const data = entityMap.get(key)!;
        data.positions.push(entity.position);
        data.llmsCiting.push(provider);
        if (entity.sentiment) data.sentiments.push(entity.sentiment);
        if (entity.context) data.contexts.push(entity.context);
      });

      // Process citations
      result.citations.forEach((citation) => {
        if (!citation.url) return; // Skip empty citations
        const key = citation.url.toLowerCase();

        // Safely extract domain
        let domain = citation.domain || "";
        if (!domain && citation.url) {
          try {
            if (citation.url.startsWith("http")) {
              domain = new URL(citation.url).hostname.replace("www.", "");
            } else {
              domain = citation.url.split("/")[0].replace("www.", "");
            }
          } catch {
            domain = citation.url.split("/")[0];
          }
        }

        if (!citationMap.has(key)) {
          citationMap.set(key, {
            url: citation.url,
            domain: domain,
            category: citation.category || "unknown",
            isAccessible: citation.is_accessible ?? true,
            isOurDomain: citation.is_our_domain || false,
            anchorText: citation.anchor_text,
            context: citation.context,
            citedBy: [],
            positions: [],
          });
        }
        const data = citationMap.get(key)!;
        data.citedBy.push(provider);
        if (citation.position) data.positions.push(citation.position);
      });
    });

    // Convert entity map to BrandRanking array
    const rankings: BrandRanking[] = Array.from(entityMap.entries()).map(([key, data], index) => {
      const avgPosition = data.positions.length > 0
        ? data.positions.reduce((a, b) => a + b, 0) / data.positions.length
        : 0;

      // Get citations relevant to this brand from the citation map
      const brandCitations: BrandCitation[] = Array.from(citationMap.entries())
        .filter(([_, cit]) => cit.citedBy.some(p => data.llmsCiting.includes(p)))
        .slice(0, 20)
        .map(([_, cit], i) => ({
          url: cit.url,
          fullUrl: cit.url.startsWith("http") ? cit.url : `https://${cit.url}`,
          domain: cit.domain,
          pageTitle: cit.anchorText || `${cit.domain} - Citation`,
          contentType: cit.category,
          httpStatus: cit.isAccessible ? 200 : 404,
          isAccessible: cit.isAccessible,
          anchorText: cit.anchorText,
          citedBy: Array.from(new Set(cit.citedBy)),
          position: cit.positions.length > 0 ? cit.positions[0] : i + 1,
          mentionContext: data.contexts[0] || undefined,
          sentiment: (data.sentiments[0] as "positive" | "neutral" | "negative") || "neutral",
          lastCrawled: new Date().toISOString().split('T')[0],
        }));

      return {
        rank: index + 1,
        trend: 0, // Would need historical data to calculate
        name: data.name,
        domain: key.includes(".") ? key : `${key}.com`,
        shareOfVoice: Math.round((data.llmsCiting.length / Object.keys(rankingData.results_by_llm).length) * 100),
        position: Math.round(avgPosition * 10) / 10,
        citations: brandCitations.length,
        isOwnBrand: data.isOwnBrand,
        citationDetails: brandCitations,
      };
    });

    // Sort by position (best position first)
    rankings.sort((a, b) => {
      if (a.isOwnBrand) return -1;
      if (b.isOwnBrand) return 1;
      return a.position - b.position;
    });

    // Re-assign ranks after sorting
    rankings.forEach((r, i) => r.rank = i + 1);

    // Convert citation map to SourceData array
    const sources: SourceData[] = Array.from(citationMap.entries()).map(([_, data], index) => ({
      rank: index + 1,
      name: data.domain.split(".")[0] || data.domain,
      url: data.url,
      fullUrl: data.url.startsWith("http") ? data.url : `https://${data.url}`,
      mentionRate: Math.round((data.citedBy.length / Object.keys(rankingData.results_by_llm).length) * 100),
      position: data.positions.length > 0 ? data.positions[0] : index + 1,
      brandsCount: 1,
      pageTitle: data.anchorText || `${data.domain} - Source`,
      domain: data.domain,
      lastCrawled: new Date().toISOString().split('T')[0],
      isAccessible: data.isAccessible,
      httpStatus: data.isAccessible ? 200 : 404,
      contentType: data.category,
      anchorText: data.anchorText,
      citedBy: Array.from(new Set(data.citedBy)),
    }));

    // Sort sources by mention rate
    sources.sort((a, b) => b.mentionRate - a.mentionRate);
    sources.forEach((s, i) => s.rank = i + 1);

    return {
      displayRankings: rankings,
      allCitations: Array.from(citationMap.values()),
      allSources: sources,
    };
  }, [rankingData]);

  // Toggle expanded brand
  const toggleBrandExpand = (rank: number) => {
    setExpandedBrands(prev =>
      prev.includes(rank) ? prev.filter(r => r !== rank) : [...prev, rank]
    );
  };

  // Build prompts data from API responses
  const promptsData = useMemo(() => {
    if (!rankingData?.results_by_llm) return [];

    return Object.entries(rankingData.results_by_llm).map(([provider, result]) => {
      const providerConfig = llmProviders.find(p => p.id === provider);

      // Transform citations for this prompt/response
      const citations = result.citations.map((cit, idx) => {
        // Safely extract domain
        let domain = cit.domain || "";
        if (!domain && cit.url) {
          try {
            if (cit.url.startsWith("http")) {
              domain = new URL(cit.url).hostname.replace("www.", "");
            } else {
              domain = cit.url.split("/")[0].replace("www.", "");
            }
          } catch {
            domain = cit.url.split("/")[0];
          }
        }

        return {
          url: cit.url,
          fullUrl: cit.url.startsWith("http") ? cit.url : `https://${cit.url}`,
          domain: domain,
          pageTitle: cit.anchor_text || `Citation from ${domain || "source"}`,
          contentType: cit.category || "unknown",
          httpStatus: cit.is_accessible ? 200 : 404,
          isAccessible: cit.is_accessible ?? true,
          anchorText: cit.anchor_text,
          context: cit.context,
          citedBy: [provider],
          position: cit.position || idx + 1,
          mentionRate: 100, // Single provider
        };
      });

      // Transform ranked entities (competitors/brands)
      const rankedEntities = result.ranked_entities.map((entity) => ({
        position: entity.position,
        name: entity.name,
        mentionedText: entity.mentioned_text,
        isOwnBrand: entity.is_own_brand,
        context: entity.context,
        sentiment: entity.sentiment,
      }));

      return {
        prompt: `Analysis by ${providerConfig?.name || provider}`,
        mentioned: result.our_brand_mentioned,
        brandsCount: result.total_brands_mentioned || result.ranked_entities.length,
        sourcesCount: result.citations.length,
        citations,
        rankedEntities,
        provider,
        rawResponse: result.raw_response, // Full response for display
        visibilityScore: result.visibility_score,
        ourPosition: result.our_brand_position,
        lastRun: result.last_run,
        model: result.model,
      };
    });
  }, [rankingData]);

  // Toggle expanded prompt
  const togglePromptExpand = (idx: number) => {
    setExpandedPrompts(prev =>
      prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx]
    );
  };

  const toggleProvider = (providerId: string) => {
    setSelectedProviders(prev => {
      if (prev.includes(providerId)) {
        if (prev.length === 1) return prev;
        return prev.filter(p => p !== providerId);
      }
      return [...prev, providerId];
    });
  };

  const getTrendIcon = (trend: number) => {
    if (trend > 0) return <span className="text-green-500 text-xs flex items-center gap-0.5"><TrendingUp className="w-3 h-3" />{trend}</span>;
    if (trend < 0) return <span className="text-red-500 text-xs flex items-center gap-0.5"><TrendingDown className="w-3 h-3" />{Math.abs(trend)}</span>;
    return <span className="text-gray-400 text-xs"><Minus className="w-3 h-3" /></span>;
  };

  if (keywordLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <RefreshCw className="w-8 h-8 text-violet-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => router.back()}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="w-5 h-5 text-gray-600" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-500">Keyword:</span>
              <h1 className="text-xl font-bold text-gray-900">
                {keywordData?.keyword || "Loading..."}
              </h1>
              <span className="text-sm text-gray-400">
                Last updated: {new Date().toLocaleDateString("en-US", { day: "numeric", month: "short", year: "numeric" })}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Globe className="w-4 h-4" />
            <span>Search volume: <strong className="text-gray-900">300</strong>/mo</span>
          </div>
          <button className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <Download className="w-4 h-4" />
            Export CSV
          </button>
          <button className="flex items-center gap-2 px-3 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors">
            <Share2 className="w-4 h-4" />
            Share
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-6">
          {[
            { id: "rankings", label: "Rankings", icon: BarChart3, count: displayRankings.length || undefined },
            { id: "prompts", label: "LLM Responses", icon: FileText, count: promptsData.length || undefined },
            { id: "sources", label: "Sources", icon: Link2, count: allSources.length || undefined },
            { id: "google_aio", label: "Google AIO", icon: Search, badge: aioData?.has_ai_overview ? "Live" : undefined },
            { id: "shopping", label: "Shopping", icon: ShoppingCart },
            { id: "settings", label: "Settings", icon: Settings },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`flex items-center gap-2 px-1 py-3 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-gray-900 text-gray-900"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              <tab.icon className="w-4 h-4" />
              {tab.label}
              {tab.count && (
                <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                  {tab.count}
                </span>
              )}
              {"badge" in tab && tab.badge && (
                <span className="px-1.5 py-0.5 bg-green-100 text-green-700 rounded text-xs animate-pulse">
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Rankings Tab */}
      {activeTab === "rankings" && (
        <div className="space-y-6">
          {/* Loading State */}
          {rankingLoading && (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
              <RefreshCw className="w-8 h-8 text-violet-500 animate-spin mx-auto mb-4" />
              <p className="text-gray-500">Loading ranking data...</p>
            </div>
          )}

          {/* Error State */}
          {rankingError && (
            <div className="bg-white rounded-xl border border-red-200 p-6">
              <div className="flex items-center gap-3 text-red-600">
                <AlertCircle className="w-6 h-6" />
                <div>
                  <h3 className="font-semibold">Failed to load ranking data</h3>
                  <p className="text-sm text-red-500">Please try refreshing the page or run a new analysis.</p>
                </div>
              </div>
            </div>
          )}

          {/* Empty State */}
          {!rankingLoading && !rankingError && displayRankings.length === 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
              <AlertTriangle className="w-16 h-16 text-amber-400 mx-auto mb-4" />
              <h2 className="text-lg font-bold text-gray-900 mb-2">No ranking data yet</h2>
              <p className="text-gray-500 max-w-md mx-auto mb-6">
                Run an LLM analysis for this keyword to see which brands are being mentioned and how they rank.
              </p>
              <p className="text-sm text-gray-400">
                Go to the keywords page and click "Analyze" to start tracking this keyword.
              </p>
            </div>
          )}

          {/* Chart Header */}
          {!rankingLoading && displayRankings.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Brand rankings</h2>
                <p className="text-sm text-gray-500">Overview of all brands & visibility for this keyword</p>
              </div>

              {/* AI Search Engines Selector */}
              <div className="relative">
                <button
                  onClick={() => setShowProviderDropdown(!showProviderDropdown)}
                  className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg hover:border-gray-300 transition-colors"
                >
                  <span className="text-sm text-gray-600">AI Search Engines</span>
                  <div className="flex -space-x-1">
                    {selectedProviders.slice(0, 6).map(p => {
                      const provider = llmProviders.find(lp => lp.id === p);
                      return (
                        <div
                          key={p}
                          className={`w-5 h-5 rounded ${provider?.color || "bg-gray-400"} flex items-center justify-center text-white text-[9px] font-bold ring-1 ring-white`}
                        >
                          {provider?.name?.charAt(0) || "?"}
                        </div>
                      );
                    })}
                  </div>
                  <ChevronDown className="w-4 h-4 text-gray-400" />
                </button>

                {showProviderDropdown && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setShowProviderDropdown(false)} />
                    <div className="absolute right-0 top-full mt-2 w-64 bg-white rounded-xl shadow-xl ring-1 ring-gray-100 py-2 z-50 max-h-80 overflow-y-auto">
                      {llmProviders.map(provider => (
                        <button
                          key={provider.id}
                          onClick={() => toggleProvider(provider.id)}
                          className="w-full flex items-center gap-3 px-4 py-2 hover:bg-gray-50 transition-colors"
                        >
                          <div className={`w-5 h-5 rounded ${provider.color} flex items-center justify-center text-white text-[10px] font-bold`}>
                            {provider.name.charAt(0)}
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
            </div>

            {/* Position Trend Chart */}
            <PositionTrendChart
              data={[]}
              providers={llmProviders.filter(p => selectedProviders.includes(p.id))}
            />
          </div>
          )}

          {/* Rankings Table */}
          {!rankingLoading && displayRankings.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Top {displayRankings.length} Brand Rankings</h2>
                <p className="text-sm text-gray-500">
                  Showing {Math.min(brandsLimit, displayRankings.length)} of {displayRankings.length} brands. Click a row to see citation details.
                </p>
              </div>
              <button className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                <Download className="w-4 h-4" />
                Export Rankings
              </button>
            </div>

            <table className="w-full">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Rank</th>
                  <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Brand</th>
                  <th className="text-center px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Share of Voice</th>
                  <th className="text-center px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Position</th>
                  <th className="text-center px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Citations</th>
                  <th className="w-10"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {displayRankings.slice(0, brandsLimit).map((brand, index) => (
                  <React.Fragment key={brand.rank}>
                    {/* Brand Row - Clickable */}
                    <tr
                      className={`hover:bg-gray-50 cursor-pointer transition-colors ${
                        brand.isOwnBrand
                          ? "bg-gradient-to-r from-violet-50 to-indigo-50 border-l-4 border-l-violet-500"
                          : ""
                      } ${expandedBrands.includes(brand.rank) ? "bg-blue-50" : ""}`}
                      onClick={() => toggleBrandExpand(brand.rank)}
                    >
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className={`font-medium ${brand.isOwnBrand ? "text-violet-700" : "text-gray-900"}`}>
                            #{brand.rank}
                          </span>
                          {getTrendIcon(brand.trend)}
                          {brand.isOwnBrand && (
                            <span className="px-1.5 py-0.5 bg-violet-100 text-violet-700 rounded text-[10px] font-semibold uppercase">
                              You
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold ${
                            brand.isOwnBrand
                              ? "bg-gradient-to-br from-violet-500 to-indigo-600 text-white"
                              : "bg-gray-100 text-gray-600"
                          }`}>
                            {brand.name.charAt(0)}
                          </div>
                          <div>
                            <p className={`font-medium ${brand.isOwnBrand ? "text-violet-900" : "text-gray-900"}`}>
                              {brand.name}
                            </p>
                            <p className="text-xs text-gray-400">{brand.domain}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-center gap-2">
                          <span className={`font-semibold ${
                            brand.isOwnBrand ? "text-violet-600" :
                            brand.shareOfVoice >= 50 ? "text-green-600" :
                            brand.shareOfVoice >= 30 ? "text-amber-600" :
                            "text-gray-600"
                          }`}>
                            {brand.shareOfVoice}%
                          </span>
                          <div className="w-20 bg-gray-200 rounded-full h-1.5">
                            <div
                              className={`h-full rounded-full ${
                                brand.isOwnBrand ? "bg-violet-500" :
                                brand.shareOfVoice >= 50 ? "bg-green-500" :
                                brand.shareOfVoice >= 30 ? "bg-amber-500" :
                                "bg-gray-400"
                              }`}
                              style={{ width: `${Math.min(brand.shareOfVoice, 100)}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className={brand.isOwnBrand ? "text-violet-700 font-medium" : "text-gray-700"}>
                          {brand.position}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className={brand.isOwnBrand ? "text-violet-600" : "text-blue-600"}>
                          {brand.citations}
                        </span>
                        <span className="text-gray-400 text-sm ml-1">URLs</span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${expandedBrands.includes(brand.rank) ? 'rotate-180' : ''}`} />
                      </td>
                    </tr>

                    {/* Expanded Citation Details */}
                    {expandedBrands.includes(brand.rank) && brand.citationDetails && (
                      <tr>
                        <td colSpan={6} className="p-0">
                          <div className="bg-gray-50 border-t border-b border-gray-200">
                            {/* Citation Header */}
                            <div className="px-6 py-3 bg-gray-100 border-b border-gray-200">
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                  <span className="text-sm font-semibold text-gray-700">
                                    Citations for {brand.name}
                                  </span>
                                  <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs font-medium">
                                    {brand.citationDetails.length} sources
                                  </span>
                                </div>
                                <div className="flex items-center gap-4">
                                  <div className="flex items-center gap-2">
                                    <span className="text-xs text-gray-500">Sentiment:</span>
                                    <span className="px-2 py-0.5 bg-green-100 text-green-700 rounded text-xs">
                                      {brand.citationDetails.filter(c => c.sentiment === 'positive').length} positive
                                    </span>
                                    <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                                      {brand.citationDetails.filter(c => c.sentiment === 'neutral').length} neutral
                                    </span>
                                    <span className="px-2 py-0.5 bg-red-100 text-red-700 rounded text-xs">
                                      {brand.citationDetails.filter(c => c.sentiment === 'negative').length} negative
                                    </span>
                                  </div>
                                </div>
                              </div>
                            </div>

                            {/* Citations List */}
                            <div className="max-h-[400px] overflow-y-auto">
                              {brand.citationDetails.map((citation, citIdx) => (
                                <div key={citIdx} className="px-6 py-3 border-b border-gray-100 last:border-b-0 hover:bg-white transition-colors">
                                  <div className="flex items-start gap-3">
                                    {/* Rank */}
                                    <span className="text-xs font-medium text-gray-400 w-6 pt-1">#{citIdx + 1}</span>

                                    {/* Citation Content */}
                                    <div className="flex-1 min-w-0">
                                      {/* Title & URL */}
                                      <div className="flex items-start justify-between gap-3">
                                        <div className="min-w-0 flex-1">
                                          <h4 className="text-sm font-medium text-gray-900 truncate">{citation.pageTitle}</h4>
                                          <a
                                            href={citation.fullUrl}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-xs text-blue-600 hover:underline flex items-center gap-1"
                                            onClick={(e) => e.stopPropagation()}
                                          >
                                            <span className="truncate max-w-md">{citation.fullUrl}</span>
                                            <ExternalLink className="w-3 h-3 flex-shrink-0" />
                                          </a>
                                        </div>

                                        {/* Status & Sentiment */}
                                        <div className="flex items-center gap-2">
                                          {citation.sentiment && (
                                            <span className={`px-2 py-0.5 rounded text-xs ${
                                              citation.sentiment === 'positive' ? 'bg-green-100 text-green-700' :
                                              citation.sentiment === 'negative' ? 'bg-red-100 text-red-700' :
                                              'bg-gray-100 text-gray-600'
                                            }`}>
                                              {citation.sentiment}
                                            </span>
                                          )}
                                          {citation.isAccessible ? (
                                            <span className="flex items-center gap-1 px-2 py-0.5 bg-green-100 text-green-700 rounded-full text-xs">
                                              <CheckCircle className="w-3 h-3" />
                                              {citation.httpStatus}
                                            </span>
                                          ) : (
                                            <span className="flex items-center gap-1 px-2 py-0.5 bg-red-100 text-red-700 rounded-full text-xs">
                                              <AlertCircle className="w-3 h-3" />
                                              Error
                                            </span>
                                          )}
                                        </div>
                                      </div>

                                      {/* Mention Context */}
                                      {citation.mentionContext && (
                                        <p className="text-xs text-gray-600 mt-1 italic bg-gray-100 px-2 py-1 rounded">
                                          "{citation.mentionContext}"
                                        </p>
                                      )}

                                      {/* Meta Row */}
                                      <div className="flex items-center gap-3 mt-2 flex-wrap">
                                        {/* Domain */}
                                        <span className="text-xs text-gray-500 flex items-center gap-1">
                                          <Globe className="w-3 h-3" />
                                          {citation.domain}
                                        </span>

                                        {/* Content Type */}
                                        <span className="px-1.5 py-0.5 bg-gray-200 text-gray-600 rounded text-xs">
                                          {citation.contentType}
                                        </span>

                                        {/* Position */}
                                        <span className="text-xs text-gray-500">
                                          Pos: <strong className="text-gray-700">{citation.position}</strong>
                                        </span>

                                        {/* Last Crawled */}
                                        {citation.lastCrawled && (
                                          <span className="text-xs text-gray-400">
                                            Crawled: {citation.lastCrawled}
                                          </span>
                                        )}

                                        {/* Cited By LLMs */}
                                        <div className="flex items-center gap-1 ml-auto">
                                          <span className="text-xs text-gray-400 mr-1">Cited by:</span>
                                          {citation.citedBy.map(providerId => {
                                            const provider = llmProviders.find(p => p.id === providerId);
                                            return provider ? (
                                              <div
                                                key={providerId}
                                                className={`w-4 h-4 rounded ${provider.color} flex items-center justify-center text-white text-[8px] font-bold`}
                                                title={provider.name}
                                              >
                                                {provider.name.charAt(0)}
                                              </div>
                                            ) : null;
                                          })}
                                        </div>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>

            {/* Load More / Show All Buttons */}
            {brandsLimit < displayRankings.length && (
              <div className="px-6 py-4 border-t border-gray-100 bg-gray-50">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">
                    Showing {brandsLimit} of {displayRankings.length} brands
                  </span>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setBrandsLimit(prev => Math.min(prev + 10, displayRankings.length))}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      Load More (+10)
                    </button>
                    <button
                      onClick={() => setBrandsLimit(displayRankings.length)}
                      className="px-4 py-2 text-sm font-medium text-white bg-violet-600 rounded-lg hover:bg-violet-700 transition-colors"
                    >
                      Show All {displayRankings.length}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* All Loaded */}
            {brandsLimit >= displayRankings.length && displayRankings.length > 20 && (
              <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 text-center">
                <span className="text-sm text-gray-500">
                  All {displayRankings.length} brands loaded
                </span>
                <button
                  onClick={() => setBrandsLimit(20)}
                  className="ml-3 text-sm text-violet-600 hover:underline"
                >
                  Collapse list
                </button>
              </div>
            )}
          </div>
          )}
        </div>
      )}

      {/* Prompts Tab */}
      {activeTab === "prompts" && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-gray-900">LLM Response Explorer</h2>
              <p className="text-sm text-gray-500">Breakdown of AI responses & citations for this keyword. Click to expand details.</p>
            </div>
            <div className="flex items-center gap-2">
              {rankingData?.summary && (
                <span className="px-3 py-1 bg-violet-100 text-violet-700 rounded-full text-sm font-medium">
                  {rankingData.summary.total_llms_analyzed} LLMs analyzed
                </span>
              )}
            </div>
          </div>

          {promptsData.length === 0 && !rankingLoading && (
            <div className="px-6 py-12 text-center">
              <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No analysis data yet</h3>
              <p className="text-gray-500 max-w-md mx-auto">
                Run an LLM analysis for this keyword to see how different AI models respond.
              </p>
            </div>
          )}

          <div className="divide-y divide-gray-100">
            {promptsData.map((prompt, idx) => {
              const providerConfig = llmProviders.find(p => p.id === prompt.provider);
              return (
                <div key={idx}>
                  {/* Prompt Header - Clickable */}
                  <div
                    className="px-6 py-4 hover:bg-gray-50 cursor-pointer"
                    onClick={() => togglePromptExpand(idx)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        {providerConfig && (
                          <div className={`w-8 h-8 rounded-lg ${providerConfig.color} flex items-center justify-center text-white text-sm font-bold`}>
                            {providerConfig.name.charAt(0)}
                          </div>
                        )}
                        <div>
                          <p className="text-gray-900 font-medium">{prompt.prompt}</p>
                          {prompt.lastRun && (
                            <p className="text-xs text-gray-400 mt-0.5">
                              Last analyzed: {new Date(prompt.lastRun).toLocaleDateString()}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-6 text-sm shrink-0">
                        {prompt.mentioned ? (
                          <span className="flex items-center gap-1 text-green-600">
                            <CheckCircle className="w-4 h-4" />
                            Position #{prompt.ourPosition || "N/A"}
                          </span>
                        ) : (
                          <span className="text-gray-400">Not mentioned</span>
                        )}
                        <span className="text-gray-500">
                          <strong className="text-gray-700">{prompt.brandsCount}</strong> Brands
                        </span>
                        <span className="text-gray-500">
                          <strong className="text-blue-600">{prompt.sourcesCount}</strong> Citations
                        </span>
                        {prompt.visibilityScore !== undefined && (
                          <span className="px-2 py-0.5 bg-violet-100 text-violet-700 rounded text-xs font-medium">
                            Score: {prompt.visibilityScore}
                          </span>
                        )}
                        <ChevronDown className={`w-4 h-4 text-gray-400 transition-transform ${expandedPrompts.includes(idx) ? 'rotate-180' : ''}`} />
                      </div>
                    </div>
                  </div>

                  {/* Expanded Details - Raw Response, Brands, Citations */}
                  {expandedPrompts.includes(idx) && (
                    <div className="bg-gray-50 border-t border-gray-100">
                      {/* Tabs for different views */}
                      <div className="px-6 py-3 border-b border-gray-200 bg-gray-100 flex items-center gap-4">
                        <span className="text-sm font-medium text-gray-700">
                          {providerConfig?.name || prompt.provider} Analysis
                        </span>
                        {prompt.model && (
                          <span className="px-2 py-0.5 bg-white text-gray-600 rounded text-xs">
                            Model: {prompt.model}
                          </span>
                        )}
                      </div>

                      {/* Raw LLM Response */}
                      {prompt.rawResponse && (
                        <div className="px-6 py-4 border-b border-gray-200">
                          <h4 className="text-sm font-semibold text-gray-800 mb-2 flex items-center gap-2">
                            <FileText className="w-4 h-4" />
                            Raw LLM Response
                          </h4>
                          <div className="bg-white border border-gray-200 rounded-lg p-4 max-h-[300px] overflow-y-auto">
                            <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono leading-relaxed">
                              {prompt.rawResponse}
                            </pre>
                          </div>
                        </div>
                      )}

                      {/* Ranked Brands/Competitors */}
                      {prompt.rankedEntities && prompt.rankedEntities.length > 0 && (
                        <div className="px-6 py-4 border-b border-gray-200">
                          <h4 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
                            <BarChart3 className="w-4 h-4" />
                            Brands Mentioned ({prompt.rankedEntities.length})
                          </h4>
                          <div className="space-y-2">
                            {prompt.rankedEntities.map((entity, entityIdx) => (
                              <div
                                key={entityIdx}
                                className={`flex items-start gap-3 p-3 rounded-lg border ${
                                  entity.isOwnBrand
                                    ? "bg-violet-50 border-violet-200"
                                    : "bg-white border-gray-200"
                                }`}
                              >
                                <span className={`text-lg font-bold ${
                                  entity.isOwnBrand ? "text-violet-600" : "text-gray-400"
                                }`}>
                                  #{entity.position}
                                </span>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-2">
                                    <span className={`font-medium ${
                                      entity.isOwnBrand ? "text-violet-900" : "text-gray-900"
                                    }`}>
                                      {entity.name}
                                    </span>
                                    {entity.isOwnBrand && (
                                      <span className="px-1.5 py-0.5 bg-violet-200 text-violet-700 rounded text-[10px] font-semibold">
                                        YOUR BRAND
                                      </span>
                                    )}
                                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                      entity.sentiment === "positive" ? "bg-green-100 text-green-700" :
                                      entity.sentiment === "negative" ? "bg-red-100 text-red-700" :
                                      "bg-gray-100 text-gray-600"
                                    }`}>
                                      {entity.sentiment}
                                    </span>
                                  </div>
                                  {entity.context && (
                                    <p className="text-xs text-gray-500 mt-1 italic">
                                      "...{entity.context}..."
                                    </p>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Citations Section */}
                      <div className="px-6 py-4">
                        <h4 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
                          <Link2 className="w-4 h-4" />
                          Citations / Sources ({prompt.citations.length})
                        </h4>

                        {prompt.citations.length === 0 ? (
                          <div className="py-6 text-center bg-white rounded-lg border border-gray-200">
                            <p className="text-sm text-gray-500">No URL citations found in this response.</p>
                            <p className="text-xs text-gray-400 mt-1">The LLM may not have included explicit source links.</p>
                          </div>
                        ) : (
                          <div className="space-y-2 max-h-[400px] overflow-y-auto">
                            {prompt.citations.map((citation, citIdx) => (
                              <div key={citIdx} className="p-3 bg-white rounded-lg border border-gray-200 hover:border-blue-300 transition-colors">
                                <div className="flex items-start gap-3">
                                  <span className="text-xs font-bold text-gray-400 w-6">#{citIdx + 1}</span>
                                  <div className="flex-1 min-w-0">
                                    <a
                                      href={citation.fullUrl}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-sm text-blue-600 hover:underline flex items-center gap-1 font-medium"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <span className="truncate">{citation.fullUrl}</span>
                                      <ExternalLink className="w-3 h-3 flex-shrink-0" />
                                    </a>
                                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                                      <span className="text-xs text-gray-500 flex items-center gap-1">
                                        <Globe className="w-3 h-3" />
                                        {citation.domain}
                                      </span>
                                      {citation.contentType && (
                                        <span className="px-1.5 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                                          {citation.contentType}
                                        </span>
                                      )}
                                      {citation.anchorText && (
                                        <span className="text-xs text-gray-400 italic">"{citation.anchorText}"</span>
                                      )}
                                    </div>
                                    {citation.context && (
                                      <p className="text-xs text-gray-500 mt-1.5 bg-gray-50 p-2 rounded">
                                        Context: {citation.context.substring(0, 200)}...
                                      </p>
                                    )}
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Sources Tab */}
      {activeTab === "sources" && (
        <div className="space-y-6">
          {/* Summary Cards */}
          <div className="grid grid-cols-4 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-sm text-gray-500">Total Citations</p>
              <p className="text-2xl font-bold text-gray-900">{allSources.length}</p>
              <p className="text-xs text-gray-400 mt-1">From LLM responses</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-sm text-gray-500">Unique Domains</p>
              <p className="text-2xl font-bold text-gray-900">{new Set(allSources.map(s => s.domain)).size}</p>
              <p className="text-xs text-gray-400 mt-1">Across all LLMs</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-sm text-gray-500">Accessible URLs</p>
              <p className="text-2xl font-bold text-green-600">{allSources.filter(s => s.isAccessible).length}</p>
              <p className="text-xs text-gray-400 mt-1">HTTP 200 responses</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-sm text-gray-500">Your Domain Cited</p>
              <p className="text-2xl font-bold text-violet-600">
                {allSources.some(s => s.domain?.includes(projectDomain)) ? "Yes" : "No"}
              </p>
              <p className="text-xs text-gray-400 mt-1">{projectDomain || "Set domain in project"}</p>
            </div>
          </div>

          {/* Citations Table */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-gray-900">{allSources.length > 0 ? `Top ${allSources.length} Citations` : "Citations"}</h2>
                <p className="text-sm text-gray-500">
                  {allSources.length > 0
                    ? `Showing ${Math.min(sourcesLimit, allSources.length)} of ${allSources.length} URLs cited by AI for this keyword`
                    : "No citations found. Run an analysis to see citation data."
                  }
                </p>
              </div>
              <div className="flex items-center gap-3">
                <button className="flex items-center gap-2 px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                  <Download className="w-4 h-4" />
                  Export All ({allSources.length})
                </button>
                {/* AI Search Engines Selector */}
                <div className="flex items-center gap-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg">
                  <span className="text-sm text-gray-600 mr-2">Cited By</span>
                  {llmProviders.slice(0, 6).map(p => (
                    <div
                      key={p.id}
                      className={`w-5 h-5 rounded ${p.color} flex items-center justify-center text-white text-[9px] font-bold`}
                    >
                      {p.name.charAt(0)}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {allSources.length === 0 && !rankingLoading && (
              <div className="px-6 py-12 text-center">
                <AlertTriangle className="w-12 h-12 text-amber-400 mx-auto mb-4" />
                <h3 className="text-lg font-semibold text-gray-900 mb-2">No citation data yet</h3>
                <p className="text-gray-500 max-w-md mx-auto">
                  Run an LLM analysis for this keyword to see which URLs are being cited by AI models.
                </p>
              </div>
            )}

            <div className="divide-y divide-gray-100">
              {allSources.slice(0, sourcesLimit).map((source) => (
                <div key={source.rank} className="px-6 py-4 hover:bg-gray-50">
                  <div className="flex items-start gap-4">
                    {/* Rank & Logo */}
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-xs font-semibold text-gray-400">#{source.rank}</span>
                      <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center text-sm font-bold text-gray-600">
                        {source.name.charAt(0)}
                      </div>
                    </div>

                    {/* Main Content */}
                    <div className="flex-1 min-w-0">
                      {/* Title & URL */}
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0 flex-1">
                          <h3 className="font-medium text-gray-900 truncate">
                            {source.pageTitle || source.name}
                          </h3>
                          <a
                            href={source.fullUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm text-blue-600 hover:underline flex items-center gap-1 mt-0.5"
                          >
                            <span className="truncate max-w-lg">{source.fullUrl}</span>
                            <ExternalLink className="w-3 h-3 flex-shrink-0" />
                          </a>
                        </div>

                        {/* Status Badge */}
                        <div className="flex items-center gap-2">
                          {source.isAccessible ? (
                            <span className="flex items-center gap-1 px-2 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium">
                              <CheckCircle className="w-3 h-3" />
                              {source.httpStatus}
                            </span>
                          ) : (
                            <span className="flex items-center gap-1 px-2 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium">
                              <AlertCircle className="w-3 h-3" />
                              {source.httpStatus || "Error"}
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Meta Info Row */}
                      <div className="flex items-center gap-4 mt-3 text-sm">
                        {/* Domain */}
                        <div className="flex items-center gap-1 text-gray-500">
                          <Globe className="w-3.5 h-3.5" />
                          <span>{source.domain}</span>
                        </div>

                        {/* Content Type */}
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-600 rounded text-xs">
                          {source.contentType}
                        </span>

                        {/* Mention Rate */}
                        <div className="flex items-center gap-1">
                          <span className={`font-semibold ${
                            source.mentionRate >= 20 ? "text-green-600" :
                            source.mentionRate >= 10 ? "text-amber-600" :
                            "text-gray-500"
                          }`}>
                            {source.mentionRate}%
                          </span>
                          <span className="text-gray-400">mention rate</span>
                        </div>

                        {/* Position */}
                        <div className="flex items-center gap-1 text-gray-500">
                          <span>Avg. position:</span>
                          <span className="font-medium text-gray-700">{source.position}</span>
                        </div>

                        {/* Last Crawled */}
                        <div className="flex items-center gap-1 text-gray-400 text-xs">
                          <span>Crawled:</span>
                          <span>{source.lastCrawled}</span>
                        </div>
                      </div>

                      {/* Anchor Text & Cited By */}
                      <div className="flex items-center gap-4 mt-3">
                        {/* Anchor Text */}
                        {source.anchorText && (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-400">Anchor:</span>
                            <span className="text-xs text-gray-600 italic">"{source.anchorText}"</span>
                          </div>
                        )}

                        {/* Cited By LLMs */}
                        {source.citedBy && source.citedBy.length > 0 && (
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-gray-400">Cited by:</span>
                            <div className="flex items-center gap-1">
                              {source.citedBy.map(providerId => {
                                const provider = llmProviders.find(p => p.id === providerId);
                                return provider ? (
                                  <div
                                    key={providerId}
                                    className={`w-5 h-5 rounded ${provider.color} flex items-center justify-center text-white text-[9px] font-bold`}
                                    title={provider.name}
                                  >
                                    {provider.name.charAt(0)}
                                  </div>
                                ) : null;
                              })}
                            </div>
                          </div>
                        )}

                        {/* Brands Count */}
                        <div className="flex items-center gap-1 text-xs text-gray-500">
                          <span>Mentions</span>
                          <span className="font-semibold text-gray-700">{source.brandsCount}</span>
                          <span>brand{source.brandsCount !== 1 ? "s" : ""}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Load More / Show All Button */}
            {sourcesLimit < allSources.length && (
              <div className="px-6 py-4 border-t border-gray-100 bg-gray-50">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">
                    Showing {sourcesLimit} of {allSources.length} citations
                  </span>
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => setSourcesLimit(prev => Math.min(prev + 20, allSources.length))}
                      className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      Load More (+20)
                    </button>
                    <button
                      onClick={() => setSourcesLimit(allSources.length)}
                      className="px-4 py-2 text-sm font-medium text-white bg-violet-600 rounded-lg hover:bg-violet-700 transition-colors"
                    >
                      Show All {allSources.length}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* All Loaded Message */}
            {sourcesLimit >= allSources.length && allSources.length > 20 && (
              <div className="px-6 py-4 border-t border-gray-100 bg-gray-50 text-center">
                <span className="text-sm text-gray-500">
                  All {allSources.length} citations loaded
                </span>
                <button
                  onClick={() => setSourcesLimit(20)}
                  className="ml-3 text-sm text-violet-600 hover:underline"
                >
                  Collapse list
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Google AIO Tab */}
      {activeTab === "google_aio" && (
        <div className="space-y-6">
          {/* Header with refresh button */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                <Search className="w-5 h-5 text-blue-500" />
                Google AI Overview
              </h2>
              <p className="text-sm text-gray-500">
                Real-time analysis of Google&apos;s AI Overview for this keyword
              </p>
            </div>
            <div className="flex items-center gap-3">
              {/* Country Display (set at project level) */}
              <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                <Globe className="w-4 h-4 text-gray-400" />
                <span className="text-gray-600">
                  {projectCountryInfo.flag} {projectCountryInfo.name}
                </span>
              </div>
              {/* Refresh Button */}
              <button
                onClick={fetchFreshAio}
                disabled={isLoadingAio || aioLoading}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
              >
                <RefreshCw className={`w-4 h-4 ${isLoadingAio ? "animate-spin" : ""}`} />
                {isLoadingAio ? "Fetching..." : "Fetch AIO Data"}
              </button>
            </div>
          </div>

          {/* Loading State */}
          {(aioLoading || isLoadingAio) && (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
              <RefreshCw className="w-8 h-8 text-blue-500 animate-spin mx-auto mb-4" />
              <p className="text-gray-500">Fetching Google AI Overview data...</p>
              <p className="text-sm text-gray-400 mt-2">This may take a few seconds</p>
            </div>
          )}

          {/* No Data State */}
          {!aioLoading && !isLoadingAio && !aioData && (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
              <Search className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-bold text-gray-900 mb-2">No AI Overview Data Yet</h3>
              <p className="text-gray-500 max-w-md mx-auto mb-6">
                Click &quot;Fetch AIO Data&quot; to check if Google shows an AI Overview for this keyword and analyze your brand&apos;s presence.
              </p>
              <button
                onClick={fetchFreshAio}
                className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Fetch AI Overview Data
              </button>
            </div>
          )}

          {/* AIO Data Display */}
          {!aioLoading && !isLoadingAio && aioData && (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-4 gap-4">
                {/* Has AI Overview */}
                <div className={`rounded-xl border p-4 ${aioData.has_ai_overview ? "bg-green-50 border-green-200" : "bg-gray-50 border-gray-200"}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Sparkles className={`w-5 h-5 ${aioData.has_ai_overview ? "text-green-600" : "text-gray-400"}`} />
                    <p className="text-sm font-medium text-gray-700">AI Overview</p>
                  </div>
                  <p className={`text-2xl font-bold ${aioData.has_ai_overview ? "text-green-600" : "text-gray-400"}`}>
                    {aioData.has_ai_overview ? "Active" : "None"}
                  </p>
                  {aioData.aio_type && (
                    <p className="text-xs text-gray-500 mt-1">Type: {aioData.aio_type}</p>
                  )}
                </div>

                {/* Brand in AIO */}
                <div className={`rounded-xl border p-4 ${aioData.brand_in_aio ? "bg-violet-50 border-violet-200" : "bg-gray-50 border-gray-200"}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Eye className={`w-5 h-5 ${aioData.brand_in_aio ? "text-violet-600" : "text-gray-400"}`} />
                    <p className="text-sm font-medium text-gray-700">Brand in AIO</p>
                  </div>
                  <p className={`text-2xl font-bold ${aioData.brand_in_aio ? "text-violet-600" : "text-gray-400"}`}>
                    {aioData.brand_in_aio ? "Yes" : "No"}
                  </p>
                  {aioData.brand_aio_position && (
                    <p className="text-xs text-violet-600 mt-1">Position #{aioData.brand_aio_position}</p>
                  )}
                </div>

                {/* Domain in AIO Sources */}
                <div className={`rounded-xl border p-4 ${aioData.domain_in_aio ? "bg-blue-50 border-blue-200" : "bg-gray-50 border-gray-200"}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Link2 className={`w-5 h-5 ${aioData.domain_in_aio ? "text-blue-600" : "text-gray-400"}`} />
                    <p className="text-sm font-medium text-gray-700">Domain Cited</p>
                  </div>
                  <p className={`text-2xl font-bold ${aioData.domain_in_aio ? "text-blue-600" : "text-gray-400"}`}>
                    {aioData.domain_in_aio ? "Yes" : "No"}
                  </p>
                  {aioData.domain_aio_position && (
                    <p className="text-xs text-blue-600 mt-1">Source #{aioData.domain_aio_position}</p>
                  )}
                </div>

                {/* Organic Position */}
                <div className={`rounded-xl border p-4 ${aioData.brand_in_organic ? "bg-amber-50 border-amber-200" : "bg-gray-50 border-gray-200"}`}>
                  <div className="flex items-center gap-2 mb-2">
                    <Globe className={`w-5 h-5 ${aioData.brand_in_organic ? "text-amber-600" : "text-gray-400"}`} />
                    <p className="text-sm font-medium text-gray-700">Organic Results</p>
                  </div>
                  <p className={`text-2xl font-bold ${aioData.brand_in_organic ? "text-amber-600" : "text-gray-400"}`}>
                    {aioData.brand_in_organic ? `#${aioData.brand_organic_position}` : "Not Found"}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">In top 10 results</p>
                </div>
              </div>

              {/* AI Overview Content */}
              {aioData.has_ai_overview && aioData.aio_text && (
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-blue-50 to-indigo-50">
                    <h3 className="font-semibold text-gray-900 flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-blue-600" />
                      AI Overview Content
                    </h3>
                    <p className="text-sm text-gray-500">The AI-generated summary shown by Google</p>
                  </div>
                  <div className="px-6 py-4">
                    <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                      <p className="text-gray-700 leading-relaxed whitespace-pre-wrap">
                        {aioData.aio_text}
                      </p>
                    </div>
                    {aioData.brand_aio_context && (
                      <div className="mt-4 p-3 bg-violet-50 rounded-lg border border-violet-200">
                        <p className="text-sm font-medium text-violet-800 mb-1">Your Brand Context:</p>
                        <p className="text-sm text-violet-700 italic">&quot;{aioData.brand_aio_context}&quot;</p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* AIO Sources */}
              {aioData.aio_sources && aioData.aio_sources.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="px-6 py-4 border-b border-gray-100">
                    <h3 className="font-semibold text-gray-900">AIO Sources</h3>
                    <p className="text-sm text-gray-500">Sources cited in the AI Overview</p>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {aioData.aio_sources.map((source: { title?: string; link?: string; snippet?: string }, idx: number) => (
                      <div key={idx} className="px-6 py-3 hover:bg-gray-50">
                        <div className="flex items-start gap-3">
                          <span className="text-xs font-bold text-gray-400 mt-1">#{idx + 1}</span>
                          <div className="flex-1 min-w-0">
                            {source.title && (
                              <p className="font-medium text-gray-900 truncate">{source.title}</p>
                            )}
                            {source.link && (
                              <a
                                href={source.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-blue-600 hover:underline flex items-center gap-1"
                              >
                                <span className="truncate">{source.link}</span>
                                <ExternalLink className="w-3 h-3 flex-shrink-0" />
                              </a>
                            )}
                            {source.snippet && (
                              <p className="text-xs text-gray-500 mt-1 line-clamp-2">{source.snippet}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Competitors in AIO */}
              {aioData.competitors_in_aio && aioData.competitors_in_aio.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="px-6 py-4 border-b border-gray-100">
                    <h3 className="font-semibold text-gray-900">Competitors in AI Overview</h3>
                    <p className="text-sm text-gray-500">{aioData.competitors_in_aio.length} competitors found in the AIO</p>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {aioData.competitors_in_aio.map((comp: { name: string; position: number; context?: string }, idx: number) => (
                      <div key={idx} className="px-6 py-3 hover:bg-gray-50">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <span className="w-8 h-8 rounded-lg bg-red-100 text-red-600 flex items-center justify-center text-sm font-bold">
                              {comp.name.charAt(0)}
                            </span>
                            <div>
                              <p className="font-medium text-gray-900">{comp.name}</p>
                              {comp.context && (
                                <p className="text-xs text-gray-500 truncate max-w-md">{comp.context}</p>
                              )}
                            </div>
                          </div>
                          <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-sm">
                            Position #{comp.position}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Organic Results */}
              {aioData.organic_results && aioData.organic_results.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="px-6 py-4 border-b border-gray-100">
                    <h3 className="font-semibold text-gray-900">Top Organic Results</h3>
                    <p className="text-sm text-gray-500">Traditional search results for this keyword</p>
                  </div>
                  <div className="divide-y divide-gray-100">
                    {aioData.organic_results.map((result: { title?: string; link?: string; snippet?: string; position?: number }, idx: number) => (
                      <div key={idx} className="px-6 py-3 hover:bg-gray-50">
                        <div className="flex items-start gap-3">
                          <span className="text-xs font-bold text-gray-400 mt-1 w-6">#{result.position || idx + 1}</span>
                          <div className="flex-1 min-w-0">
                            {result.title && (
                              <p className="font-medium text-gray-900 truncate">{result.title}</p>
                            )}
                            {result.link && (
                              <a
                                href={result.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-sm text-green-600 hover:underline flex items-center gap-1"
                              >
                                <span className="truncate">{result.link}</span>
                                <ExternalLink className="w-3 h-3 flex-shrink-0" />
                              </a>
                            )}
                            {result.snippet && (
                              <p className="text-xs text-gray-500 mt-1 line-clamp-2">{result.snippet}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Timestamp */}
              <div className="text-center text-sm text-gray-400">
                Last fetched: {new Date(aioData.search_timestamp).toLocaleString()} • Country: {aioData.country?.toUpperCase()}
              </div>
            </>
          )}
        </div>
      )}

      {/* Shopping Tab */}
      {activeTab === "shopping" && (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
          <ShoppingCart className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-lg font-bold text-gray-900 mb-2">Shopping Recommendations</h2>
          <p className="text-gray-500 max-w-md mx-auto">
            View product recommendations and shopping results from AI responses for this keyword.
          </p>
          <p className="text-sm text-gray-400 mt-4">Coming soon</p>
        </div>
      )}

      {/* Settings Tab */}
      {activeTab === "settings" && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-bold text-gray-900 mb-2">Keyword settings</h2>
            <p className="text-sm text-gray-500 mb-6">Manage keyword status, configuration and AI prompts</p>

            {/* Move to another project */}
            <div className="border border-gray-200 rounded-lg p-4 mb-4">
              <h3 className="font-medium text-gray-900 mb-1">Move to another project</h3>
              <p className="text-sm text-gray-500 mb-3">
                Transfer this keyword to a different project in {currentProject?.name || "your organization"}
              </p>
              <select className="px-3 py-2 border border-gray-200 rounded-lg text-sm">
                <option>Select a project</option>
              </select>
            </div>

            {/* Archive keyword */}
            <div className="border border-gray-200 rounded-lg p-4">
              <h3 className="font-medium text-gray-900 mb-1">Keyword status</h3>
              <p className="text-sm text-gray-500 mb-3">
                Archive this keyword to stop tracking changes
              </p>
              <button className="px-4 py-2 border border-red-200 text-red-600 rounded-lg hover:bg-red-50 transition-colors text-sm">
                Archive keyword
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
