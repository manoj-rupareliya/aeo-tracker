"use client";

import { useQuery } from "@tanstack/react-query";
import { useProjectStore } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Lightbulb, ExternalLink, Check, ArrowLeft } from "lucide-react";
import Link from "next/link";

interface Recommendation {
  id: string;
  title: string;
  description: string;
  type: string;
  priority: number;
  effort: string;
  impact: string;
  action_url?: string;
  completed: boolean;
}

export default function RecommendationsPage() {
  const { currentProject } = useProjectStore();

  const { data: recommendations, isLoading } = useQuery({
    queryKey: ["recommendations", currentProject?.id],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      // Mock data - replace with actual API
      return {
        items: [
          {
            id: "1",
            title: "Get listed on G2",
            description: "G2 is frequently cited by LLMs as a trusted source for software reviews. Getting listed and gathering reviews can significantly improve your visibility.",
            type: "get_listed",
            priority: 85,
            effort: "medium",
            impact: "high",
            action_url: "https://www.g2.com",
            completed: false,
          },
          {
            id: "2",
            title: "Improve visibility for 'data analytics'",
            description: "Your brand is mentioned in only 12% of responses for this high-value keyword. Consider creating more targeted content.",
            type: "target_keyword",
            priority: 72,
            effort: "low",
            impact: "high",
            completed: false,
          },
          {
            id: "3",
            title: "Address competitor advantage: Competitor A",
            description: "Competitor A is mentioned 2.5x more frequently than your brand. Analyze their content strategy and cited sources.",
            type: "competitor_gap",
            priority: 68,
            effort: "high",
            impact: "high",
            completed: false,
          },
          {
            id: "4",
            title: "Create Wikipedia presence",
            description: "LLMs heavily rely on Wikipedia for factual information. Consider creating or improving your Wikipedia page.",
            type: "get_listed",
            priority: 65,
            effort: "high",
            impact: "high",
            completed: false,
          },
          {
            id: "5",
            title: "Publish on industry blogs",
            description: "Guest posts on high-authority sites like TechCrunch, Forbes, or industry-specific publications improve citation likelihood.",
            type: "content",
            priority: 60,
            effort: "medium",
            impact: "medium",
            completed: true,
          },
        ] as Recommendation[],
        stats: {
          total: 5,
          completed: 1,
          high_priority: 3,
        },
      };
    },
    enabled: !!currentProject?.id,
  });

  const getPriorityColor = (priority: number) => {
    if (priority >= 80) return "bg-danger-500";
    if (priority >= 60) return "bg-warning-500";
    return "bg-success-500";
  };

  const getEffortBadge = (effort: string) => {
    switch (effort) {
      case "low":
        return "bg-success-100 text-success-700";
      case "medium":
        return "bg-warning-100 text-warning-700";
      case "high":
        return "bg-danger-100 text-danger-700";
      default:
        return "bg-gray-100 text-gray-700";
    }
  };

  const getTypeBadge = (type: string) => {
    switch (type) {
      case "get_listed":
        return "bg-purple-100 text-purple-700";
      case "target_keyword":
        return "bg-blue-100 text-blue-700";
      case "competitor_gap":
        return "bg-orange-100 text-orange-700";
      case "content":
        return "bg-green-100 text-green-700";
      default:
        return "bg-gray-100 text-gray-700";
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
            <h1 className="text-2xl font-bold text-gray-900">GEO Recommendations</h1>
            <p className="text-sm text-gray-500">
              Actionable steps to improve your LLM visibility for {currentProject.name}
            </p>
          </div>
        </div>
        <Button variant="secondary" size="sm" className="shadow-sm">
          <Lightbulb className="h-4 w-4 mr-2" />
          Generate New
        </Button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="bg-gradient-to-br from-gray-50 to-white overflow-hidden relative">
          <div className="absolute top-0 right-0 w-16 h-16 bg-gray-200/50 rounded-full blur-2xl" />
          <CardContent className="pt-6 text-center relative">
            <p className="text-4xl font-bold text-gray-900">{recommendations?.stats?.total || 0}</p>
            <p className="text-sm font-medium text-gray-500 mt-1">Total Recommendations</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-danger-50 to-white overflow-hidden relative border-danger-100">
          <div className="absolute top-0 right-0 w-16 h-16 bg-danger-200/50 rounded-full blur-2xl" />
          <CardContent className="pt-6 text-center relative">
            <p className="text-4xl font-bold text-danger-600">{recommendations?.stats?.high_priority || 0}</p>
            <p className="text-sm font-medium text-danger-500 mt-1">High Priority</p>
          </CardContent>
        </Card>
        <Card className="bg-gradient-to-br from-success-50 to-white overflow-hidden relative border-success-100">
          <div className="absolute top-0 right-0 w-16 h-16 bg-success-200/50 rounded-full blur-2xl" />
          <CardContent className="pt-6 text-center relative">
            <p className="text-4xl font-bold text-success-600">{recommendations?.stats?.completed || 0}</p>
            <p className="text-sm font-medium text-success-500 mt-1">Completed</p>
          </CardContent>
        </Card>
      </div>

      {/* Recommendations List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-warning-500" />
            All Recommendations
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-24 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : recommendations?.items?.length === 0 ? (
            <p className="text-gray-500 text-center py-8">
              No recommendations yet. Run an analysis to get personalized suggestions.
            </p>
          ) : (
            <div className="space-y-4">
              {recommendations?.items?.map((rec: Recommendation) => (
                <div
                  key={rec.id}
                  className={`p-5 rounded-xl ring-1 transition-all ${rec.completed ? "bg-gray-50 opacity-60 ring-gray-100" : "bg-gradient-to-r from-gray-50 to-white ring-gray-100 hover:ring-primary-200 hover:shadow-lg"}`}
                >
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 mt-1">
                      <div
                        className={`w-4 h-4 rounded-full ${getPriorityColor(rec.priority)} shadow-sm`}
                        title={`Priority: ${rec.priority}`}
                      />
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <h3 className={`font-semibold text-lg ${rec.completed ? "line-through text-gray-500" : "text-gray-900"}`}>
                          {rec.title}
                        </h3>
                        {rec.completed && <Check className="h-5 w-5 text-success-500" />}
                      </div>
                      <p className="text-sm text-gray-600 mb-4">{rec.description}</p>
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${getTypeBadge(rec.type)}`}>
                          {rec.type.replace("_", " ")}
                        </span>
                        <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${getEffortBadge(rec.effort)}`}>
                          {rec.effort} effort
                        </span>
                        <span className="text-xs text-gray-500 font-medium bg-gray-100 px-2.5 py-1 rounded-full">
                          Score: {rec.priority}
                        </span>
                      </div>
                    </div>
                    <div className="flex-shrink-0">
                      {rec.action_url && !rec.completed && (
                        <a href={rec.action_url} target="_blank" rel="noopener noreferrer">
                          <Button size="sm">
                            <ExternalLink className="h-4 w-4 mr-1" />
                            Take Action
                          </Button>
                        </a>
                      )}
                      {!rec.completed && !rec.action_url && (
                        <Button variant="secondary" size="sm">
                          <Check className="h-4 w-4 mr-1" />
                          Mark Done
                        </Button>
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
