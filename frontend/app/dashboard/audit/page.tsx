"use client";

import { useQuery } from "@tanstack/react-query";
import { useProjectStore } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Activity, Filter, Download } from "lucide-react";
import Link from "next/link";

interface AuditEvent {
  id: string;
  event_type: string;
  description: string;
  created_at: string;
  metadata?: Record<string, any>;
}

export default function AuditPage() {
  const { currentProject } = useProjectStore();

  // Mock audit data - replace with actual API call when available
  const { data: auditData, isLoading } = useQuery({
    queryKey: ["audit", currentProject?.id],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      // Mock data for now
      return {
        events: [
          {
            id: "1",
            event_type: "project_created",
            description: "Project created",
            created_at: new Date().toISOString(),
            metadata: { project_name: currentProject.name },
          },
          {
            id: "2",
            event_type: "keywords_added",
            description: "Keywords added to project",
            created_at: new Date(Date.now() - 3600000).toISOString(),
            metadata: { count: 5 },
          },
          {
            id: "3",
            event_type: "analysis_run",
            description: "LLM analysis executed",
            created_at: new Date(Date.now() - 7200000).toISOString(),
            metadata: { providers: ["openai", "anthropic"] },
          },
        ] as AuditEvent[],
        total: 3,
      };
    },
    enabled: !!currentProject?.id,
  });

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case "project_created":
        return "bg-success-100 text-success-600";
      case "keywords_added":
        return "bg-primary-100 text-primary-600";
      case "analysis_run":
        return "bg-warning-100 text-warning-600";
      default:
        return "bg-gray-100 text-gray-600";
    }
  };

  const formatEventType = (eventType: string) => {
    return eventType.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
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
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit Trail</h1>
          <p className="text-sm text-gray-500">
            Activity log for {currentProject.name}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" className="shadow-sm">
            <Filter className="h-4 w-4 mr-2" />
            Filter
          </Button>
          <Button variant="secondary" size="sm" className="shadow-sm">
            <Download className="h-4 w-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Recent Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 bg-gray-100 rounded animate-pulse" />
              ))}
            </div>
          ) : auditData?.events?.length === 0 ? (
            <p className="text-gray-500 text-center py-8">
              No activity recorded yet.
            </p>
          ) : (
            <div className="space-y-4">
              {auditData?.events?.map((event: AuditEvent) => (
                <div
                  key={event.id}
                  className="flex items-start gap-4 p-4 bg-gradient-to-r from-gray-50 to-white rounded-xl ring-1 ring-gray-100 hover:shadow-md hover:ring-primary-100 transition-all"
                >
                  <div className={`p-2.5 rounded-xl ${getEventIcon(event.event_type)} shadow-sm`}>
                    <Activity className="h-4 w-4" />
                  </div>
                  <div className="flex-1">
                    <p className="font-semibold text-gray-900">
                      {formatEventType(event.event_type)}
                    </p>
                    <p className="text-sm text-gray-600 mt-0.5">{event.description}</p>
                    {event.metadata && Object.keys(event.metadata).length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {Object.entries(event.metadata).map(([key, value]) => (
                          <span
                            key={key}
                            className="text-xs bg-gray-100 text-gray-700 px-2.5 py-1 rounded-full font-medium"
                          >
                            {key}: {typeof value === "object" ? JSON.stringify(value) : String(value)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
                    {new Date(event.created_at).toLocaleString()}
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
