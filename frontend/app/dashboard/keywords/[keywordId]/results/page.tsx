"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { visibilityApi } from "@/lib/api";
import { useProjectStore } from "@/lib/store";
import {
  ArrowLeft, Award, Trophy, Medal, ExternalLink, Globe, Link2,
  CheckCircle, XCircle, AlertTriangle, TrendingUp, TrendingDown,
  Minus, Quote, Search, ShoppingBag, MessageSquare, FileText,
  ChevronDown, ChevronUp, Star, Sparkles
} from "lucide-react";
import Link from "next/link";

interface RankedEntity {
  position: number;
  name: string;
  mentioned_text: string;
  is_own_brand: boolean;
  context: string | null;
  sentiment: string;
  sentiment_score: number | null;
  match_type: string;
  match_confidence: number;
}

interface CitationData {
  position: number | null;
  url: string;
  domain: string | null;
  category: string;
  domain_authority: number | null;
  anchor_text: string | null;
  context: string | null;
  is_valid: boolean | null;
  is_accessible: boolean | null;
  is_hallucinated: boolean | null;
  is_our_domain: boolean;
}

interface LLMResult {
  provider: string;
  model: string;
  last_run: string;
  raw_response: string | null;
  ranked_entities: RankedEntity[];
  citations: CitationData[];
  our_brand_position: number | null;
  our_brand_mentioned: boolean;
  total_brands_mentioned: number;
  visibility_score?: number;
  mention_type?: string;
  competitors_mentioned?: Array<{ name: string; position?: number }>;
  fan_out_queries?: string[];
  has_shopping_recommendations?: boolean;
}

interface RankingResultsData {
  keyword_id: string;
  keyword: string;
  project_domain: string;
  analysis_period_days: number;
  results_by_llm: Record<string, LLMResult>;
  summary: {
    total_llms_analyzed: number;
    llms_mentioning_us: number;
    best_position: number | null;
    total_citations_across_llms: number;
  };
}

export default function KeywordRankingResultsPage() {
  const params = useParams();
  const router = useRouter();
  const keywordId = params.keywordId as string;
  const { currentProject } = useProjectStore();
  const [expandedLLM, setExpandedLLM] = useState<string | null>(null);
  const [showRawResponse, setShowRawResponse] = useState<string | null>(null);

  const { data: resultsData, isLoading } = useQuery({
    queryKey: ["keyword-ranking-results", currentProject?.id, keywordId],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      const response = await visibilityApi.getKeywordRankingResults(currentProject.id, keywordId, 30);
      return response.data as RankingResultsData;
    },
    enabled: !!currentProject?.id && !!keywordId,
  });

  const getPositionIcon = (position: number) => {
    if (position === 1) return <Trophy className="w-5 h-5 text-yellow-500" />;
    if (position === 2) return <Medal className="w-5 h-5 text-gray-400" />;
    if (position === 3) return <Medal className="w-5 h-5 text-amber-600" />;
    return <span className="w-5 h-5 flex items-center justify-center text-sm font-bold text-gray-500">#{position}</span>;
  };

  const getPositionBadge = (position: number | null, isOwn: boolean = false) => {
    if (!position) return null;

    const baseClasses = "inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-bold";

    if (isOwn) {
      if (position === 1) return <span className={`${baseClasses} bg-yellow-100 text-yellow-700 ring-2 ring-yellow-400`}><Trophy className="w-3 h-3" /> #1</span>;
      if (position <= 3) return <span className={`${baseClasses} bg-green-100 text-green-700 ring-2 ring-green-400`}>#{position}</span>;
      if (position <= 10) return <span className={`${baseClasses} bg-blue-100 text-blue-700`}>#{position}</span>;
      return <span className={`${baseClasses} bg-gray-100 text-gray-600`}>#{position}</span>;
    }

    if (position === 1) return <span className={`${baseClasses} bg-yellow-100 text-yellow-700`}><Trophy className="w-3 h-3" /> #1</span>;
    if (position <= 3) return <span className={`${baseClasses} bg-green-100 text-green-700`}>#{position}</span>;
    if (position <= 10) return <span className={`${baseClasses} bg-blue-100 text-blue-700`}>#{position}</span>;
    return <span className={`${baseClasses} bg-gray-100 text-gray-600`}>#{position}</span>;
  };

  const getSentimentColor = (sentiment: string) => {
    if (sentiment === "positive") return "text-green-600 bg-green-50";
    if (sentiment === "negative") return "text-red-600 bg-red-50";
    return "text-gray-600 bg-gray-50";
  };

  const getLLMColor = (provider: string) => {
    const colors: Record<string, { bg: string; text: string; border: string }> = {
      openai: { bg: "bg-green-500", text: "text-green-700", border: "border-green-200" },
      anthropic: { bg: "bg-orange-500", text: "text-orange-700", border: "border-orange-200" },
      google: { bg: "bg-blue-500", text: "text-blue-700", border: "border-blue-200" },
      perplexity: { bg: "bg-purple-500", text: "text-purple-700", border: "border-purple-200" },
    };
    return colors[provider] || { bg: "bg-gray-500", text: "text-gray-700", border: "border-gray-200" };
  };

  const getLLMName = (provider: string) => {
    const names: Record<string, string> = {
      openai: "ChatGPT",
      anthropic: "Claude",
      google: "Gemini",
      perplexity: "Perplexity",
    };
    return names[provider] || provider;
  };

  const getCategoryIcon = (category: string) => {
    const icons: Record<string, React.ReactNode> = {
      official_docs: <FileText className="w-4 h-4" />,
      blog: <MessageSquare className="w-4 h-4" />,
      news: <Globe className="w-4 h-4" />,
      review_site: <Star className="w-4 h-4" />,
      ecommerce: <ShoppingBag className="w-4 h-4" />,
    };
    return icons[category] || <Link2 className="w-4 h-4" />;
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-gray-200 rounded animate-pulse" />
        <div className="h-64 bg-gray-100 rounded-xl animate-pulse" />
      </div>
    );
  }

  if (!resultsData) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">No results found</p>
        <Link href="/dashboard/keywords" className="text-violet-600 hover:underline mt-2 inline-block">
          Back to Keywords
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button
            onClick={() => router.back()}
            className="flex items-center gap-2 text-gray-500 hover:text-gray-700 mb-4"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Keywords
          </button>
          <h1 className="text-2xl font-bold text-gray-900">Ranking Results</h1>
          <div className="flex items-center gap-3 mt-2">
            <span className="px-3 py-1 bg-violet-100 text-violet-700 rounded-full font-medium">
              {resultsData.keyword}
            </span>
            <span className="text-gray-400">|</span>
            <span className="text-gray-500 text-sm">
              Last {resultsData.analysis_period_days} days
            </span>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-violet-100 rounded-xl">
              <Sparkles className="w-6 h-6 text-violet-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{resultsData.summary.total_llms_analyzed}</p>
              <p className="text-sm text-gray-500">LLMs Analyzed</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-green-100 rounded-xl">
              <CheckCircle className="w-6 h-6 text-green-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{resultsData.summary.llms_mentioning_us}</p>
              <p className="text-sm text-gray-500">LLMs Mentioning Us</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-yellow-100 rounded-xl">
              <Trophy className="w-6 h-6 text-yellow-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {resultsData.summary.best_position ? `#${resultsData.summary.best_position}` : "-"}
              </p>
              <p className="text-sm text-gray-500">Best Position</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-blue-100 rounded-xl">
              <Link2 className="w-6 h-6 text-blue-600" />
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{resultsData.summary.total_citations_across_llms}</p>
              <p className="text-sm text-gray-500">Total Citations</p>
            </div>
          </div>
        </div>
      </div>

      {/* Results by LLM */}
      <div className="space-y-4">
        <h2 className="text-lg font-bold text-gray-900">Results by AI Engine</h2>

        {Object.entries(resultsData.results_by_llm).length === 0 ? (
          <div className="card text-center py-12">
            <Search className="w-12 h-12 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-500">No analysis results yet</p>
            <p className="text-gray-400 text-sm mt-1">Run an analysis to see ranking results</p>
          </div>
        ) : (
          Object.entries(resultsData.results_by_llm).map(([provider, result]) => {
            const colors = getLLMColor(provider);
            const isExpanded = expandedLLM === provider;

            return (
              <div
                key={provider}
                className={`card border-l-4 ${colors.border} overflow-hidden`}
              >
                {/* LLM Header */}
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setExpandedLLM(isExpanded ? null : provider)}
                >
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-xl ${colors.bg} flex items-center justify-center text-white font-bold text-lg`}>
                      {provider[0].toUpperCase()}
                    </div>
                    <div>
                      <h3 className="font-bold text-gray-900">{getLLMName(provider)}</h3>
                      <p className="text-sm text-gray-500">{result.model}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Our Position */}
                    <div className="text-center">
                      <p className="text-xs text-gray-400 uppercase">Our Position</p>
                      {result.our_brand_mentioned ? (
                        getPositionBadge(result.our_brand_position, true)
                      ) : (
                        <span className="text-gray-400 text-sm">Not Mentioned</span>
                      )}
                    </div>

                    {/* Visibility Score */}
                    {result.visibility_score !== undefined && (
                      <div className="text-center">
                        <p className="text-xs text-gray-400 uppercase">Score</p>
                        <p className="font-bold text-violet-600">{result.visibility_score?.toFixed(0)}/100</p>
                      </div>
                    )}

                    {/* Brands Count */}
                    <div className="text-center">
                      <p className="text-xs text-gray-400 uppercase">Brands</p>
                      <p className="font-bold text-gray-700">{result.total_brands_mentioned}</p>
                    </div>

                    {/* Citations Count */}
                    <div className="text-center">
                      <p className="text-xs text-gray-400 uppercase">Citations</p>
                      <p className="font-bold text-gray-700">{result.citations.length}</p>
                    </div>

                    <button className="p-2 rounded-lg hover:bg-gray-100">
                      {isExpanded ? <ChevronUp className="w-5 h-5" /> : <ChevronDown className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                {/* Expanded Content */}
                {isExpanded && (
                  <div className="mt-6 pt-6 border-t border-gray-100 space-y-6">
                    {/* Ranked Entities */}
                    <div>
                      <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                        <Award className="w-4 h-4 text-yellow-500" />
                        Who Ranked in Top Positions
                      </h4>

                      {result.ranked_entities.length === 0 ? (
                        <p className="text-gray-400 text-sm">No brands mentioned in response</p>
                      ) : (
                        <div className="space-y-2">
                          {result.ranked_entities.map((entity, idx) => (
                            <div
                              key={idx}
                              className={`p-4 rounded-xl ${
                                entity.is_own_brand
                                  ? "bg-gradient-to-r from-violet-50 to-indigo-50 ring-2 ring-violet-200"
                                  : "bg-gray-50"
                              }`}
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex items-start gap-3">
                                  {getPositionIcon(entity.position)}
                                  <div>
                                    <div className="flex items-center gap-2">
                                      <span className={`font-semibold ${entity.is_own_brand ? "text-violet-700" : "text-gray-900"}`}>
                                        {entity.name}
                                      </span>
                                      {entity.is_own_brand && (
                                        <span className="px-2 py-0.5 bg-violet-500 text-white text-xs rounded-full">
                                          Your Brand
                                        </span>
                                      )}
                                      <span className={`px-2 py-0.5 text-xs rounded-full ${getSentimentColor(entity.sentiment)}`}>
                                        {entity.sentiment}
                                      </span>
                                    </div>
                                    {entity.context && (
                                      <p className="text-sm text-gray-600 mt-1 flex items-start gap-1">
                                        <Quote className="w-3 h-3 mt-1 text-gray-400 flex-shrink-0" />
                                        <span className="italic">{entity.context}</span>
                                      </p>
                                    )}
                                    <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                                      <span>Match: {entity.match_type}</span>
                                      <span>Confidence: {(entity.match_confidence * 100).toFixed(0)}%</span>
                                    </div>
                                  </div>
                                </div>
                                {getPositionBadge(entity.position, entity.is_own_brand)}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Citations */}
                    <div>
                      <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                        <Link2 className="w-4 h-4 text-blue-500" />
                        Citations & Sources
                      </h4>

                      {result.citations.length === 0 ? (
                        <p className="text-gray-400 text-sm">No citations in response</p>
                      ) : (
                        <div className="space-y-2">
                          {result.citations.map((citation, idx) => (
                            <div
                              key={idx}
                              className={`p-4 rounded-xl ${
                                citation.is_our_domain
                                  ? "bg-gradient-to-r from-green-50 to-emerald-50 ring-2 ring-green-200"
                                  : "bg-gray-50"
                              }`}
                            >
                              <div className="flex items-start justify-between">
                                <div className="flex items-start gap-3">
                                  <div className={`p-2 rounded-lg ${citation.is_our_domain ? "bg-green-100" : "bg-gray-100"}`}>
                                    {getCategoryIcon(citation.category)}
                                  </div>
                                  <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2 flex-wrap">
                                      <span className={`font-medium ${citation.is_our_domain ? "text-green-700" : "text-gray-900"}`}>
                                        {citation.domain || "Unknown Domain"}
                                      </span>
                                      {citation.is_our_domain && (
                                        <span className="px-2 py-0.5 bg-green-500 text-white text-xs rounded-full">
                                          Your Domain
                                        </span>
                                      )}
                                      <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs rounded-full capitalize">
                                        {citation.category.replace("_", " ")}
                                      </span>
                                      {citation.domain_authority && (
                                        <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">
                                          DA: {citation.domain_authority}
                                        </span>
                                      )}
                                    </div>

                                    <a
                                      href={citation.url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-sm text-blue-600 hover:underline flex items-center gap-1 mt-1 truncate"
                                    >
                                      {citation.url}
                                      <ExternalLink className="w-3 h-3 flex-shrink-0" />
                                    </a>

                                    {citation.anchor_text && (
                                      <p className="text-sm text-gray-500 mt-1">
                                        <span className="text-gray-400">Anchor:</span> {citation.anchor_text}
                                      </p>
                                    )}

                                    {citation.context && (
                                      <p className="text-sm text-gray-600 mt-2 flex items-start gap-1">
                                        <Quote className="w-3 h-3 mt-1 text-gray-400 flex-shrink-0" />
                                        <span className="italic">{citation.context}</span>
                                      </p>
                                    )}

                                    {/* Citation Status */}
                                    <div className="flex items-center gap-3 mt-2 text-xs">
                                      {citation.is_valid !== null && (
                                        <span className={`flex items-center gap-1 ${citation.is_valid ? "text-green-600" : "text-red-600"}`}>
                                          {citation.is_valid ? <CheckCircle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                                          {citation.is_valid ? "Valid URL" : "Invalid URL"}
                                        </span>
                                      )}
                                      {citation.is_accessible !== null && (
                                        <span className={`flex items-center gap-1 ${citation.is_accessible ? "text-green-600" : "text-amber-600"}`}>
                                          {citation.is_accessible ? <CheckCircle className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                                          {citation.is_accessible ? "Accessible" : "Not Accessible"}
                                        </span>
                                      )}
                                      {citation.is_hallucinated && (
                                        <span className="flex items-center gap-1 text-red-600">
                                          <AlertTriangle className="w-3 h-3" />
                                          Hallucinated
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                </div>
                                {citation.position && (
                                  <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded-full">
                                    #{citation.position}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Fan-out Queries */}
                    {result.fan_out_queries && result.fan_out_queries.length > 0 && (
                      <div>
                        <h4 className="font-semibold text-gray-900 mb-3 flex items-center gap-2">
                          <Search className="w-4 h-4 text-amber-500" />
                          Web Search Queries (Fan-out)
                        </h4>
                        <div className="flex flex-wrap gap-2">
                          {result.fan_out_queries.map((query, idx) => (
                            <span key={idx} className="px-3 py-1 bg-amber-50 text-amber-700 rounded-full text-sm">
                              {query}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Raw Response Toggle */}
                    {result.raw_response && (
                      <div>
                        <button
                          onClick={() => setShowRawResponse(showRawResponse === provider ? null : provider)}
                          className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
                        >
                          {showRawResponse === provider ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                          {showRawResponse === provider ? "Hide" : "Show"} Raw Response
                        </button>

                        {showRawResponse === provider && (
                          <div className="mt-3 p-4 bg-gray-900 text-gray-100 rounded-xl text-sm font-mono overflow-x-auto max-h-96 overflow-y-auto">
                            <pre className="whitespace-pre-wrap">{result.raw_response}</pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
