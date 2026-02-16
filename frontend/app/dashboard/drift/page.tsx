"use client";

import { useQuery } from "@tanstack/react-query";
import { useProjectStore } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Activity, AlertCircle, TrendingDown, TrendingUp, ArrowLeft } from "lucide-react";
import Link from "next/link";

interface DriftEvent {
  id: string;
  type: string;
  severity: string;
  provider: string;
  description: string;
  created_at: string;
  keyword?: string;
  old_value?: number;
  new_value?: number;
}

export default function DriftPage() {
  const { currentProject } = useProjectStore();

  const { data: driftData, isLoading } = useQuery({
    queryKey: ["drift", currentProject?.id],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      // Mock data - replace with actual API
      return {
        events: [
          {
            id: "1",
            type: "brand_disappeared",
            severity: "critical",
            provider: "openai",
            description: "Brand disappeared from 'best analytics tools' query",
            created_at: new Date().toISOString(),
            keyword: "best analytics tools",
          },
          {
            id: "2",
            type: "position_declined",
            severity: "major",
            provider: "anthropic",
            description: "Position dropped from #2 to #5 for 'data visualization software'",
            created_at: new Date(Date.now() - 3600000).toISOString(),
            keyword: "data visualization software",
            old_value: 2,
            new_value: 5,
          },
          {
            id: "3",
            type: "mention_rate_change",
            severity: "moderate",
            provider: "google",
            description: "Mention rate decreased by 15% for 'business intelligence'",
            created_at: new Date(Date.now() - 7200000).toISOString(),
            keyword: "business intelligence",
            old_value: 45,
            new_value: 30,
          },
          {
            id: "4",
            type: "competitor_surge",
            severity: "major",
            provider: "perplexity",
            description: "Competitor 'CompetitorX' now mentioned 3x more frequently",
            created_at: new Date(Date.now() - 10800000).toISOString(),
          },
        ] as DriftEvent[],
        summary: {
          critical: 1,
          major: 2,
          moderate: 1,
          minor: 0,
        },
      };
    },
    enabled: !!currentProject?.id,
  });

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical":
        return "bg-danger-100 text-danger-700 border-danger-200";
      case "major":
        return "bg-warning-100 text-warning-700 border-warning-200";
      case "moderate":
        return "bg-blue-100 text-blue-700 border-blue-200";
      default:
        return "bg-gray-100 text-gray-700 border-gray-200";
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case "brand_disappeared":
        return <AlertCircle className="h-5 w-5 text-danger-500" />;
      case "position_declined":
        return <TrendingDown className="h-5 w-5 text-warning-500" />;
      case "competitor_surge":
        return <TrendingUp className="h-5 w-5 text-warning-500" />;
      default:
        return <Activity className="h-5 w-5 text-blue-500" />;
    }
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
            <h1 className="text-2xl font-bold text-gray-900">Drift Detection</h1>
            <p className="text-sm text-gray-500">
              Track visibility changes over time for {currentProject.name}
            </p>
          </div>
        </div>
        <select className="input py-2 px-3 text-sm">
          <option>Last 7 days</option>
          <option>Last 30 days</option>
          <option>All time</option>
        </select>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="border-danger-200 bg-gradient-to-br from-danger-50 to-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-16 h-16 bg-danger-200/50 rounded-full blur-2xl" />
          <CardContent className="pt-6 text-center relative">
            <p className="text-4xl font-bold text-danger-600">{driftData?.summary?.critical || 0}</p>
            <p className="text-sm font-medium text-danger-500 mt-1">Critical</p>
          </CardContent>
        </Card>
        <Card className="border-warning-200 bg-gradient-to-br from-warning-50 to-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-16 h-16 bg-warning-200/50 rounded-full blur-2xl" />
          <CardContent className="pt-6 text-center relative">
            <p className="text-4xl font-bold text-warning-600">{driftData?.summary?.major || 0}</p>
            <p className="text-sm font-medium text-warning-500 mt-1">Major</p>
          </CardContent>
        </Card>
        <Card className="border-blue-200 bg-gradient-to-br from-blue-50 to-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-16 h-16 bg-blue-200/50 rounded-full blur-2xl" />
          <CardContent className="pt-6 text-center relative">
            <p className="text-4xl font-bold text-blue-600">{driftData?.summary?.moderate || 0}</p>
            <p className="text-sm font-medium text-blue-500 mt-1">Moderate</p>
          </CardContent>
        </Card>
        <Card className="border-gray-200 bg-gradient-to-br from-gray-50 to-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-16 h-16 bg-gray-200/50 rounded-full blur-2xl" />
          <CardContent className="pt-6 text-center relative">
            <p className="text-4xl font-bold text-gray-600">{driftData?.summary?.minor || 0}</p>
            <p className="text-sm font-medium text-gray-500 mt-1">Minor</p>
          </CardContent>
        </Card>
      </div>

      {/* Drift Timeline */}
      <Card>
        <CardHeader>
          <CardTitle>Drift Timeline</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-20 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : driftData?.events?.length === 0 ? (
            <p className="text-gray-500 text-center py-8">
              No drift events detected. Your visibility is stable.
            </p>
          ) : (
            <div className="space-y-4">
              {driftData?.events?.map((event: DriftEvent) => (
                <div
                  key={event.id}
                  className={`p-4 rounded-lg border ${getSeverityColor(event.severity)}`}
                >
                  <div className="flex items-start gap-4">
                    <div className="mt-1">{getTypeIcon(event.type)}</div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded ${getSeverityColor(event.severity)}`}>
                          {event.severity}
                        </span>
                        <span className="text-xs text-gray-500">{event.provider}</span>
                        <span className="text-xs text-gray-400">
                          {new Date(event.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="font-medium text-gray-900">{event.description}</p>
                      {event.keyword && (
                        <p className="text-sm text-gray-600 mt-1">
                          Keyword: <span className="font-medium">{event.keyword}</span>
                        </p>
                      )}
                      {event.old_value !== undefined && event.new_value !== undefined && (
                        <p className="text-sm text-gray-600 mt-1">
                          Change: {event.old_value} → {event.new_value}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
