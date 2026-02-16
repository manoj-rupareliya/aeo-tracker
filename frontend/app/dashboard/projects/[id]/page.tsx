"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { projectsApi } from "@/lib/api";
import { useProjectStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ArrowLeft, Save, Trash2, Plus, X, Building2, Users } from "lucide-react";

export default function ProjectSettingsPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const projectId = params.id as string;
  const { setCurrentProject, projects, setProjects } = useProjectStore();

  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("");
  const [crawlFrequency, setCrawlFrequency] = useState(7);
  const [enabledLlms, setEnabledLlms] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Brand management
  const [newBrandName, setNewBrandName] = useState("");
  const [newBrandAliases, setNewBrandAliases] = useState("");
  const [showAddBrand, setShowAddBrand] = useState(false);

  // Competitor management
  const [newCompName, setNewCompName] = useState("");
  const [newCompDomain, setNewCompDomain] = useState("");
  const [showAddComp, setShowAddComp] = useState(false);

  const { data: project, isLoading } = useQuery({
    queryKey: ["project", projectId],
    queryFn: async () => {
      const response = await projectsApi.get(projectId);
      const p = response.data;
      setName(p.name);
      setIndustry(p.industry);
      setCrawlFrequency(p.crawl_frequency_days);
      setEnabledLlms(p.enabled_llms);
      return p;
    },
  });

  const updateMutation = useMutation({
    mutationFn: async (data: Record<string, unknown>) => {
      return projectsApi.update(projectId, data);
    },
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setCurrentProject(response.data);
      setSuccess("Project updated successfully");
      setTimeout(() => setSuccess(""), 3000);
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || "Failed to update project");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async () => {
      return projectsApi.delete(projectId);
    },
    onSuccess: () => {
      const updatedProjects = projects.filter((p) => p.id !== projectId);
      setProjects(updatedProjects);
      if (updatedProjects.length > 0) {
        setCurrentProject(updatedProjects[0]);
      }
      router.push("/dashboard");
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || "Failed to delete project");
    },
  });

  // Add brand mutation
  const addBrandMutation = useMutation({
    mutationFn: async (data: { name: string; is_primary?: boolean; aliases?: string[] }) => {
      return projectsApi.addBrand(projectId, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      setNewBrandName("");
      setNewBrandAliases("");
      setShowAddBrand(false);
      setSuccess("Brand added successfully");
      setTimeout(() => setSuccess(""), 3000);
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || "Failed to add brand");
    },
  });

  // Delete brand mutation
  const deleteBrandMutation = useMutation({
    mutationFn: async (brandId: string) => {
      return projectsApi.deleteBrand(projectId, brandId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });

  // Add competitor mutation
  const addCompMutation = useMutation({
    mutationFn: async (data: { name: string; domain?: string }) => {
      return projectsApi.addCompetitor(projectId, data);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
      setNewCompName("");
      setNewCompDomain("");
      setShowAddComp(false);
      setSuccess("Competitor added successfully");
      setTimeout(() => setSuccess(""), 3000);
    },
    onError: (err: unknown) => {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || "Failed to add competitor");
    },
  });

  // Delete competitor mutation
  const deleteCompMutation = useMutation({
    mutationFn: async (compId: string) => {
      return projectsApi.deleteCompetitor(projectId, compId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });

  const handleAddBrand = () => {
    if (!newBrandName.trim()) return;
    const aliases = newBrandAliases.split(",").map(a => a.trim()).filter(a => a);
    addBrandMutation.mutate({
      name: newBrandName.trim(),
      is_primary: false,
      aliases: aliases.length > 0 ? aliases : undefined,
    });
  };

  const handleAddComp = () => {
    if (!newCompName.trim()) return;
    addCompMutation.mutate({
      name: newCompName.trim(),
      domain: newCompDomain.trim() || undefined,
    });
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    updateMutation.mutate({
      name,
      industry,
      crawl_frequency_days: crawlFrequency,
      enabled_llms: enabledLlms,
    });
  };

  const handleDelete = () => {
    if (confirm("Are you sure you want to delete this project? This action cannot be undone.")) {
      deleteMutation.mutate();
    }
  };

  const toggleLlm = (llm: string) => {
    if (enabledLlms.includes(llm)) {
      setEnabledLlms(enabledLlms.filter((l) => l !== llm));
    } else {
      setEnabledLlms([...enabledLlms, llm]);
    }
  };

  if (isLoading) {
    return (
      <div className="animate-pulse space-y-6">
        <div className="h-8 bg-gray-200 rounded w-1/4" />
        <div className="h-64 bg-gray-200 rounded" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">Project not found</p>
        <Link href="/dashboard">
          <Button className="mt-4">Back to Dashboard</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div className="mb-6">
        <Link
          href="/dashboard"
          className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back to Dashboard
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Project Settings</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-danger-50 text-danger-600 px-4 py-3 rounded-md text-sm">
                {error}
              </div>
            )}
            {success && (
              <div className="bg-success-50 text-success-600 px-4 py-3 rounded-md text-sm">
                {success}
              </div>
            )}

            <div>
              <label htmlFor="name" className="label">
                Project Name
              </label>
              <input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="input mt-1"
              />
            </div>

            <div>
              <label htmlFor="domain" className="label">
                Domain
              </label>
              <input
                id="domain"
                type="text"
                value={project.domain}
                disabled
                className="input mt-1 bg-gray-100"
              />
              <p className="text-xs text-gray-500 mt-1">Domain cannot be changed</p>
            </div>

            <div>
              <label htmlFor="industry" className="label">
                Industry
              </label>
              <select
                id="industry"
                value={industry}
                onChange={(e) => setIndustry(e.target.value)}
                className="input mt-1"
              >
                <option value="technology">Technology</option>
                <option value="saas">SaaS</option>
                <option value="ecommerce">E-commerce</option>
                <option value="finance">Finance</option>
                <option value="healthcare">Healthcare</option>
                <option value="education">Education</option>
                <option value="marketing">Marketing</option>
                <option value="media">Media & Entertainment</option>
                <option value="travel">Travel & Hospitality</option>
                <option value="retail">Retail</option>
                <option value="other">Other</option>
              </select>
            </div>

            <div>
              <label htmlFor="crawl" className="label">
                Crawl Frequency (days)
              </label>
              <select
                id="crawl"
                value={crawlFrequency}
                onChange={(e) => setCrawlFrequency(Number(e.target.value))}
                className="input mt-1"
              >
                <option value={1}>Daily</option>
                <option value={3}>Every 3 days</option>
                <option value={7}>Weekly</option>
                <option value={14}>Every 2 weeks</option>
                <option value={30}>Monthly</option>
              </select>
            </div>

            <div>
              <label className="label">Enabled LLMs</label>
              <div className="flex flex-wrap gap-2 mt-2">
                {["openai", "anthropic", "google", "perplexity"].map((llm) => (
                  <button
                    key={llm}
                    type="button"
                    onClick={() => toggleLlm(llm)}
                    className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                      enabledLlms.includes(llm)
                        ? "bg-primary-100 text-primary-700 border-2 border-primary-500"
                        : "bg-gray-100 text-gray-600 border-2 border-transparent"
                    }`}
                  >
                    {llm === "openai" ? "ChatGPT" :
                     llm === "anthropic" ? "Claude" :
                     llm === "google" ? "Gemini" : "Perplexity"}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-3 pt-4">
              <Button type="submit" loading={updateMutation.isPending}>
                <Save className="h-4 w-4 mr-2" />
                Save Changes
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {/* Brands */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <Building2 className="h-5 w-5 text-violet-500" />
            <CardTitle>Your Brands</CardTitle>
          </div>
          <button
            onClick={() => setShowAddBrand(!showAddBrand)}
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-violet-600"
          >
            <Plus className="h-5 w-5" />
          </button>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500 mb-4">
            Add your brand names and aliases so we can track when AI mentions your company.
          </p>

          {showAddBrand && (
            <div className="p-4 bg-violet-50 rounded-lg mb-4 space-y-3">
              <div>
                <label className="text-sm font-medium text-gray-700">Brand Name *</label>
                <input
                  type="text"
                  value={newBrandName}
                  onChange={(e) => setNewBrandName(e.target.value)}
                  placeholder="e.g., Your Company Name"
                  className="input mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Aliases (comma separated)</label>
                <input
                  type="text"
                  value={newBrandAliases}
                  onChange={(e) => setNewBrandAliases(e.target.value)}
                  placeholder="e.g., YCN, Your Co, YourCompany"
                  className="input mt-1"
                />
                <p className="text-xs text-gray-400 mt-1">Alternative names, abbreviations, or common misspellings</p>
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleAddBrand}
                  loading={addBrandMutation.isPending}
                  size="sm"
                >
                  Add Brand
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAddBrand(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}

          <div className="space-y-2">
            {project.brands?.length === 0 ? (
              <p className="text-amber-600 text-sm bg-amber-50 p-3 rounded-lg">
                No brands defined. Add your brand name to track mentions in AI responses.
              </p>
            ) : (
              project.brands?.map((brand: { id: string; name: string; is_primary: boolean; aliases?: string[] }) => (
                <div
                  key={brand.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg group"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{brand.name}</span>
                    {brand.is_primary && (
                      <span className="text-xs bg-violet-100 text-violet-700 px-2 py-0.5 rounded-full">
                        Primary
                      </span>
                    )}
                    {brand.aliases && brand.aliases.length > 0 && (
                      <span className="text-xs text-gray-400">
                        ({brand.aliases.join(", ")})
                      </span>
                    )}
                  </div>
                  {!brand.is_primary && (
                    <button
                      onClick={() => deleteBrandMutation.mutate(brand.id)}
                      className="p-1 rounded text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  )}
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      {/* Competitors */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="h-5 w-5 text-orange-500" />
            <CardTitle>Competitors</CardTitle>
          </div>
          <button
            onClick={() => setShowAddComp(!showAddComp)}
            className="p-2 rounded-lg hover:bg-gray-100 text-gray-500 hover:text-orange-600"
          >
            <Plus className="h-5 w-5" />
          </button>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500 mb-4">
            Add competitor names to track how often they appear vs your brand.
          </p>

          {showAddComp && (
            <div className="p-4 bg-orange-50 rounded-lg mb-4 space-y-3">
              <div>
                <label className="text-sm font-medium text-gray-700">Competitor Name *</label>
                <input
                  type="text"
                  value={newCompName}
                  onChange={(e) => setNewCompName(e.target.value)}
                  placeholder="e.g., Competitor Inc"
                  className="input mt-1"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-gray-700">Domain (optional)</label>
                <input
                  type="text"
                  value={newCompDomain}
                  onChange={(e) => setNewCompDomain(e.target.value)}
                  placeholder="e.g., competitor.com"
                  className="input mt-1"
                />
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleAddComp}
                  loading={addCompMutation.isPending}
                  size="sm"
                  className="bg-orange-500 hover:bg-orange-600"
                >
                  Add Competitor
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAddComp(false)}
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}

          {project.competitors?.length === 0 ? (
            <p className="text-gray-500 text-sm">No competitors added yet</p>
          ) : (
            <div className="space-y-2">
              {project.competitors?.map((comp: { id: string; name: string; domain?: string }) => (
                <div
                  key={comp.id}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg group"
                >
                  <div>
                    <span className="font-medium">{comp.name}</span>
                    {comp.domain && (
                      <span className="text-sm text-gray-500 ml-2">({comp.domain})</span>
                    )}
                  </div>
                  <button
                    onClick={() => deleteCompMutation.mutate(comp.id)}
                    className="p-1 rounded text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Danger Zone */}
      <Card className="border-danger-200">
        <CardHeader>
          <CardTitle className="text-danger-600">Danger Zone</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600 mb-4">
            Once you delete a project, there is no going back. Please be certain.
          </p>
          <Button
            variant="outline"
            onClick={handleDelete}
            loading={deleteMutation.isPending}
            className="border-danger-300 text-danger-600 hover:bg-danger-50"
          >
            <Trash2 className="h-4 w-4 mr-2" />
            Delete Project
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
