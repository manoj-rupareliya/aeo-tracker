"use client";

import { useState } from "react";
import { useProjectStore } from "@/lib/store";
import {
  MessageSquare, Search, ExternalLink, ThumbsUp, MessageCircle,
  Clock, TrendingUp, Filter, RefreshCw, ArrowUpRight, Users, Star
} from "lucide-react";

interface RedditThread {
  id: string;
  title: string;
  subreddit: string;
  url: string;
  score: number;
  comments: number;
  created: string;
  author: string;
  relevanceScore: number;
  mentionsBrand: boolean;
  mentionsCompetitor: string | null;
}

export default function RedditThreadsFinderPage() {
  const { currentProject } = useProjectStore();
  const [query, setQuery] = useState(currentProject?.name || "");
  const [searching, setSearching] = useState(false);
  const [threads, setThreads] = useState<RedditThread[] | null>(null);
  const [filter, setFilter] = useState<"all" | "mentions" | "opportunities">("all");

  // Mock data
  const mockThreads: RedditThread[] = [
    {
      id: "1",
      title: "What's the best HR software for a 50-person company in India?",
      subreddit: "r/IndianStartups",
      url: "https://reddit.com/r/IndianStartups/comments/abc123",
      score: 156,
      comments: 78,
      created: "2 days ago",
      author: "startup_founder",
      relevanceScore: 95,
      mentionsBrand: false,
      mentionsCompetitor: "Zoho People"
    },
    {
      id: "2",
      title: "Comparing HRMS solutions - Keka vs Zoho vs Others",
      subreddit: "r/india",
      url: "https://reddit.com/r/india/comments/def456",
      score: 234,
      comments: 145,
      created: "1 week ago",
      author: "hr_manager_india",
      relevanceScore: 88,
      mentionsBrand: false,
      mentionsCompetitor: "Keka, Zoho People"
    },
    {
      id: "3",
      title: "Need recommendations for payroll software with compliance features",
      subreddit: "r/humanresources",
      url: "https://reddit.com/r/humanresources/comments/ghi789",
      score: 89,
      comments: 52,
      created: "3 days ago",
      author: "payroll_person",
      relevanceScore: 82,
      mentionsBrand: false,
      mentionsCompetitor: null
    },
    {
      id: "4",
      title: "FactoHR review - anyone using it?",
      subreddit: "r/IndianStartups",
      url: "https://reddit.com/r/IndianStartups/comments/jkl012",
      score: 45,
      comments: 23,
      created: "5 days ago",
      author: "curious_cto",
      relevanceScore: 100,
      mentionsBrand: true,
      mentionsCompetitor: null
    },
    {
      id: "5",
      title: "Automating leave management - what tools do you use?",
      subreddit: "r/smallbusiness",
      url: "https://reddit.com/r/smallbusiness/comments/mno345",
      score: 67,
      comments: 31,
      created: "1 day ago",
      author: "small_biz_owner",
      relevanceScore: 75,
      mentionsBrand: false,
      mentionsCompetitor: null
    },
  ];

  const handleSearch = async () => {
    if (!query) return;
    setSearching(true);

    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 2000));

    setThreads(mockThreads);
    setSearching(false);
  };

  const filteredThreads = threads?.filter(thread => {
    if (filter === "mentions") return thread.mentionsBrand;
    if (filter === "opportunities") return !thread.mentionsBrand && !thread.mentionsCompetitor;
    return true;
  });

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-orange-500 to-red-600 flex items-center justify-center shadow-lg">
            <MessageSquare className="h-6 w-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Reddit Threads Finder</h1>
            <p className="text-gray-500">Find relevant Reddit discussions to engage with</p>
          </div>
        </div>
      </div>

      {/* Search */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex gap-3">
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search for topics, keywords, or your brand..."
              className="w-full pl-12 pr-4 py-3 border border-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={searching || !query}
            className="flex items-center gap-2 px-6 py-3 bg-orange-500 text-white rounded-lg font-medium hover:bg-orange-600 transition-colors disabled:opacity-50"
          >
            {searching ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <Search className="w-5 h-5" />
                Find Threads
              </>
            )}
          </button>
        </div>

        {/* Quick filters */}
        <div className="mt-4 flex flex-wrap gap-2">
          {["HR software", "HRMS India", "payroll software", "employee management"].map((suggestion) => (
            <button
              key={suggestion}
              onClick={() => setQuery(suggestion)}
              className="px-3 py-1.5 bg-gray-100 text-gray-700 rounded-full text-sm hover:bg-gray-200 transition-colors"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      {threads && (
        <>
          {/* Stats & Filters */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6 text-sm">
              <span className="text-gray-500">
                Found <strong className="text-gray-900">{threads.length}</strong> threads
              </span>
              <div className="flex items-center gap-2">
                <span className="flex items-center gap-1 text-green-600">
                  <Star className="w-4 h-4" />
                  {threads.filter(t => t.mentionsBrand).length} mention your brand
                </span>
                <span className="flex items-center gap-1 text-amber-600">
                  <TrendingUp className="w-4 h-4" />
                  {threads.filter(t => !t.mentionsBrand && !t.mentionsCompetitor).length} opportunities
                </span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {[
                { id: "all", label: "All Threads" },
                { id: "mentions", label: "Brand Mentions" },
                { id: "opportunities", label: "Opportunities" },
              ].map((item) => (
                <button
                  key={item.id}
                  onClick={() => setFilter(item.id as typeof filter)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    filter === item.id
                      ? "bg-violet-100 text-violet-700"
                      : "text-gray-600 hover:bg-gray-100"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>

          {/* Thread List */}
          <div className="space-y-3">
            {filteredThreads?.map((thread) => (
              <div
                key={thread.id}
                className={`bg-white rounded-xl border p-5 hover:shadow-md transition-shadow ${
                  thread.mentionsBrand ? "border-green-200 bg-green-50/30" :
                  !thread.mentionsCompetitor ? "border-amber-200 bg-amber-50/30" :
                  "border-gray-200"
                }`}
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-medium text-orange-600 bg-orange-100 px-2 py-0.5 rounded">
                        {thread.subreddit}
                      </span>
                      {thread.mentionsBrand && (
                        <span className="text-xs font-medium text-green-600 bg-green-100 px-2 py-0.5 rounded">
                          Mentions You
                        </span>
                      )}
                      {!thread.mentionsBrand && !thread.mentionsCompetitor && (
                        <span className="text-xs font-medium text-amber-600 bg-amber-100 px-2 py-0.5 rounded">
                          Opportunity
                        </span>
                      )}
                      {thread.mentionsCompetitor && (
                        <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                          Mentions: {thread.mentionsCompetitor}
                        </span>
                      )}
                    </div>

                    <a
                      href={thread.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-lg font-semibold text-gray-900 hover:text-violet-600 transition-colors line-clamp-2"
                    >
                      {thread.title}
                    </a>

                    <div className="flex items-center gap-4 mt-3 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <ThumbsUp className="w-4 h-4" />
                        {thread.score} upvotes
                      </span>
                      <span className="flex items-center gap-1">
                        <MessageCircle className="w-4 h-4" />
                        {thread.comments} comments
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock className="w-4 h-4" />
                        {thread.created}
                      </span>
                      <span className="flex items-center gap-1">
                        <Users className="w-4 h-4" />
                        u/{thread.author}
                      </span>
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-2">
                    <div className="text-right">
                      <p className="text-xs text-gray-500">Relevance</p>
                      <p className={`text-lg font-bold ${
                        thread.relevanceScore >= 90 ? "text-green-600" :
                        thread.relevanceScore >= 70 ? "text-amber-600" :
                        "text-gray-600"
                      }`}>
                        {thread.relevanceScore}%
                      </p>
                    </div>
                    <a
                      href={thread.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-sm text-violet-600 font-medium hover:underline"
                    >
                      View Thread
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Empty State */}
      {!threads && !searching && (
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-12 text-center">
          <MessageSquare className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">Find relevant Reddit discussions</h3>
          <p className="text-gray-500 max-w-md mx-auto">
            Search for your brand, industry keywords, or competitors to find Reddit threads where you can engage and build visibility.
          </p>
        </div>
      )}
    </div>
  );
}
