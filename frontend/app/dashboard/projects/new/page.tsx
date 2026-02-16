"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { projectsApi } from "@/lib/api";
import { useProjectStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { ArrowLeft, Plus, X, Globe } from "lucide-react";

const availableCountries = [
  { code: "in", name: "India", flag: "🇮🇳" },
  { code: "us", name: "United States", flag: "🇺🇸" },
  { code: "uk", name: "United Kingdom", flag: "🇬🇧" },
  { code: "au", name: "Australia", flag: "🇦🇺" },
  { code: "ca", name: "Canada", flag: "🇨🇦" },
  { code: "de", name: "Germany", flag: "🇩🇪" },
  { code: "fr", name: "France", flag: "🇫🇷" },
  { code: "jp", name: "Japan", flag: "🇯🇵" },
  { code: "sg", name: "Singapore", flag: "🇸🇬" },
  { code: "ae", name: "UAE", flag: "🇦🇪" },
  { code: "br", name: "Brazil", flag: "🇧🇷" },
  { code: "mx", name: "Mexico", flag: "🇲🇽" },
  { code: "nl", name: "Netherlands", flag: "🇳🇱" },
  { code: "es", name: "Spain", flag: "🇪🇸" },
  { code: "it", name: "Italy", flag: "🇮🇹" },
];

export default function NewProjectPage() {
  const router = useRouter();
  const { setCurrentProject, setProjects, projects } = useProjectStore();

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [industry, setIndustry] = useState("");
  const [country, setCountry] = useState("in");
  const [brands, setBrands] = useState<{ name: string; is_primary: boolean; aliases: string[] }[]>([
    { name: "", is_primary: true, aliases: [] },
  ]);
  const [competitors, setCompetitors] = useState<{ name: string; domain: string }[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const addBrand = () => {
    setBrands([...brands, { name: "", is_primary: false, aliases: [] }]);
  };

  const removeBrand = (index: number) => {
    if (brands.length > 1) {
      setBrands(brands.filter((_, i) => i !== index));
    }
  };

  const updateBrand = (index: number, field: string, value: string | boolean) => {
    const updated = [...brands];
    if (field === "is_primary" && value === true) {
      // Only one primary brand allowed
      updated.forEach((b, i) => {
        b.is_primary = i === index;
      });
    } else {
      (updated[index] as Record<string, unknown>)[field] = value;
    }
    setBrands(updated);
  };

  const addCompetitor = () => {
    setCompetitors([...competitors, { name: "", domain: "" }]);
  };

  const removeCompetitor = (index: number) => {
    setCompetitors(competitors.filter((_, i) => i !== index));
  };

  const updateCompetitor = (index: number, field: string, value: string) => {
    const updated = [...competitors];
    (updated[index] as Record<string, string>)[field] = value;
    setCompetitors(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      // Filter out empty brands and competitors
      const validBrands = brands.filter((b) => b.name.trim());
      const validCompetitors = competitors.filter((c) => c.name.trim());

      if (!validBrands.length) {
        setError("At least one brand is required");
        setLoading(false);
        return;
      }

      const response = await projectsApi.create({
        name,
        domain,
        industry,
        country,
        brands: validBrands,
        competitors: validCompetitors.length > 0 ? validCompetitors : undefined,
      });

      // Update store
      const newProject = response.data;
      setProjects([...projects, newProject]);
      setCurrentProject(newProject);

      router.push("/dashboard");
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string | Array<{ msg: string; loc?: string[] }> } } };
      const detail = error.response?.data?.detail;

      // Handle validation errors (array of error objects from FastAPI)
      if (Array.isArray(detail)) {
        const messages = detail.map((e) => e.msg).join(". ");
        setError(messages || "Validation error. Please check your inputs.");
      } else if (typeof detail === "string") {
        setError(detail);
      } else {
        setError("Failed to create project. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto">
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
          <CardTitle>Create New Project</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && (
              <div className="bg-danger-50 text-danger-600 px-4 py-3 rounded-md text-sm">
                {error}
              </div>
            )}

            {/* Basic Info */}
            <div className="space-y-4">
              <div>
                <label htmlFor="name" className="label">
                  Project Name *
                </label>
                <input
                  id="name"
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="My Company"
                  className="input mt-1"
                />
              </div>

              <div>
                <label htmlFor="domain" className="label">
                  Domain *
                </label>
                <input
                  id="domain"
                  type="text"
                  required
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  placeholder="example.com"
                  className="input mt-1"
                />
              </div>

              <div>
                <label htmlFor="industry" className="label">
                  Industry *
                </label>
                <select
                  id="industry"
                  required
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                  className="input mt-1"
                >
                  <option value="">Select an industry</option>
                  <option value="technology">Technology / SaaS</option>
                  <option value="ecommerce">E-commerce / Retail</option>
                  <option value="finance">Finance / Fintech</option>
                  <option value="healthcare">Healthcare</option>
                  <option value="education">Education</option>
                  <option value="marketing">Marketing</option>
                  <option value="legal">Legal</option>
                  <option value="real_estate">Real Estate</option>
                  <option value="travel">Travel & Hospitality</option>
                  <option value="food_beverage">Food & Beverage</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div>
                <label htmlFor="country" className="label">
                  <Globe className="h-4 w-4 inline mr-1" />
                  Target Country *
                </label>
                <p className="text-xs text-gray-500 mb-2">
                  All LLM analysis and Google AIO results will be specific to this country.
                </p>
                <select
                  id="country"
                  required
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  className="input mt-1"
                >
                  {availableCountries.map((c) => (
                    <option key={c.code} value={c.code}>
                      {c.flag} {c.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Brands */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="label">Brands *</label>
                <Button type="button" variant="ghost" size="sm" onClick={addBrand}>
                  <Plus className="h-4 w-4 mr-1" />
                  Add Brand
                </Button>
              </div>
              <p className="text-xs text-gray-500 mb-3">
                Add your brand names that LLMs should mention. The primary brand is used for main tracking.
              </p>
              <div className="space-y-3">
                {brands.map((brand, index) => (
                  <div key={index} className="flex gap-2 items-start">
                    <div className="flex-1">
                      <input
                        type="text"
                        value={brand.name}
                        onChange={(e) => updateBrand(index, "name", e.target.value)}
                        placeholder="Brand name"
                        className="input"
                      />
                    </div>
                    <label className="flex items-center gap-2 px-3 py-2 text-sm">
                      <input
                        type="radio"
                        name="primary_brand"
                        checked={brand.is_primary}
                        onChange={() => updateBrand(index, "is_primary", true)}
                      />
                      Primary
                    </label>
                    {brands.length > 1 && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeBrand(index)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Competitors */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="label">Competitors (Optional)</label>
                <Button type="button" variant="ghost" size="sm" onClick={addCompetitor}>
                  <Plus className="h-4 w-4 mr-1" />
                  Add Competitor
                </Button>
              </div>
              <p className="text-xs text-gray-500 mb-3">
                Add competitors to track and compare visibility against.
              </p>
              {competitors.length === 0 ? (
                <p className="text-sm text-gray-400 italic">No competitors added</p>
              ) : (
                <div className="space-y-3">
                  {competitors.map((competitor, index) => (
                    <div key={index} className="flex gap-2 items-start">
                      <div className="flex-1">
                        <input
                          type="text"
                          value={competitor.name}
                          onChange={(e) => updateCompetitor(index, "name", e.target.value)}
                          placeholder="Competitor name"
                          className="input"
                        />
                      </div>
                      <div className="flex-1">
                        <input
                          type="text"
                          value={competitor.domain}
                          onChange={(e) => updateCompetitor(index, "domain", e.target.value)}
                          placeholder="competitor.com (optional)"
                          className="input"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => removeCompetitor(index)}
                      >
                        <X className="h-4 w-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Submit */}
            <div className="flex gap-3 pt-4">
              <Button type="submit" loading={loading}>
                Create Project
              </Button>
              <Link href="/dashboard">
                <Button type="button" variant="outline">
                  Cancel
                </Button>
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
