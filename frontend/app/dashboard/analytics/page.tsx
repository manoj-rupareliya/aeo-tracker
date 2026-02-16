"use client";

import { useQuery } from "@tanstack/react-query";
import { useProjectStore } from "@/lib/store";
import { analysisApi, dashboardApi } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScoreChart } from "@/components/charts/score-chart";
import { LLMBreakdownChart } from "@/components/charts/llm-breakdown-chart";
import { formatScore, formatPercent, LLM_DISPLAY_NAMES } from "@/lib/utils";
import Link from "next/link";

export default function AnalyticsPage() {
  const { currentProject } = useProjectStore();

  const { data: timeSeries, isLoading: timeSeriesLoading } = useQuery({
    queryKey: ["time-series", currentProject?.id],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      const response = await dashboardApi.getTimeSeries(currentProject.id);
      return response.data;
    },
    enabled: !!currentProject?.id,
  });

  const { data: llmBreakdown, isLoading: llmLoading } = useQuery({
    queryKey: ["llm-breakdown", currentProject?.id],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      const response = await dashboardApi.getLLMBreakdown(currentProject.id);
      return response.data;
    },
    enabled: !!currentProject?.id,
  });

  const { data: keywordBreakdown } = useQuery({
    queryKey: ["keyword-breakdown", currentProject?.id],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      const response = await dashboardApi.getKeywordBreakdown(currentProject.id);
      return response.data;
    },
    enabled: !!currentProject?.id,
  });

  if (!currentProject) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px]">
        <p className="text-gray-600 mb-4">Please select a project first.</p>
        <Link href="/dashboard/projects">
          <Button>Go to Projects</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Analytics</h1>
          <p className="text-sm text-gray-500">
            Detailed analytics for {currentProject.name}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select className="input py-2 px-3 text-sm">
            <option>Last 7 days</option>
            <option>Last 30 days</option>
            <option>Last 90 days</option>
          </select>
        </div>
      </div>

      {/* Visibility Over Time */}
      <Card>
        <CardHeader>
          <CardTitle>Visibility Score Over Time</CardTitle>
        </CardHeader>
        <CardContent>
          {timeSeriesLoading ? (
            <div className="h-[300px] animate-pulse bg-gray-100 rounded" />
          ) : timeSeries?.series ? (
            <ScoreChart data={timeSeries.series} />
          ) : (
            <div className="h-[300px] flex items-center justify-center text-gray-500">
              No data available yet. Run an analysis to see trends.
            </div>
          )}
        </CardContent>
      </Card>

      {/* LLM Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Performance by LLM</CardTitle>
          </CardHeader>
          <CardContent>
            {llmLoading ? (
              <div className="h-[250px] animate-pulse bg-gray-100 rounded" />
            ) : llmBreakdown?.providers ? (
              <LLMBreakdownChart data={llmBreakdown.providers} />
            ) : (
              <div className="h-[250px] flex items-center justify-center text-gray-500">
                No LLM data available
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>LLM Details</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {llmBreakdown?.providers ? (
                Object.entries(llmBreakdown.providers).map(([llm, data]: [string, any]) => (
                  <div key={llm} className="flex items-center justify-between p-4 bg-gradient-to-r from-gray-50 to-white rounded-xl ring-1 ring-gray-100 hover:shadow-md transition-all">
                    <div>
                      <p className="font-semibold text-gray-900">{LLM_DISPLAY_NAMES[llm] || llm}</p>
                      <p className="text-xs text-gray-500 mt-0.5">
                        {data.run_count || 0} analysis runs
                      </p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg font-bold text-primary-600">{formatScore(data.avg_score || 0)}</p>
                      <p className="text-xs text-gray-500">
                        {formatPercent(data.mention_rate || 0)} mentions
                      </p>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-gray-500 text-center py-4">No data available</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Keyword Performance */}
      <Card>
        <CardHeader>
          <CardTitle>Top Keywords by Performance</CardTitle>
        </CardHeader>
        <CardContent>
          {keywordBreakdown?.keywords?.length > 0 ? (
            <div className="space-y-3">
              {keywordBreakdown.keywords.slice(0, 10).map((kw: any, idx: number) => (
                <div key={kw.keyword_id || idx} className="flex items-center gap-4">
                  <span className="text-sm font-medium text-gray-500 w-6">{idx + 1}</span>
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">{kw.keyword}</p>
                    <div className="flex gap-4 text-xs text-gray-500">
                      <span>Score: {formatScore(kw.avg_score || 0)}</span>
                      <span>Mentions: {formatPercent(kw.mention_rate || 0)}</span>
                    </div>
                  </div>
                  <div className="w-24">
                    <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary-500 rounded-full"
                        style={{ width: `${Math.min((kw.avg_score || 0), 100)}%` }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-center py-8">
              No keyword data available. Add keywords and run an analysis.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
