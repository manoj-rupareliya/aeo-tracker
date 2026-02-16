"use client";

import { useQuery } from "@tanstack/react-query";
import { useProjectStore } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TrendingUp, TrendingDown, Minus, ArrowLeft } from "lucide-react";
import { LLM_DISPLAY_NAMES } from "@/lib/utils";
import Link from "next/link";

export default function SAIVPage() {
  const { currentProject } = useProjectStore();

  const { data: saivData, isLoading } = useQuery({
    queryKey: ["saiv-detail", currentProject?.id],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      // Mock data - replace with actual API
      return {
        overall_saiv: 23.5,
        trend_direction: "up",
        saiv_delta: 2.3,
        by_llm: {
          openai: { saiv: 28.4, trend: "up", delta: 3.1 },
          anthropic: { saiv: 22.1, trend: "stable", delta: 0.2 },
          google: { saiv: 18.9, trend: "down", delta: -1.5 },
          perplexity: { saiv: 24.6, trend: "up", delta: 2.8 },
        },
        competitors: [
          { name: "Competitor A", saiv: 31.2, trend: "up" },
          { name: "Competitor B", saiv: 19.8, trend: "down" },
          { name: "Competitor C", saiv: 15.4, trend: "stable" },
        ],
        history: [
          { date: "2026-02-04", saiv: 21.2 },
          { date: "2026-02-05", saiv: 21.8 },
          { date: "2026-02-06", saiv: 22.1 },
          { date: "2026-02-07", saiv: 22.5 },
          { date: "2026-02-08", saiv: 23.0 },
          { date: "2026-02-09", saiv: 23.2 },
          { date: "2026-02-10", saiv: 23.5 },
        ],
      };
    },
    enabled: !!currentProject?.id,
  });

  const TrendIcon = ({ trend }: { trend: string }) => {
    if (trend === "up") return <TrendingUp className="h-4 w-4 text-success-500" />;
    if (trend === "down") return <TrendingDown className="h-4 w-4 text-danger-500" />;
    return <Minus className="h-4 w-4 text-gray-400" />;
  };

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
        <div className="flex items-center gap-4">
          <Link href="/dashboard" className="p-2 rounded-lg bg-white/80 backdrop-blur-sm ring-1 ring-gray-200 text-gray-500 hover:text-gray-700 hover:shadow-md transition-all">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Share of AI Voice (SAIV)</h1>
            <p className="text-sm text-gray-500">
              Your brand's share of mentions across AI responses for {currentProject.name}
            </p>
          </div>
        </div>
        <select className="input py-2 px-3 text-sm">
          <option>Last 7 days</option>
          <option>Last 30 days</option>
          <option>Last 90 days</option>
        </select>
      </div>

      {/* Overall SAIV */}
      <Card className="bg-gradient-to-br from-violet-600 via-indigo-600 to-purple-700 border-0 overflow-hidden relative">
        <div className="absolute top-0 right-0 w-64 h-64 bg-white/10 rounded-full blur-3xl translate-x-1/3 -translate-y-1/3" />
        <div className="absolute bottom-0 left-0 w-48 h-48 bg-pink-500/20 rounded-full blur-3xl -translate-x-1/3 translate-y-1/3" />
        <CardContent className="pt-8 pb-8 relative z-10">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-violet-200">Overall SAIV</p>
              <p className="text-6xl font-bold text-white mt-2">
                {saivData?.overall_saiv?.toFixed(1)}%
              </p>
              <p className={`text-sm mt-3 flex items-center gap-1 ${
                saivData?.trend_direction === "up" ? "text-emerald-300" :
                saivData?.trend_direction === "down" ? "text-rose-300" : "text-violet-200"
              }`}>
                <TrendIcon trend={saivData?.trend_direction || "stable"} />
                {(saivData?.saiv_delta ?? 0) > 0 ? "+" : ""}{saivData?.saiv_delta?.toFixed(1)}% vs last week
              </p>
            </div>
            <div className="text-right max-w-xs">
              <p className="text-sm text-violet-100/80">
                Your brand is mentioned in approximately <span className="font-bold text-white">{saivData?.overall_saiv?.toFixed(0)}%</span> of relevant AI responses.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* SAIV by LLM */}
        <Card>
          <CardHeader>
            <CardTitle>SAIV by LLM Provider</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-4">
                {[1, 2, 3, 4].map((i) => (
                  <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="space-y-4">
                {saivData?.by_llm && Object.entries(saivData.by_llm).map(([llm, data]: [string, any]) => (
                  <div key={llm} className="p-4 bg-gradient-to-r from-gray-50 to-white rounded-xl ring-1 ring-gray-100 hover:shadow-lg hover:ring-primary-200 transition-all">
                    <div className="flex items-center justify-between mb-3">
                      <span className="font-semibold text-gray-900">{LLM_DISPLAY_NAMES[llm] || llm}</span>
                      <div className="flex items-center gap-2">
                        <TrendIcon trend={data.trend} />
                        <span className="text-lg font-bold text-primary-600">{data.saiv?.toFixed(1)}%</span>
                      </div>
                    </div>
                    <div className="h-2.5 bg-gray-200 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-all"
                        style={{ width: `${Math.min(data.saiv, 100)}%` }}
                      />
                    </div>
                    <p className={`text-xs mt-2 font-medium ${
                      data.delta > 0 ? "text-success-600" :
                      data.delta < 0 ? "text-danger-600" : "text-gray-500"
                    }`}>
                      {data.delta > 0 ? "+" : ""}{data.delta?.toFixed(1)}% change
                    </p>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Competitor Comparison */}
        <Card>
          <CardHeader>
            <CardTitle>Competitor SAIV Comparison</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Your brand */}
              <div className="p-4 bg-primary-50 rounded-lg border-2 border-primary-200">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-primary-700">Your Brand</span>
                  <span className="font-bold text-primary-700">{saivData?.overall_saiv?.toFixed(1)}%</span>
                </div>
                <div className="h-2 bg-primary-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary-500 rounded-full"
                    style={{ width: `${Math.min((saivData?.overall_saiv || 0) * 2, 100)}%` }}
                  />
                </div>
              </div>

              {/* Competitors */}
              {saivData?.competitors?.map((comp: any, idx: number) => (
                <div key={idx} className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-700">{comp.name}</span>
                    <div className="flex items-center gap-2">
                      <TrendIcon trend={comp.trend} />
                      <span className="font-bold">{comp.saiv?.toFixed(1)}%</span>
                    </div>
                  </div>
                  <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gray-400 rounded-full"
                      style={{ width: `${Math.min(comp.saiv * 2, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* SAIV History */}
      <Card>
        <CardHeader>
          <CardTitle>SAIV Trend (Last 7 Days)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[200px] flex items-end gap-2">
            {saivData?.history?.map((point: any, idx: number) => (
              <div key={idx} className="flex-1 flex flex-col items-center">
                <div
                  className="w-full bg-primary-500 rounded-t"
                  style={{ height: `${(point.saiv / 50) * 100}%` }}
                />
                <p className="text-xs text-gray-500 mt-2">
                  {new Date(point.date).toLocaleDateString("en-US", { weekday: "short" })}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
