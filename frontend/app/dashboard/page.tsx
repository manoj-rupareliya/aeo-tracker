"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScoreChart } from "@/components/charts/score-chart";
import { LLMBreakdownChart } from "@/components/charts/llm-breakdown-chart";
import { dashboardApi, projectsApi } from "@/lib/api";
import { useProjectStore } from "@/lib/store";
import {
  formatScore,
  getScoreClass,
  formatPercent,
  LLM_DISPLAY_NAMES,
} from "@/lib/utils";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  AlertCircle,
  RefreshCw,
  Zap,
  Target,
  GitBranch,
  DollarSign,
  BarChart3,
  Lightbulb,
  Activity,
} from "lucide-react";
import Link from "next/link";

export default function DashboardPage() {
  const { currentProject, setCurrentProject, projects, setProjects } = useProjectStore();
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

  // Fetch projects if not loaded
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
      if (!currentProject && projectsData.items.length > 0) {
        setCurrentProject(projectsData.items[0]);
        setSelectedProjectId(projectsData.items[0].id);
      }
    }
  }, [projectsData, currentProject, setCurrentProject, setProjects]);

  // Fetch dashboard data
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ["dashboard-overview", selectedProjectId],
    queryFn: async () => {
      if (!selectedProjectId) return null;
      const response = await dashboardApi.getOverview(selectedProjectId);
      return response.data;
    },
    enabled: !!selectedProjectId,
  });

  const { data: llmBreakdown } = useQuery({
    queryKey: ["llm-breakdown", selectedProjectId],
    queryFn: async () => {
      if (!selectedProjectId) return null;
      const response = await dashboardApi.getLLMBreakdown(selectedProjectId);
      return response.data;
    },
    enabled: !!selectedProjectId,
  });

  const { data: timeSeries } = useQuery({
    queryKey: ["time-series", selectedProjectId],
    queryFn: async () => {
      if (!selectedProjectId) return null;
      const response = await dashboardApi.getTimeSeries(selectedProjectId);
      return response.data;
    },
    enabled: !!selectedProjectId,
  });

  // V2 Data - SAIV, Drift, Recommendations
  const { data: saivData } = useQuery({
    queryKey: ["saiv-current", selectedProjectId],
    queryFn: async () => {
      if (!selectedProjectId) return null;
      // Mock data for now - replace with actual API call
      return {
        overall_saiv: 23.5,
        trend_direction: "up",
        saiv_delta: 2.3,
        by_llm: {
          openai: 28.4,
          anthropic: 22.1,
          google: 18.9,
          perplexity: 24.6,
        },
        top_competitor: { name: "Competitor A", saiv: 31.2 },
      };
    },
    enabled: !!selectedProjectId,
  });

  const { data: driftData } = useQuery({
    queryKey: ["drift-summary", selectedProjectId],
    queryFn: async () => {
      if (!selectedProjectId) return null;
      // Mock data for now - replace with actual API call
      return {
        total_drifts: 12,
        critical: 1,
        major: 3,
        moderate: 5,
        minor: 3,
        recent_alerts: [
          { type: "brand_disappeared", severity: "critical", provider: "openai", description: "Brand disappeared from 'best analytics tools' query" },
          { type: "position_declined", severity: "major", provider: "anthropic", description: "Position dropped from #2 to #5" },
        ],
      };
    },
    enabled: !!selectedProjectId,
  });

  const { data: recommendationsData } = useQuery({
    queryKey: ["recommendations-summary", selectedProjectId],
    queryFn: async () => {
      if (!selectedProjectId) return null;
      // Mock data for now - replace with actual API call
      return {
        total_active: 8,
        high_priority: 3,
        top_recommendations: [
          { title: "Get listed on G2", type: "get_listed", priority: 85, effort: "medium" },
          { title: "Improve visibility for 'data analytics'", type: "target_keyword", priority: 72, effort: "low" },
          { title: "Address competitor advantage: Competitor A", type: "competitor_gap", priority: 68, effort: "high" },
        ],
      };
    },
    enabled: !!selectedProjectId,
  });

  const { data: costData } = useQuery({
    queryKey: ["cost-summary", selectedProjectId],
    queryFn: async () => {
      if (!selectedProjectId) return null;
      // Mock data for now - replace with actual API call
      return {
        cost_today_usd: 2.34,
        cost_this_month_usd: 45.67,
        tokens_today: 23400,
        cache_hit_rate: 0.42,
        budget_remaining_percent: 77,
      };
    },
    enabled: !!selectedProjectId,
  });

  if (!projects.length) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <h2 className="text-xl font-semibold text-gray-900 mb-2">
          Welcome to llmrefs.com
        </h2>
        <p className="text-gray-600 mb-6">
          Create your first project to start tracking LLM visibility.
        </p>
        <Link href="/dashboard/projects/new">
          <Button>Create Project</Button>
        </Link>
      </div>
    );
  }

  if (overviewLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-gray-200 rounded w-1/4" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 bg-gray-200 rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            {overview?.project_name || "Dashboard"}
          </h1>
          <p className="text-sm text-gray-500">
            LLM Visibility & GEO Intelligence Platform
          </p>
        </div>
        <div className="flex gap-3">
          <Link href="/dashboard/audit">
            <Button variant="outline" size="sm">
              <Activity className="h-4 w-4 mr-2" />
              Audit Trail
            </Button>
          </Link>
          <Button>
            <RefreshCw className="h-4 w-4 mr-2" />
            Run Analysis
          </Button>
        </div>
      </div>

      {/* V2 Key Metrics - SAIV Prominent */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        {/* SAIV - Primary Metric */}
        <Card className="md:col-span-2 bg-gradient-to-br from-primary-50 to-white border-primary-200">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-primary-600">Share of AI Voice</p>
                <p className="text-4xl font-bold text-primary-900 mt-1">
                  {saivData?.overall_saiv?.toFixed(1)}%
                </p>
                <p className={`text-sm mt-1 flex items-center gap-1 ${
                  saivData?.trend_direction === "up" ? "text-success-600" :
                  saivData?.trend_direction === "down" ? "text-danger-600" : "text-gray-500"
                }`}>
                  {saivData?.trend_direction === "up" ? <TrendingUp className="h-4 w-4" /> :
                   saivData?.trend_direction === "down" ? <TrendingDown className="h-4 w-4" /> :
                   <Minus className="h-4 w-4" />}
                  {saivData?.saiv_delta > 0 ? "+" : ""}{saivData?.saiv_delta?.toFixed(1)}% vs last week
                </p>
              </div>
              <div className="text-right">
                <p className="text-xs text-gray-500">Top Competitor</p>
                <p className="text-lg font-semibold text-gray-700">
                  {saivData?.top_competitor?.name}
                </p>
                <p className="text-sm text-gray-500">
                  {saivData?.top_competitor?.saiv?.toFixed(1)}% SAIV
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Other Key Metrics */}
        <MetricCard
          label="Visibility Score"
          value={formatScore(overview?.visibility_score?.value || 0)}
          trend={overview?.visibility_score?.trend || "stable"}
          trendDelta={overview?.visibility_score?.trend_delta}
          icon={<BarChart3 className="h-5 w-5 text-gray-400" />}
        />
        <MetricCard
          label="Mention Rate"
          value={formatPercent(overview?.mention_rate?.value || 0)}
          trend={overview?.mention_rate?.trend || "stable"}
          icon={<Target className="h-5 w-5 text-gray-400" />}
        />
        <MetricCard
          label="Citation Rate"
          value={formatPercent(overview?.citation_rate?.value || 0)}
          trend={overview?.citation_rate?.trend || "stable"}
          icon={<GitBranch className="h-5 w-5 text-gray-400" />}
        />
      </div>

      {/* Drift Alerts Banner */}
      {driftData && driftData.critical > 0 && (
        <div className="bg-danger-50 border border-danger-200 rounded-lg p-4">
          <div className="flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-danger-500 mt-0.5" />
            <div className="flex-1">
              <h3 className="font-semibold text-danger-800">Critical Drift Detected</h3>
              <p className="text-sm text-danger-700 mt-1">
                {driftData.recent_alerts[0]?.description}
              </p>
              <Link href="/dashboard/drift">
                <Button variant="outline" size="sm" className="mt-2 border-danger-300 text-danger-700 hover:bg-danger-100">
                  View All Drift Alerts
                </Button>
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Main Dashboard Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Visibility Trend - Larger */}
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Visibility & SAIV Trend</CardTitle>
            <Link href="/dashboard/saiv">
              <Button variant="ghost" size="sm">View Details</Button>
            </Link>
          </CardHeader>
          <CardContent>
            {timeSeries?.series ? (
              <ScoreChart data={timeSeries.series} />
            ) : (
              <div className="h-[300px] flex items-center justify-center text-gray-500">
                No data available yet
              </div>
            )}
          </CardContent>
        </Card>

        {/* SAIV by LLM */}
        <Card>
          <CardHeader>
            <CardTitle>SAIV by LLM</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {saivData?.by_llm && Object.entries(saivData.by_llm).map(([llm, value]) => (
                <div key={llm} className="space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="font-medium">{LLM_DISPLAY_NAMES[llm] || llm}</span>
                    <span className="text-gray-600">{(value as number).toFixed(1)}%</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary-500 rounded-full transition-all"
                      style={{ width: `${Math.min((value as number), 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Second Row - Recommendations and Drift */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* GEO Recommendations */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-warning-500" />
              <CardTitle>GEO Recommendations</CardTitle>
            </div>
            <span className="text-sm text-gray-500">
              {recommendationsData?.total_active} active
            </span>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recommendationsData?.top_recommendations?.map((rec, idx) => (
                <div key={idx} className="flex items-start gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className={`w-2 h-2 rounded-full mt-2 ${
                    rec.priority >= 80 ? "bg-danger-500" :
                    rec.priority >= 60 ? "bg-warning-500" : "bg-success-500"
                  }`} />
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{rec.title}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-xs px-2 py-0.5 bg-gray-200 rounded-full">
                        {rec.type.replace("_", " ")}
                      </span>
                      <span className="text-xs text-gray-500">
                        Effort: {rec.effort}
                      </span>
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-gray-600">
                    {rec.priority}
                  </span>
                </div>
              ))}
            </div>
            <Link href="/dashboard/recommendations">
              <Button variant="outline" className="w-full mt-4">
                View All Recommendations
              </Button>
            </Link>
          </CardContent>
        </Card>

        {/* Drift Summary */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="h-5 w-5 text-primary-500" />
              <CardTitle>Drift Detection</CardTitle>
            </div>
            <span className="text-sm text-gray-500">
              Last 7 days
            </span>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4 mb-4">
              <div className="text-center p-3 bg-danger-50 rounded-lg">
                <p className="text-2xl font-bold text-danger-600">{driftData?.critical || 0}</p>
                <p className="text-xs text-danger-500">Critical</p>
              </div>
              <div className="text-center p-3 bg-warning-50 rounded-lg">
                <p className="text-2xl font-bold text-warning-600">{driftData?.major || 0}</p>
                <p className="text-xs text-warning-500">Major</p>
              </div>
              <div className="text-center p-3 bg-blue-50 rounded-lg">
                <p className="text-2xl font-bold text-blue-600">{driftData?.moderate || 0}</p>
                <p className="text-xs text-blue-500">Moderate</p>
              </div>
              <div className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-2xl font-bold text-gray-600">{driftData?.minor || 0}</p>
                <p className="text-xs text-gray-500">Minor</p>
              </div>
            </div>

            <div className="space-y-2">
              {driftData?.recent_alerts?.slice(0, 2).map((alert, idx) => (
                <div key={idx} className={`p-3 rounded-lg ${
                  alert.severity === "critical" ? "bg-danger-50" :
                  alert.severity === "major" ? "bg-warning-50" : "bg-gray-50"
                }`}>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${
                      alert.severity === "critical" ? "bg-danger-200 text-danger-700" :
                      alert.severity === "major" ? "bg-warning-200 text-warning-700" :
                      "bg-gray-200 text-gray-700"
                    }`}>
                      {alert.severity}
                    </span>
                    <span className="text-xs text-gray-500">{alert.provider}</span>
                  </div>
                  <p className="text-sm text-gray-700 mt-1">{alert.description}</p>
                </div>
              ))}
            </div>
            <Link href="/dashboard/drift">
              <Button variant="outline" className="w-full mt-4">
                View Drift Timeline
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Bottom Row - Cost and Quick Stats */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Cost Governance */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-success-500" />
              <CardTitle className="text-base">Cost Today</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">${costData?.cost_today_usd?.toFixed(2)}</p>
            <p className="text-xs text-gray-500 mt-1">
              ${costData?.cost_this_month_usd?.toFixed(2)} this month
            </p>
            <div className="mt-3">
              <div className="flex justify-between text-xs mb-1">
                <span>Budget Used</span>
                <span>{100 - (costData?.budget_remaining_percent || 0)}%</span>
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    (100 - (costData?.budget_remaining_percent || 0)) > 80 ? "bg-danger-500" :
                    (100 - (costData?.budget_remaining_percent || 0)) > 60 ? "bg-warning-500" : "bg-success-500"
                  }`}
                  style={{ width: `${100 - (costData?.budget_remaining_percent || 0)}%` }}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Cache Performance */}
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-warning-500" />
              <CardTitle className="text-base">Cache Hit Rate</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{((costData?.cache_hit_rate || 0) * 100).toFixed(0)}%</p>
            <p className="text-xs text-gray-500 mt-1">
              {costData?.tokens_today?.toLocaleString()} tokens today
            </p>
          </CardContent>
        </Card>

        {/* Active LLMs */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Active LLMs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {overview?.active_llms?.map((llm: string) => (
                <span
                  key={llm}
                  className="px-2 py-1 bg-success-50 text-success-700 text-xs font-medium rounded-full"
                >
                  {LLM_DISPLAY_NAMES[llm] || llm}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Quick Actions */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Quick Actions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Link href="/dashboard/keywords" className="block">
                <Button variant="outline" size="sm" className="w-full justify-start">
                  Manage Keywords
                </Button>
              </Link>
              <Link href="/dashboard/graph" className="block">
                <Button variant="outline" size="sm" className="w-full justify-start">
                  View Preference Graph
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function MetricCard({
  label,
  value,
  trend,
  trendDelta,
  icon,
}: {
  label: string;
  value: string;
  trend: string;
  trendDelta?: number | null;
  icon?: React.ReactNode;
}) {
  const TrendIcon = () => {
    if (trend === "up") return <TrendingUp className="h-4 w-4 text-success-500" />;
    if (trend === "down") return <TrendingDown className="h-4 w-4 text-danger-500" />;
    return <Minus className="h-4 w-4 text-gray-400" />;
  };

  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {icon}
            <p className="text-sm font-medium text-gray-600">{label}</p>
          </div>
          <TrendIcon />
        </div>
        <p className="text-2xl font-bold mt-2">{value}</p>
        {trendDelta !== null && trendDelta !== undefined && (
          <p
            className={`text-xs mt-1 ${
              trendDelta > 0 ? "text-success-600" : trendDelta < 0 ? "text-danger-600" : "text-gray-500"
            }`}
          >
            {trendDelta > 0 ? "+" : ""}
            {trendDelta.toFixed(1)} vs last period
          </p>
        )}
      </CardContent>
    </Card>
  );
}
