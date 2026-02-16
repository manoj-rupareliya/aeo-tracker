"use client";

import { useQuery } from "@tanstack/react-query";
import { useProjectStore } from "@/lib/store";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Network, ArrowLeft, ExternalLink } from "lucide-react";
import Link from "next/link";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  weight: number;
}

interface GraphEdge {
  source: string;
  target: string;
  weight: number;
}

export default function GraphPage() {
  const { currentProject } = useProjectStore();

  const { data: graphData, isLoading } = useQuery({
    queryKey: ["graph", currentProject?.id],
    queryFn: async () => {
      if (!currentProject?.id) return null;
      // Mock data - replace with actual API
      return {
        nodes: [
          { id: "brand", name: "Your Brand", type: "brand", weight: 100 },
          { id: "wiki", name: "Wikipedia", type: "source", weight: 85 },
          { id: "g2", name: "G2", type: "source", weight: 72 },
          { id: "capterra", name: "Capterra", type: "source", weight: 68 },
          { id: "comp1", name: "Competitor A", type: "competitor", weight: 90 },
          { id: "comp2", name: "Competitor B", type: "competitor", weight: 65 },
          { id: "techcrunch", name: "TechCrunch", type: "source", weight: 60 },
          { id: "forbes", name: "Forbes", type: "source", weight: 55 },
        ] as GraphNode[],
        edges: [
          { source: "brand", target: "wiki", weight: 0.8 },
          { source: "brand", target: "g2", weight: 0.6 },
          { source: "comp1", target: "wiki", weight: 0.9 },
          { source: "comp1", target: "capterra", weight: 0.7 },
          { source: "comp2", target: "g2", weight: 0.5 },
          { source: "wiki", target: "techcrunch", weight: 0.4 },
        ] as GraphEdge[],
        summary: {
          total_nodes: 8,
          total_edges: 6,
          most_cited_source: "Wikipedia",
          brand_connections: 2,
        },
      };
    },
    enabled: !!currentProject?.id,
  });

  const getNodeColor = (type: string) => {
    switch (type) {
      case "brand":
        return "bg-primary-500 text-white";
      case "competitor":
        return "bg-danger-500 text-white";
      case "source":
        return "bg-success-500 text-white";
      default:
        return "bg-gray-500 text-white";
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
            <h1 className="text-2xl font-bold text-gray-900">Preference Graph</h1>
            <p className="text-sm text-gray-500">
              Visualize citation relationships for {currentProject.name}
            </p>
          </div>
        </div>
        <Button variant="secondary" size="sm" className="shadow-sm">
          <ExternalLink className="h-4 w-4 mr-2" />
          Export Graph
        </Button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-3xl font-bold text-gray-900">{graphData?.summary?.total_nodes || 0}</p>
            <p className="text-sm text-gray-500">Entities</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-3xl font-bold text-gray-900">{graphData?.summary?.total_edges || 0}</p>
            <p className="text-sm text-gray-500">Connections</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-3xl font-bold text-success-600">{graphData?.summary?.brand_connections || 0}</p>
            <p className="text-sm text-gray-500">Brand Citations</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-xl font-bold text-primary-600">{graphData?.summary?.most_cited_source || "N/A"}</p>
            <p className="text-sm text-gray-500">Top Source</p>
          </CardContent>
        </Card>
      </div>

      {/* Graph Visualization Placeholder */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Network className="h-5 w-5" />
            Citation Network
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-[400px] bg-gradient-to-br from-gray-50 to-white rounded-xl flex items-center justify-center border-2 border-dashed border-gray-200 relative overflow-hidden">
            <div className="absolute inset-0 bg-mesh opacity-50" />
            {/* Simulated nodes */}
            <div className="absolute w-20 h-20 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 flex items-center justify-center text-white font-bold text-xs shadow-lg shadow-violet-500/30">
              Brand
            </div>
            <div className="absolute w-14 h-14 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 top-1/4 left-1/4 flex items-center justify-center text-white font-medium text-xs shadow-lg">
              Wiki
            </div>
            <div className="absolute w-14 h-14 rounded-full bg-gradient-to-br from-emerald-400 to-teal-500 top-1/3 right-1/4 flex items-center justify-center text-white font-medium text-xs shadow-lg">
              G2
            </div>
            <div className="absolute w-16 h-16 rounded-full bg-gradient-to-br from-rose-400 to-red-500 bottom-1/4 right-1/3 flex items-center justify-center text-white font-medium text-xs shadow-lg">
              Comp A
            </div>
            <div className="absolute bottom-4 right-4 z-10">
              <p className="text-xs text-gray-400 bg-white/80 backdrop-blur-sm px-3 py-1.5 rounded-full">
                Interactive graph coming soon
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Nodes List */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Entities in Graph</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 bg-gray-100 rounded animate-pulse" />
                ))}
              </div>
            ) : (
              <div className="space-y-2">
                {graphData?.nodes?.map((node: GraphNode) => (
                  <div
                    key={node.id}
                    className="flex items-center justify-between p-4 bg-gradient-to-r from-gray-50 to-white rounded-xl ring-1 ring-gray-100 hover:shadow-md transition-all"
                  >
                    <div className="flex items-center gap-3">
                      <div className={`w-4 h-4 rounded-full ${getNodeColor(node.type).replace("text-white", "")} shadow-sm`} />
                      <div>
                        <p className="font-semibold text-gray-900">{node.name}</p>
                        <p className="text-xs text-gray-500 capitalize">{node.type}</p>
                      </div>
                    </div>
                    <span className="text-sm font-bold text-primary-600 bg-primary-50 px-2 py-1 rounded-full">
                      {node.weight}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top Sources Cited</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {graphData?.nodes
                ?.filter((n: GraphNode) => n.type === "source")
                .sort((a: GraphNode, b: GraphNode) => b.weight - a.weight)
                .map((source: GraphNode, idx: number) => (
                  <div key={source.id} className="flex items-center gap-4">
                    <span className="text-lg font-bold text-gray-400 w-6">{idx + 1}</span>
                    <div className="flex-1">
                      <p className="font-medium">{source.name}</p>
                      <div className="h-2 bg-gray-100 rounded-full mt-1 overflow-hidden">
                        <div
                          className="h-full bg-success-500 rounded-full"
                          style={{ width: `${source.weight}%` }}
                        />
                      </div>
                    </div>
                    <span className="text-sm text-gray-500">{source.weight}%</span>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
