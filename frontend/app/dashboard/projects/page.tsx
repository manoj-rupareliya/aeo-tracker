"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { projectsApi } from "@/lib/api";
import { useProjectStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Plus, Settings, Globe, Calendar } from "lucide-react";

interface Project {
  id: string;
  name: string;
  domain: string;
  industry: string;
  country?: string;
  is_active: boolean;
  created_at: string;
  brands: { id: string; name: string; is_primary: boolean }[];
  enabled_llms?: string[];
  competitors?: { id: string; name: string }[];
  keyword_count?: number;
  total_runs?: number;
  last_crawl_at?: string | null;
}

export default function ProjectsPage() {
  const { setCurrentProject } = useProjectStore();

  const { data: projectsData, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const response = await projectsApi.list();
      return response.data;
    },
  });

  const handleSelectProject = (project: Project) => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    setCurrentProject(project as any);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Projects</h1>
          <p className="text-sm text-gray-500">Manage your tracking projects</p>
        </div>
        <Link href="/dashboard/projects/new">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            New Project
          </Button>
        </Link>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-48 bg-gray-100 rounded-lg animate-pulse" />
          ))}
        </div>
      ) : projectsData?.items?.length === 0 ? (
        <Card className="text-center py-16 bg-gradient-to-br from-gray-50 to-white">
          <div className="max-w-sm mx-auto">
            <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-violet-500/30">
              <Plus className="h-8 w-8 text-white" />
            </div>
            <h3 className="text-xl font-bold text-gray-900 mb-2">Create your first project</h3>
            <p className="text-gray-500 mb-6">Start tracking your brand's visibility across AI platforms</p>
            <Link href="/dashboard/projects/new">
              <Button size="lg">Create Project</Button>
            </Link>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {projectsData?.items?.map((project: Project) => (
            <div
              key={project.id}
              onClick={() => handleSelectProject(project)}
              className="cursor-pointer"
            >
              <Card className="hover:shadow-xl hover:ring-primary-200 transition-all group overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-br from-violet-500/10 to-transparent rounded-full blur-2xl -translate-y-1/2 translate-x-1/2 group-hover:scale-150 transition-transform" />
              <CardContent className="pt-6 relative">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-lg text-gray-900 group-hover:text-primary-600 transition-colors">
                      {project.name}
                    </h3>
                    <div className="flex items-center gap-1.5 text-sm text-gray-500 mt-1">
                      <Globe className="h-3.5 w-3.5" />
                      {project.domain}
                    </div>
                  </div>
                  <Link
                    href={`/dashboard/projects/${project.id}`}
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button variant="ghost" size="sm" className="opacity-0 group-hover:opacity-100 transition-opacity">
                      <Settings className="h-4 w-4" />
                    </Button>
                  </Link>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs bg-gray-100 text-gray-700 px-2.5 py-1 rounded-full font-medium">
                      {project.industry}
                    </span>
                    <span
                      className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                        project.is_active
                          ? "bg-success-100 text-success-700"
                          : "bg-gray-100 text-gray-500"
                      }`}
                    >
                      {project.is_active ? "Active" : "Paused"}
                    </span>
                  </div>

                  <div className="flex items-center gap-1.5 text-xs text-gray-400">
                    <Calendar className="h-3.5 w-3.5" />
                    Created {new Date(project.created_at).toLocaleDateString()}
                  </div>

                  {project.brands?.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {project.brands.slice(0, 3).map((brand) => (
                        <span
                          key={brand.id}
                          className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                            brand.is_primary
                              ? "bg-gradient-to-r from-violet-100 to-indigo-100 text-primary-700"
                              : "bg-gray-100 text-gray-600"
                          }`}
                        >
                          {brand.name}
                        </span>
                      ))}
                      {project.brands.length > 3 && (
                        <span className="text-xs text-gray-400 font-medium">
                          +{project.brands.length - 3} more
                        </span>
                      )}
                    </div>
                  )}
                </div>

                <div className="mt-5 pt-4 border-t border-gray-100">
                  <Link
                    href="/dashboard"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleSelectProject(project);
                    }}
                  >
                    <Button variant="secondary" size="sm" className="w-full group-hover:bg-gradient-to-r group-hover:from-violet-500 group-hover:to-indigo-600 group-hover:text-white transition-all">
                      View Dashboard
                    </Button>
                  </Link>
                </div>
              </CardContent>
              </Card>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
