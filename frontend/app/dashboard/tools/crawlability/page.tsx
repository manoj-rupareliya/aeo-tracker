"use client";

import { useState } from "react";
import { useProjectStore } from "@/lib/store";
import {
  Bot, Search, CheckCircle, XCircle, AlertCircle, RefreshCw,
  Globe, FileText, Code, Shield, Zap, ExternalLink, ArrowRight
} from "lucide-react";

interface CrawlResult {
  check: string;
  status: "pass" | "fail" | "warning";
  message: string;
  details?: string;
}

export default function AICrawlabilityCheckerPage() {
  const { currentProject } = useProjectStore();
  const [url, setUrl] = useState(currentProject?.domain ? `https://${currentProject.domain}` : "");
  const [checking, setChecking] = useState(false);
  const [results, setResults] = useState<CrawlResult[] | null>(null);
  const [overallScore, setOverallScore] = useState<number | null>(null);

  const handleCheck = async () => {
    if (!url) return;

    setChecking(true);
    setResults(null);

    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 2500));

    // Mock results
    const mockResults: CrawlResult[] = [
      {
        check: "robots.txt",
        status: "pass",
        message: "robots.txt file found and accessible",
        details: "AI crawlers (GPTBot, Google-Extended, Claude-Web) are allowed"
      },
      {
        check: "llms.txt",
        status: "warning",
        message: "llms.txt file not found",
        details: "Consider adding an llms.txt file to provide AI-specific instructions"
      },
      {
        check: "Meta Tags",
        status: "pass",
        message: "AI-friendly meta tags detected",
        details: "Title, description, and Open Graph tags are present"
      },
      {
        check: "Structured Data",
        status: "pass",
        message: "Schema.org markup found",
        details: "Organization, Product, and FAQPage schemas detected"
      },
      {
        check: "Content Accessibility",
        status: "pass",
        message: "Main content is accessible",
        details: "No JavaScript-only content blocking detected"
      },
      {
        check: "Page Speed",
        status: "warning",
        message: "Page load time is moderate",
        details: "Consider optimizing for faster AI crawler access (3.2s load time)"
      },
      {
        check: "SSL Certificate",
        status: "pass",
        message: "Valid SSL certificate",
        details: "HTTPS is properly configured"
      },
      {
        check: "Sitemap",
        status: "pass",
        message: "XML sitemap found",
        details: "Sitemap contains 156 URLs and is properly formatted"
      },
    ];

    setResults(mockResults);

    // Calculate score
    const passCount = mockResults.filter(r => r.status === "pass").length;
    const warningCount = mockResults.filter(r => r.status === "warning").length;
    const score = Math.round((passCount * 100 + warningCount * 50) / mockResults.length);
    setOverallScore(score);

    setChecking(false);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "pass":
        return <CheckCircle className="w-5 h-5 text-green-500" />;
      case "fail":
        return <XCircle className="w-5 h-5 text-red-500" />;
      case "warning":
        return <AlertCircle className="w-5 h-5 text-amber-500" />;
      default:
        return null;
    }
  };

  const getStatusBg = (status: string) => {
    switch (status) {
      case "pass":
        return "bg-green-50 border-green-200";
      case "fail":
        return "bg-red-50 border-red-200";
      case "warning":
        return "bg-amber-50 border-amber-200";
      default:
        return "bg-gray-50 border-gray-200";
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg">
            <Bot className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">AI Crawlability Checker</h1>
            <p className="text-gray-500">Check if your website is optimized for AI crawlers</p>
          </div>
        </div>
      </div>

      {/* URL Input */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Globe className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com"
              className="w-full pl-12 pr-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent text-lg"
            />
          </div>
          <button
            onClick={handleCheck}
            disabled={checking || !url}
            className="flex items-center gap-2 px-6 py-3 bg-violet-600 text-white rounded-lg font-medium hover:bg-violet-700 transition-colors disabled:opacity-50"
          >
            {checking ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                Checking...
              </>
            ) : (
              <>
                <Search className="w-5 h-5" />
                Check Crawlability
              </>
            )}
          </button>
        </div>

        {/* What we check */}
        <div className="mt-6 grid grid-cols-4 gap-4">
          {[
            { icon: FileText, label: "robots.txt" },
            { icon: Code, label: "Structured Data" },
            { icon: Shield, label: "Security" },
            { icon: Zap, label: "Performance" },
          ].map((item) => (
            <div key={item.label} className="flex items-center gap-2 text-sm text-gray-500">
              <item.icon className="w-4 h-4" />
              {item.label}
            </div>
          ))}
        </div>
      </div>

      {/* Results */}
      {results && (
        <div className="space-y-4">
          {/* Overall Score */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-gray-900">Overall AI Crawlability Score</h2>
                <p className="text-gray-500 text-sm mt-1">
                  Based on {results.length} checks
                </p>
              </div>
              <div className="text-right">
                <div className={`text-4xl font-bold ${
                  overallScore! >= 80 ? "text-green-600" :
                  overallScore! >= 60 ? "text-amber-600" :
                  "text-red-600"
                }`}>
                  {overallScore}%
                </div>
                <p className={`text-sm ${
                  overallScore! >= 80 ? "text-green-600" :
                  overallScore! >= 60 ? "text-amber-600" :
                  "text-red-600"
                }`}>
                  {overallScore! >= 80 ? "Excellent" :
                   overallScore! >= 60 ? "Good" :
                   "Needs Improvement"}
                </p>
              </div>
            </div>

            {/* Progress bar */}
            <div className="mt-4 h-3 bg-gray-200 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  overallScore! >= 80 ? "bg-green-500" :
                  overallScore! >= 60 ? "bg-amber-500" :
                  "bg-red-500"
                }`}
                style={{ width: `${overallScore}%` }}
              />
            </div>

            {/* Summary */}
            <div className="mt-4 flex gap-6">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-green-500" />
                <span className="text-sm text-gray-600">
                  {results.filter(r => r.status === "pass").length} Passed
                </span>
              </div>
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-amber-500" />
                <span className="text-sm text-gray-600">
                  {results.filter(r => r.status === "warning").length} Warnings
                </span>
              </div>
              <div className="flex items-center gap-2">
                <XCircle className="w-4 h-4 text-red-500" />
                <span className="text-sm text-gray-600">
                  {results.filter(r => r.status === "fail").length} Failed
                </span>
              </div>
            </div>
          </div>

          {/* Detailed Results */}
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-100">
              <h2 className="font-bold text-gray-900">Detailed Results</h2>
            </div>
            <div className="divide-y divide-gray-100">
              {results.map((result, idx) => (
                <div
                  key={idx}
                  className={`px-6 py-4 ${getStatusBg(result.status)} border-l-4 ${
                    result.status === "pass" ? "border-l-green-500" :
                    result.status === "warning" ? "border-l-amber-500" :
                    "border-l-red-500"
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      {getStatusIcon(result.status)}
                      <div>
                        <p className="font-medium text-gray-900">{result.check}</p>
                        <p className="text-sm text-gray-600 mt-1">{result.message}</p>
                        {result.details && (
                          <p className="text-xs text-gray-500 mt-1">{result.details}</p>
                        )}
                      </div>
                    </div>
                    {result.status === "warning" && (
                      <button className="text-sm text-violet-600 font-medium flex items-center gap-1 hover:underline">
                        Fix this <ArrowRight className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Recommendations */}
          {results.some(r => r.status !== "pass") && (
            <div className="bg-violet-50 border border-violet-200 rounded-xl p-6">
              <h3 className="font-bold text-violet-900 mb-3">Recommendations</h3>
              <ul className="space-y-2">
                {results.filter(r => r.status !== "pass").map((result, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-sm text-violet-800">
                    <ArrowRight className="w-4 h-4 mt-0.5 shrink-0" />
                    <span>
                      {result.check === "llms.txt" && "Create an llms.txt file using our generator tool"}
                      {result.check === "Page Speed" && "Optimize images and enable caching for faster load times"}
                      {result.status === "fail" && `Fix ${result.check} issue: ${result.message}`}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Empty State */}
      {!results && !checking && (
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-12 text-center">
          <Bot className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Enter a URL to check</h3>
          <p className="text-gray-500 max-w-md mx-auto">
            We'll analyze your website's compatibility with AI crawlers like GPTBot, Claude-Web, and Google-Extended.
          </p>
        </div>
      )}
    </div>
  );
}
