"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { visibilityApi, projectsApi } from "@/lib/api";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Award,
  Target,
  Link2,
  FileText,
  Lightbulb,
  ExternalLink,
  RefreshCw,
  Search,
  BarChart3,
  PieChart,
  ArrowUpRight,
  ArrowDownRight,
  ChevronRight,
  CheckCircle,
  AlertCircle,
  Zap,
  Globe,
} from "lucide-react";

export default function VisibilityPage() {
  const [selectedProject, setSelectedProject] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "citations" | "opportunities" | "gaps" | "volume">("overview");
  const queryClient = useQueryClient();

  // Fetch projects
  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: () => projectsApi.list(),
  });

  const projects = projectsData?.data?.items || [];

  // Set first project as default
  useEffect(() => {
    if (projects.length > 0 && !selectedProject) {
      setSelectedProject(projects[0].id);
    }
  }, [projects, selectedProject]);

  // Fetch visibility dashboard
  const { data: dashboardData, isLoading: dashboardLoading } = useQuery({
    queryKey: ["visibility-dashboard", selectedProject],
    queryFn: () => visibilityApi.getDashboard(selectedProject!, 30),
    enabled: !!selectedProject,
  });

  // Fetch citation sources
  const { data: sourcesData } = useQuery({
    queryKey: ["citation-sources", selectedProject],
    queryFn: () => visibilityApi.getCitationSources(selectedProject!, 20),
    enabled: !!selectedProject && activeTab === "citations",
  });

  // Fetch outreach opportunities
  const { data: opportunitiesData } = useQuery({
    queryKey: ["opportunities", selectedProject],
    queryFn: () => visibilityApi.getOutreachOpportunities(selectedProject!, undefined, 20),
    enabled: !!selectedProject && activeTab === "opportunities",
  });

  // Fetch content gaps
  const { data: gapsData } = useQuery({
    queryKey: ["content-gaps", selectedProject],
    queryFn: () => visibilityApi.getContentGaps(selectedProject!, undefined, false, 20),
    enabled: !!selectedProject && activeTab === "gaps",
  });

  // Generate opportunities mutation
  const generateOpportunities = useMutation({
    mutationFn: () => visibilityApi.generateOpportunities(selectedProject!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["opportunities"] });
    },
  });

  // Detect gaps mutation
  const detectGaps = useMutation({
    mutationFn: () => visibilityApi.detectContentGaps(selectedProject!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["content-gaps"] });
    },
  });

  // Fetch volume estimates
  const { data: volumeData } = useQuery({
    queryKey: ["volume-estimates", selectedProject],
    queryFn: () => visibilityApi.getVolumeSummary(selectedProject!),
    enabled: !!selectedProject && activeTab === "volume",
  });

  // Generate volume estimates mutation
  const generateVolume = useMutation({
    mutationFn: () => visibilityApi.generateVolumeEstimates(selectedProject!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["volume-estimates"] });
    },
  });

  const dashboard = dashboardData?.data;
  const sources = sourcesData?.data || [];
  const opportunities = opportunitiesData?.data || [];
  const gaps = gapsData?.data || [];
  const volumeSummary = volumeData?.data;

  const getTrendIcon = (trend: string) => {
    if (trend === "up") return <TrendingUp className="w-4 h-4 text-green-500" />;
    if (trend === "down") return <TrendingDown className="w-4 h-4 text-red-500" />;
    return <Minus className="w-4 h-4 text-gray-400" />;
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "critical": return "bg-red-100 text-red-700 border-red-200";
      case "high": return "bg-orange-100 text-orange-700 border-orange-200";
      case "medium": return "bg-yellow-100 text-yellow-700 border-yellow-200";
      default: return "bg-gray-100 text-gray-700 border-gray-200";
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-violet-50">
      {/* Header */}
      <div className="border-b border-gray-200/50 bg-white/80 backdrop-blur-xl sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-violet-600 to-indigo-600 bg-clip-text text-transparent">
                Visibility Analytics
              </h1>
              <p className="text-gray-500 text-sm mt-1">
                Track Share of Voice, Citations, and AI Visibility
              </p>
            </div>
            <div className="flex items-center gap-4">
              <select
                value={selectedProject || ""}
                onChange={(e) => setSelectedProject(e.target.value)}
                className="px-4 py-2 border border-gray-200 rounded-xl bg-white/80 backdrop-blur text-sm focus:outline-none focus:ring-2 focus:ring-violet-500/20"
              >
                {projects.map((project: { id: string; name: string }) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 mt-4 bg-gray-100/50 rounded-xl p-1 w-fit">
            {[
              { id: "overview", label: "Overview", icon: BarChart3 },
              { id: "citations", label: "Citations", icon: Link2 },
              { id: "opportunities", label: "Outreach", icon: Lightbulb },
              { id: "gaps", label: "Content Gaps", icon: FileText },
              { id: "volume", label: "AI Volume", icon: TrendingUp },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as typeof activeTab)}
                className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                  activeTab === tab.id
                    ? "bg-white shadow-sm text-violet-600"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-8">
        {dashboardLoading ? (
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="w-8 h-8 text-violet-500 animate-spin" />
          </div>
        ) : (
          <>
            {/* Overview Tab */}
            {activeTab === "overview" && dashboard && (
              <div className="space-y-8">
                {/* Key Metrics */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
                  {/* Share of Voice */}
                  <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                    <div className="flex items-center justify-between mb-4">
                      <div className="p-3 bg-violet-100 rounded-xl">
                        <PieChart className="w-6 h-6 text-violet-600" />
                      </div>
                      <div className="flex items-center gap-1 text-sm">
                        {getTrendIcon(dashboard.share_of_voice?.trend)}
                        <span className={dashboard.share_of_voice?.trend === "up" ? "text-green-600" : dashboard.share_of_voice?.trend === "down" ? "text-red-600" : "text-gray-500"}>
                          {dashboard.share_of_voice?.trend_change?.toFixed(1)}%
                        </span>
                      </div>
                    </div>
                    <p className="text-gray-500 text-sm">Share of Voice</p>
                    <p className="text-3xl font-bold text-gray-900 mt-1">
                      {dashboard.share_of_voice?.share_of_voice?.toFixed(1) || 0}%
                    </p>
                    <p className="text-xs text-gray-400 mt-2">
                      {dashboard.share_of_voice?.total_mentions || 0} mentions in {dashboard.share_of_voice?.total_responses || 0} responses
                    </p>
                  </div>

                  {/* Average Position */}
                  <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                    <div className="flex items-center justify-between mb-4">
                      <div className="p-3 bg-blue-100 rounded-xl">
                        <Award className="w-6 h-6 text-blue-600" />
                      </div>
                      <div className="flex items-center gap-1 text-sm">
                        {dashboard.position_summary?.position_trend === "up" ? (
                          <ArrowUpRight className="w-4 h-4 text-green-500" />
                        ) : dashboard.position_summary?.position_trend === "down" ? (
                          <ArrowDownRight className="w-4 h-4 text-red-500" />
                        ) : null}
                      </div>
                    </div>
                    <p className="text-gray-500 text-sm">Average Position</p>
                    <p className="text-3xl font-bold text-gray-900 mt-1">
                      #{dashboard.position_summary?.avg_position?.toFixed(1) || "N/A"}
                    </p>
                    <p className="text-xs text-gray-400 mt-2">
                      Best: #{dashboard.position_summary?.best_position || "N/A"}
                    </p>
                  </div>

                  {/* Citation Rate */}
                  <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                    <div className="flex items-center justify-between mb-4">
                      <div className="p-3 bg-green-100 rounded-xl">
                        <Link2 className="w-6 h-6 text-green-600" />
                      </div>
                    </div>
                    <p className="text-gray-500 text-sm">Our Citation Rate</p>
                    <p className="text-3xl font-bold text-gray-900 mt-1">
                      {dashboard.citation_summary?.our_citation_rate?.toFixed(1) || 0}%
                    </p>
                    <p className="text-xs text-gray-400 mt-2">
                      {dashboard.citation_summary?.our_domain_citations || 0} of {dashboard.citation_summary?.total_citations || 0} citations
                    </p>
                  </div>

                  {/* Action Items */}
                  <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow">
                    <div className="flex items-center justify-between mb-4">
                      <div className="p-3 bg-orange-100 rounded-xl">
                        <Zap className="w-6 h-6 text-orange-600" />
                      </div>
                    </div>
                    <p className="text-gray-500 text-sm">Action Items</p>
                    <p className="text-3xl font-bold text-gray-900 mt-1">
                      {dashboard.citation_summary?.action_items || 0}
                    </p>
                    <p className="text-xs text-gray-400 mt-2">
                      {dashboard.citation_summary?.new_outreach_opportunities || 0} outreach + {dashboard.citation_summary?.open_content_gaps || 0} gaps
                    </p>
                  </div>
                </div>

                {/* Competitor Comparison */}
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Competitor Share of Voice</h3>
                  <div className="space-y-4">
                    {Object.entries(dashboard.share_of_voice?.competitor_shares || {}).map(([name, share]: [string, unknown]) => (
                      <div key={name} className="flex items-center gap-4">
                        <div className="w-32 text-sm text-gray-700 truncate">{name}</div>
                        <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
                          <div
                            className="h-full bg-gradient-to-r from-red-400 to-red-500 rounded-full transition-all duration-500"
                            style={{ width: `${Math.min(100, share as number)}%` }}
                          />
                        </div>
                        <div className="w-16 text-sm font-medium text-gray-900 text-right">
                          {(share as number).toFixed(1)}%
                        </div>
                      </div>
                    ))}
                    {Object.keys(dashboard.share_of_voice?.competitor_shares || {}).length === 0 && (
                      <p className="text-gray-500 text-sm">No competitor data yet. Run more analyses to see competitor comparison.</p>
                    )}
                  </div>
                </div>

                {/* Recent Analyses */}
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Analyses</h3>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-gray-100">
                          <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Keyword</th>
                          <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">LLM</th>
                          <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Mentioned</th>
                          <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Score</th>
                          <th className="text-left py-3 px-4 text-sm font-medium text-gray-500">Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dashboard.recent_analyses?.map((analysis: {
                          keyword: string;
                          provider: string;
                          brand_mentioned: boolean;
                          visibility_score: number;
                          date: string;
                        }, i: number) => (
                          <tr key={i} className="border-b border-gray-50 hover:bg-gray-50/50">
                            <td className="py-3 px-4 text-sm text-gray-900">{analysis.keyword}</td>
                            <td className="py-3 px-4">
                              <span className="px-2 py-1 text-xs font-medium rounded-full bg-violet-100 text-violet-700">
                                {analysis.provider}
                              </span>
                            </td>
                            <td className="py-3 px-4">
                              {analysis.brand_mentioned ? (
                                <CheckCircle className="w-5 h-5 text-green-500" />
                              ) : (
                                <AlertCircle className="w-5 h-5 text-gray-300" />
                              )}
                            </td>
                            <td className="py-3 px-4">
                              <div className="flex items-center gap-2">
                                <div className="w-16 bg-gray-100 rounded-full h-2 overflow-hidden">
                                  <div
                                    className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full"
                                    style={{ width: `${analysis.visibility_score}%` }}
                                  />
                                </div>
                                <span className="text-sm font-medium text-gray-900">
                                  {analysis.visibility_score?.toFixed(0)}
                                </span>
                              </div>
                            </td>
                            <td className="py-3 px-4 text-sm text-gray-500">
                              {new Date(analysis.date).toLocaleDateString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {(!dashboard.recent_analyses || dashboard.recent_analyses.length === 0) && (
                      <p className="text-center text-gray-500 py-8">No analyses yet. Run your first analysis to see results.</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Citations Tab */}
            {activeTab === "citations" && (
              <div className="space-y-6">
                <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Citation Sources</h3>
                  <p className="text-gray-500 text-sm mb-6">
                    Sources most frequently cited by AI models. These are high-authority pages influencing AI responses.
                  </p>
                  <div className="space-y-4">
                    {sources.map((source: {
                      rank: number;
                      domain: string;
                      site_name?: string;
                      citation_count: number;
                      avg_position?: number;
                      authority_score: number;
                      category: string;
                    }) => (
                      <div
                        key={source.rank}
                        className="flex items-center gap-4 p-4 bg-gray-50/50 rounded-xl hover:bg-gray-100/50 transition-colors"
                      >
                        <div className="w-8 h-8 bg-violet-100 rounded-lg flex items-center justify-center text-sm font-bold text-violet-600">
                          {source.rank}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <Globe className="w-4 h-4 text-gray-400" />
                            <span className="font-medium text-gray-900 truncate">{source.domain}</span>
                            <a
                              href={`https://${source.domain}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-violet-500 hover:text-violet-700"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </a>
                          </div>
                          <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                            <span>{source.citation_count} citations</span>
                            {source.avg_position && (
                              <span>Avg position: #{source.avg_position.toFixed(1)}</span>
                            )}
                            <span className="px-2 py-0.5 bg-gray-200 rounded-full">{source.category}</span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-lg font-bold text-violet-600">
                            {source.authority_score.toFixed(0)}
                          </div>
                          <div className="text-xs text-gray-400">authority</div>
                        </div>
                      </div>
                    ))}
                    {sources.length === 0 && (
                      <p className="text-center text-gray-500 py-8">No citation data yet. Run analyses to see cited sources.</p>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Opportunities Tab */}
            {activeTab === "opportunities" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">Outreach Opportunities</h3>
                    <p className="text-gray-500 text-sm">
                      Pages frequently cited by AI that don&apos;t mention your brand. Reach out for backlinks or mentions.
                    </p>
                  </div>
                  <button
                    onClick={() => generateOpportunities.mutate()}
                    disabled={generateOpportunities.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-xl hover:bg-violet-700 transition-colors disabled:opacity-50"
                  >
                    {generateOpportunities.isPending ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <Search className="w-4 h-4" />
                    )}
                    Find Opportunities
                  </button>
                </div>

                <div className="grid gap-4">
                  {opportunities.map((opp: {
                    id: string;
                    page_url: string;
                    page_domain: string;
                    opportunity_reason: string;
                    citation_count: number;
                    llms_citing: string[];
                    priority_score: number;
                    impact_estimate: string;
                    relevant_keywords: string[];
                    status: string;
                  }) => (
                    <div
                      key={opp.id}
                      className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2 mb-2">
                            <Globe className="w-5 h-5 text-gray-400" />
                            <a
                              href={opp.page_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-medium text-gray-900 hover:text-violet-600 flex items-center gap-1"
                            >
                              {opp.page_domain}
                              <ExternalLink className="w-4 h-4" />
                            </a>
                          </div>
                          <p className="text-gray-600 text-sm mb-3">{opp.opportunity_reason}</p>
                          <div className="flex flex-wrap gap-2">
                            <span className="px-2 py-1 text-xs font-medium rounded-full bg-violet-100 text-violet-700">
                              {opp.citation_count} citations
                            </span>
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                              opp.impact_estimate === "high" ? "bg-green-100 text-green-700" :
                              opp.impact_estimate === "medium" ? "bg-yellow-100 text-yellow-700" :
                              "bg-gray-100 text-gray-700"
                            }`}>
                              {opp.impact_estimate} impact
                            </span>
                            {opp.llms_citing.slice(0, 3).map((llm: string) => (
                              <span key={llm} className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-600">
                                {llm}
                              </span>
                            ))}
                          </div>
                          {opp.relevant_keywords.length > 0 && (
                            <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
                              <span>Keywords:</span>
                              {opp.relevant_keywords.slice(0, 3).map((kw: string, i: number) => (
                                <span key={i} className="text-gray-700">{kw}{i < 2 && opp.relevant_keywords.length > i + 1 ? "," : ""}</span>
                              ))}
                              {opp.relevant_keywords.length > 3 && (
                                <span>+{opp.relevant_keywords.length - 3} more</span>
                              )}
                            </div>
                          )}
                        </div>
                        <div className="flex flex-col items-end gap-2">
                          <div className="text-2xl font-bold text-violet-600">
                            {opp.priority_score.toFixed(0)}
                          </div>
                          <div className="text-xs text-gray-400">priority</div>
                          <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                            opp.status === "new" ? "bg-blue-100 text-blue-700" :
                            opp.status === "contacted" ? "bg-yellow-100 text-yellow-700" :
                            opp.status === "completed" ? "bg-green-100 text-green-700" :
                            "bg-gray-100 text-gray-700"
                          }`}>
                            {opp.status}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                  {opportunities.length === 0 && (
                    <div className="bg-white rounded-2xl p-12 shadow-sm border border-gray-100 text-center">
                      <Lightbulb className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                      <p className="text-gray-500">No outreach opportunities found yet.</p>
                      <p className="text-gray-400 text-sm mt-1">Run analyses and click &quot;Find Opportunities&quot; to discover pages to reach out to.</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Content Gaps Tab */}
            {activeTab === "gaps" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">Content Gaps</h3>
                    <p className="text-gray-500 text-sm">
                      Content types getting cited that you don&apos;t have. Create content to fill these gaps.
                    </p>
                  </div>
                  <button
                    onClick={() => detectGaps.mutate()}
                    disabled={detectGaps.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-xl hover:bg-violet-700 transition-colors disabled:opacity-50"
                  >
                    {detectGaps.isPending ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <Search className="w-4 h-4" />
                    )}
                    Detect Gaps
                  </button>
                </div>

                <div className="grid gap-4">
                  {gaps.map((gap: {
                    id: string;
                    gap_type: string;
                    gap_description: string;
                    related_keywords: string[];
                    content_type_needed: string;
                    opportunity_score: number;
                    recommended_action: string;
                    action_items: string[];
                    priority: string;
                    competitor_examples: { competitor?: string; url?: string }[];
                  }) => (
                    <div
                      key={gap.id}
                      className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 hover:shadow-md transition-shadow"
                    >
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <div className={`p-2 rounded-xl ${
                            gap.gap_type === "competitor_only" ? "bg-red-100" :
                            gap.gap_type === "missing_page" ? "bg-orange-100" :
                            "bg-yellow-100"
                          }`}>
                            <FileText className={`w-5 h-5 ${
                              gap.gap_type === "competitor_only" ? "text-red-600" :
                              gap.gap_type === "missing_page" ? "text-orange-600" :
                              "text-yellow-600"
                            }`} />
                          </div>
                          <div>
                            <span className={`px-2 py-1 text-xs font-medium rounded-full border ${getPriorityColor(gap.priority)}`}>
                              {gap.priority}
                            </span>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-bold text-violet-600">
                            {gap.opportunity_score.toFixed(0)}
                          </div>
                          <div className="text-xs text-gray-400">opportunity</div>
                        </div>
                      </div>

                      <p className="text-gray-900 font-medium mb-2">{gap.gap_description}</p>
                      <p className="text-gray-600 text-sm mb-4">{gap.recommended_action}</p>

                      <div className="flex flex-wrap gap-2 mb-4">
                        <span className="px-2 py-1 text-xs font-medium rounded-full bg-violet-100 text-violet-700">
                          {gap.content_type_needed}
                        </span>
                        {gap.related_keywords.slice(0, 3).map((kw: string, i: number) => (
                          <span key={i} className="px-2 py-1 text-xs font-medium rounded-full bg-gray-100 text-gray-600">
                            {kw}
                          </span>
                        ))}
                      </div>

                      {gap.action_items && gap.action_items.length > 0 && (
                        <div className="border-t border-gray-100 pt-4">
                          <h4 className="text-sm font-medium text-gray-700 mb-2">Action Items:</h4>
                          <ul className="space-y-1">
                            {gap.action_items.slice(0, 3).map((item: string, i: number) => (
                              <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                                <ChevronRight className="w-4 h-4 text-gray-400 flex-shrink-0 mt-0.5" />
                                {item}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {gap.competitor_examples && gap.competitor_examples.length > 0 && (
                        <div className="mt-4 p-3 bg-red-50 rounded-xl">
                          <h4 className="text-sm font-medium text-red-700 mb-1">Competitor Content:</h4>
                          <div className="flex flex-wrap gap-2">
                            {gap.competitor_examples.slice(0, 2).map((ex: { competitor?: string; url?: string }, i: number) => (
                              <a
                                key={i}
                                href={ex.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-red-600 hover:text-red-800 flex items-center gap-1"
                              >
                                {ex.competitor || "Competitor"}
                                <ExternalLink className="w-3 h-3" />
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                  {gaps.length === 0 && (
                    <div className="bg-white rounded-2xl p-12 shadow-sm border border-gray-100 text-center">
                      <FileText className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                      <p className="text-gray-500">No content gaps detected yet.</p>
                      <p className="text-gray-400 text-sm mt-1">Run analyses and click &quot;Detect Gaps&quot; to find content opportunities.</p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* AI Volume Tab */}
            {activeTab === "volume" && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">Monthly AI Prompt Volume</h3>
                    <p className="text-gray-500 text-sm">
                      Estimated monthly AI conversations for your topics across all chatbots.
                    </p>
                  </div>
                  <button
                    onClick={() => generateVolume.mutate()}
                    disabled={generateVolume.isPending}
                    className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-xl hover:bg-violet-700 transition-colors disabled:opacity-50"
                  >
                    {generateVolume.isPending ? (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    ) : (
                      <BarChart3 className="w-4 h-4" />
                    )}
                    Estimate Volume
                  </button>
                </div>

                {volumeSummary ? (
                  <>
                    {/* Volume Summary Cards */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                        <div className="flex items-center justify-between mb-4">
                          <div className="p-3 bg-violet-100 rounded-xl">
                            <TrendingUp className="w-6 h-6 text-violet-600" />
                          </div>
                        </div>
                        <p className="text-gray-500 text-sm">Total Monthly Volume</p>
                        <p className="text-3xl font-bold text-gray-900 mt-1">
                          {(volumeSummary.total_monthly_volume || 0).toLocaleString()}
                        </p>
                        <p className="text-xs text-gray-400 mt-2">
                          Estimated AI prompts/month for your topics
                        </p>
                      </div>

                      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                        <div className="flex items-center justify-between mb-4">
                          <div className="p-3 bg-green-100 rounded-xl">
                            <Zap className="w-6 h-6 text-green-600" />
                          </div>
                        </div>
                        <p className="text-gray-500 text-sm">High Opportunity Topics</p>
                        <p className="text-3xl font-bold text-gray-900 mt-1">
                          {volumeSummary.opportunity_summary?.high || 0}
                        </p>
                        <p className="text-xs text-gray-400 mt-2">
                          Topics with high volume + low competition
                        </p>
                      </div>

                      <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                        <div className="flex items-center justify-between mb-4">
                          <div className="p-3 bg-blue-100 rounded-xl">
                            <Target className="w-6 h-6 text-blue-600" />
                          </div>
                        </div>
                        <p className="text-gray-500 text-sm">Keywords Tracked</p>
                        <p className="text-3xl font-bold text-gray-900 mt-1">
                          {volumeSummary.total_keywords || 0}
                        </p>
                        <p className="text-xs text-gray-400 mt-2">
                          Topics being monitored
                        </p>
                      </div>
                    </div>

                    {/* Platform Breakdown */}
                    <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                      <h3 className="text-lg font-semibold text-gray-900 mb-4">Volume by Platform</h3>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                        {Object.entries(volumeSummary.platform_breakdown || {}).map(([platform, volume]) => (
                          <div key={platform} className="text-center p-4 bg-gray-50 rounded-xl">
                            <p className="text-2xl font-bold text-gray-900">
                              {((volume as number) / 1000).toFixed(1)}K
                            </p>
                            <p className="text-sm text-gray-500 capitalize mt-1">{platform}</p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Top Topics */}
                    <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
                      <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Topics by Volume</h3>
                      <div className="space-y-4">
                        {(volumeSummary.top_topics || []).map((topic: {
                          topic: string;
                          volume: number;
                          opportunity_score: number;
                          competition: string;
                        }, i: number) => (
                          <div
                            key={i}
                            className="flex items-center gap-4 p-4 bg-gray-50/50 rounded-xl"
                          >
                            <div className="w-8 h-8 bg-violet-100 rounded-lg flex items-center justify-center text-sm font-bold text-violet-600">
                              {i + 1}
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="font-medium text-gray-900 truncate">{topic.topic}</p>
                              <div className="flex items-center gap-4 mt-1 text-xs text-gray-500">
                                <span>{topic.volume.toLocaleString()} prompts/mo</span>
                                <span className={`px-2 py-0.5 rounded-full ${
                                  topic.competition === "low" ? "bg-green-100 text-green-700" :
                                  topic.competition === "medium" ? "bg-yellow-100 text-yellow-700" :
                                  "bg-red-100 text-red-700"
                                }`}>
                                  {topic.competition} competition
                                </span>
                              </div>
                            </div>
                            <div className="text-right">
                              <div className="text-lg font-bold text-violet-600">
                                {topic.opportunity_score.toFixed(0)}
                              </div>
                              <div className="text-xs text-gray-400">opportunity</div>
                            </div>
                          </div>
                        ))}
                        {(!volumeSummary.top_topics || volumeSummary.top_topics.length === 0) && (
                          <p className="text-center text-gray-500 py-4">No volume data yet.</p>
                        )}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="bg-white rounded-2xl p-12 shadow-sm border border-gray-100 text-center">
                    <TrendingUp className="w-12 h-12 text-gray-300 mx-auto mb-4" />
                    <p className="text-gray-500">No volume estimates yet.</p>
                    <p className="text-gray-400 text-sm mt-1">
                      Click &quot;Estimate Volume&quot; to see monthly AI conversation estimates for your topics.
                    </p>
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
