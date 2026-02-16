"use client";

import { useState } from "react";
import { useProjectStore } from "@/lib/store";
import {
  FlaskConical, Plus, Sparkles, RefreshCw, Copy, Check,
  ArrowRight, Lightbulb, Target, BarChart3, Trash2, ChevronDown
} from "lucide-react";

interface ContentVariant {
  id: string;
  label: string;
  content: string;
  aiScore: number | null;
  loading: boolean;
}

export default function ABTestContentPage() {
  const { currentProject } = useProjectStore();
  const [keyword, setKeyword] = useState("");
  const [contentType, setContentType] = useState<"title" | "description" | "paragraph">("title");
  const [variants, setVariants] = useState<ContentVariant[]>([
    { id: "1", label: "Variant A", content: "", aiScore: null, loading: false },
    { id: "2", label: "Variant B", content: "", aiScore: null, loading: false },
  ]);
  const [analyzing, setAnalyzing] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const addVariant = () => {
    const nextLabel = String.fromCharCode(65 + variants.length); // A, B, C, ...
    setVariants([
      ...variants,
      { id: Date.now().toString(), label: `Variant ${nextLabel}`, content: "", aiScore: null, loading: false }
    ]);
  };

  const removeVariant = (id: string) => {
    if (variants.length <= 2) return;
    setVariants(variants.filter(v => v.id !== id));
  };

  const updateVariant = (id: string, content: string) => {
    setVariants(variants.map(v => v.id === id ? { ...v, content } : v));
  };

  const generateWithAI = async (id: string) => {
    if (!keyword) return;

    setVariants(variants.map(v => v.id === id ? { ...v, loading: true } : v));

    // Simulate AI generation
    await new Promise(resolve => setTimeout(resolve, 1500));

    const templates: Record<string, string[]> = {
      title: [
        `Best ${keyword} Solutions in 2024 - Complete Guide`,
        `Top 10 ${keyword} Tools for Modern Businesses`,
        `${keyword}: Everything You Need to Know`,
        `How to Choose the Right ${keyword} for Your Company`,
      ],
      description: [
        `Discover the leading ${keyword} solutions that help businesses streamline operations, improve efficiency, and drive growth. Compare features, pricing, and reviews.`,
        `Looking for the best ${keyword}? Our comprehensive guide covers everything from basic features to advanced capabilities, helping you make an informed decision.`,
        `Compare top ${keyword} options side by side. Learn about key features, integrations, pricing plans, and what real users are saying about each solution.`,
      ],
      paragraph: [
        `When it comes to ${keyword}, businesses need solutions that are both powerful and easy to use. The right tool can transform your operations, saving countless hours and reducing errors. In this guide, we'll explore the top options available in the market today, highlighting what makes each one unique and which scenarios they're best suited for.`,
        `The ${keyword} landscape has evolved significantly in recent years. With cloud-based solutions becoming the norm, companies now have access to features that were once reserved for enterprise organizations. From automated workflows to real-time analytics, modern ${keyword} tools offer capabilities that can genuinely transform how you operate.`,
      ],
    };

    const options = templates[contentType];
    const randomContent = options[Math.floor(Math.random() * options.length)];

    setVariants(variants.map(v =>
      v.id === id
        ? { ...v, content: randomContent, loading: false }
        : v
    ));
  };

  const analyzeAll = async () => {
    if (variants.some(v => !v.content)) return;

    setAnalyzing(true);

    // Simulate analysis
    await new Promise(resolve => setTimeout(resolve, 2000));

    setVariants(variants.map(v => ({
      ...v,
      aiScore: Math.floor(Math.random() * 30) + 70 // Random score 70-100
    })));

    setAnalyzing(false);
  };

  const handleCopy = (id: string, content: string) => {
    navigator.clipboard.writeText(content);
    setCopied(id);
    setTimeout(() => setCopied(null), 2000);
  };

  const getScoreColor = (score: number) => {
    if (score >= 90) return "text-green-600";
    if (score >= 80) return "text-amber-600";
    return "text-gray-600";
  };

  const getBestVariant = () => {
    if (!variants.some(v => v.aiScore !== null)) return null;
    return variants.reduce((best, current) =>
      (current.aiScore || 0) > (best.aiScore || 0) ? current : best
    );
  };

  const bestVariant = getBestVariant();

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center shadow-lg">
            <FlaskConical className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">A/B Test Content</h1>
            <p className="text-gray-500">Compare content variants for AI visibility optimization</p>
          </div>
        </div>
      </div>

      {/* Configuration */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Target Keyword
            </label>
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="e.g., HR software, payroll management"
              className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Content Type
            </label>
            <div className="relative">
              <select
                value={contentType}
                onChange={(e) => setContentType(e.target.value as typeof contentType)}
                className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent appearance-none"
              >
                <option value="title">Page Title / H1</option>
                <option value="description">Meta Description</option>
                <option value="paragraph">Content Paragraph</option>
              </select>
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            </div>
          </div>
        </div>
      </div>

      {/* Variants */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">Content Variants</h2>
          <div className="flex items-center gap-2">
            <button
              onClick={addVariant}
              className="flex items-center gap-2 px-3 py-1.5 border border-gray-200 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
            >
              <Plus className="w-4 h-4" />
              Add Variant
            </button>
            <button
              onClick={analyzeAll}
              disabled={analyzing || variants.some(v => !v.content)}
              className="flex items-center gap-2 px-4 py-1.5 bg-violet-600 text-white rounded-lg text-sm font-medium hover:bg-violet-700 transition-colors disabled:opacity-50"
            >
              {analyzing ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <BarChart3 className="w-4 h-4" />
                  Analyze All
                </>
              )}
            </button>
          </div>
        </div>

        {variants.map((variant, idx) => (
          <div
            key={variant.id}
            className={`bg-white rounded-xl border p-5 ${
              bestVariant?.id === variant.id && variant.aiScore
                ? "border-green-300 ring-2 ring-green-100"
                : "border-gray-200"
            }`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-3">
                <span className="font-semibold text-gray-900">{variant.label}</span>
                {bestVariant?.id === variant.id && variant.aiScore && (
                  <span className="text-xs font-medium text-green-600 bg-green-100 px-2 py-0.5 rounded">
                    Best Performer
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {variant.aiScore !== null && (
                  <div className="flex items-center gap-2 px-3 py-1 bg-gray-50 rounded-lg">
                    <Target className="w-4 h-4 text-gray-400" />
                    <span className={`font-bold ${getScoreColor(variant.aiScore)}`}>
                      {variant.aiScore}
                    </span>
                    <span className="text-xs text-gray-500">AI Score</span>
                  </div>
                )}
                <button
                  onClick={() => generateWithAI(variant.id)}
                  disabled={variant.loading || !keyword}
                  className="flex items-center gap-1 px-3 py-1.5 text-violet-600 hover:bg-violet-50 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                >
                  {variant.loading ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Sparkles className="w-4 h-4" />
                  )}
                  Generate
                </button>
                <button
                  onClick={() => handleCopy(variant.id, variant.content)}
                  disabled={!variant.content}
                  className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors disabled:opacity-50"
                >
                  {copied === variant.id ? (
                    <Check className="w-4 h-4 text-green-500" />
                  ) : (
                    <Copy className="w-4 h-4" />
                  )}
                </button>
                {variants.length > 2 && (
                  <button
                    onClick={() => removeVariant(variant.id)}
                    className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>

            <textarea
              value={variant.content}
              onChange={(e) => updateVariant(variant.id, e.target.value)}
              placeholder={`Enter ${contentType === "title" ? "page title" : contentType === "description" ? "meta description" : "content paragraph"}...`}
              className={`w-full px-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent resize-none ${
                contentType === "paragraph" ? "min-h-[150px]" : "min-h-[80px]"
              }`}
            />

            {/* Character count */}
            <div className="flex items-center justify-between mt-2 text-xs text-gray-400">
              <span>{variant.content.length} characters</span>
              {contentType === "title" && variant.content.length > 60 && (
                <span className="text-amber-500">Recommended: 50-60 characters</span>
              )}
              {contentType === "description" && variant.content.length > 160 && (
                <span className="text-amber-500">Recommended: 150-160 characters</span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Analysis Results */}
      {bestVariant && bestVariant.aiScore !== null && (
        <div className="bg-gradient-to-br from-green-50 to-emerald-50 border border-green-200 rounded-xl p-6">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 rounded-xl bg-green-500 flex items-center justify-center">
              <Lightbulb className="w-6 h-6 text-white" />
            </div>
            <div className="flex-1">
              <h3 className="font-bold text-green-900 text-lg">Recommendation</h3>
              <p className="text-green-800 mt-1">
                <strong>{bestVariant.label}</strong> performs best with an AI visibility score of <strong>{bestVariant.aiScore}</strong>.
                This variant is most likely to rank well in AI-generated responses.
              </p>
              <div className="mt-4 p-4 bg-white/50 rounded-lg">
                <p className="text-sm text-green-800 font-medium mb-2">Winning Content:</p>
                <p className="text-green-900">{bestVariant.content}</p>
              </div>
              <button className="mt-4 flex items-center gap-2 text-green-700 font-medium hover:underline">
                Use this variant <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tips */}
      <div className="bg-gray-50 rounded-xl border border-gray-200 p-6">
        <h3 className="font-bold text-gray-900 mb-4">Tips for AI-Optimized Content</h3>
        <div className="grid grid-cols-2 gap-4">
          {[
            "Include your target keyword naturally in the content",
            "Use clear, descriptive language that AI can understand",
            "Structure content with proper headings and lists",
            "Include specific facts, numbers, and examples",
            "Mention your brand name in a natural context",
            "Write conversational content that answers questions",
          ].map((tip, idx) => (
            <div key={idx} className="flex items-start gap-2 text-sm text-gray-600">
              <Check className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
              {tip}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
