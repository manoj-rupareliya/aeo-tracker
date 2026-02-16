"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuthStore, useProjectStore } from "@/lib/store";
import { projectsApi } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";
import {
  LayoutDashboard,
  FolderKanban,
  Search,
  BarChart3,
  Settings,
  LogOut,
  Menu,
  X,
  ChevronDown,
  Activity,
  TrendingUp,
  Lightbulb,
  Network,
  Sparkles,
  Check,
  FileText,
  Bot,
  MessageSquare,
  FlaskConical,
  Key,
  HelpCircle,
  Gift,
  Star,
  Building2,
} from "lucide-react";

const navigation = [
  { name: "Organization", href: "/dashboard/organization", icon: Building2 },
  { name: "Projects", href: "/dashboard/projects", icon: FolderKanban },
  { name: "Keywords", href: "/dashboard/keywords", icon: Search },
  { name: "Settings", href: "/dashboard/settings", icon: Settings },
];

const toolsNavigation = [
  { name: "LLMs.txt generator", href: "/dashboard/tools/llms-txt", icon: FileText },
  { name: "AI crawlability checker", href: "/dashboard/tools/crawlability", icon: Bot },
  { name: "Reddit threads finder", href: "/dashboard/tools/reddit", icon: MessageSquare },
  { name: "A/B test content", href: "/dashboard/tools/ab-test", icon: FlaskConical },
  { name: "API access", href: "/dashboard/settings/api", icon: Key },
];

const supportNavigation = [
  { name: "Suggest a feature", href: "/dashboard/feedback", icon: Star },
  { name: "Become an affiliate", href: "/dashboard/affiliate", icon: Gift },
  { name: "Help & support", href: "/dashboard/help", icon: HelpCircle },
];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [projectDropdownOpen, setProjectDropdownOpen] = useState(false);
  const { user, logout } = useAuthStore();
  const { currentProject, setCurrentProject, projects, setProjects } = useProjectStore();

  // Fetch projects
  const { data: projectsData } = useQuery({
    queryKey: ["projects"],
    queryFn: async () => {
      const response = await projectsApi.list();
      return response.data;
    },
  });

  useEffect(() => {
    if (projectsData?.items) {
      setProjects(projectsData.items);
      if (!currentProject && projectsData.items.length > 0) {
        setCurrentProject(projectsData.items[0]);
      }
    }
  }, [projectsData, currentProject, setCurrentProject, setProjects]);

  const handleSelectProject = (project: any) => {
    setCurrentProject(project);
    setProjectDropdownOpen(false);
  };

  return (
    <div className="min-h-screen mesh-gradient">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-900/60 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 bg-white/90 backdrop-blur-xl shadow-2xl transform transition-transform duration-300 ease-in-out lg:hidden",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-20 items-center justify-between px-6 border-b border-gray-100">
          <Link href="/dashboard" className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
              <Sparkles className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold gradient-text">llmscm</span>
          </Link>
          <button onClick={() => setSidebarOpen(false)} className="p-2 rounded-lg hover:bg-gray-100">
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>
        <nav className="flex flex-col gap-1 p-4">
          {navigation.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={isActive ? "nav-item-active" : "nav-item"}
                onClick={() => setSidebarOpen(false)}
              >
                <item.icon className="h-5 w-5" />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Desktop sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-72 lg:flex-col">
        <div className="flex flex-col flex-grow bg-white/70 backdrop-blur-xl border-r border-gray-200/50">
          {/* Logo */}
          <div className="flex h-20 items-center px-6 border-b border-gray-100">
            <Link href="/dashboard" className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/30 animate-pulse-glow">
                <Sparkles className="h-5 w-5 text-white" />
              </div>
              <div>
                <span className="text-xl font-bold gradient-text">llmscm</span>
                <p className="text-xs text-gray-400">AI Visibility Platform</p>
              </div>
            </Link>
          </div>

          {/* Project selector */}
          {projects.length > 0 && (
            <div className="px-4 py-4 border-b border-gray-100">
              <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-2">Project</p>
              <div className="relative">
                <button
                  onClick={() => setProjectDropdownOpen(!projectDropdownOpen)}
                  className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-900 bg-gradient-to-r from-gray-50 to-gray-100/50 rounded-xl hover:from-gray-100 hover:to-gray-100 transition-all duration-200 ring-1 ring-gray-200/50"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-2 h-2 rounded-full bg-gradient-to-r from-emerald-400 to-emerald-500 animate-pulse" />
                    <span className="truncate">{currentProject?.name || "Select Project"}</span>
                  </div>
                  <ChevronDown className={cn("h-4 w-4 text-gray-400 transition-transform", projectDropdownOpen && "rotate-180")} />
                </button>

                {projectDropdownOpen && (
                  <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl shadow-xl ring-1 ring-gray-100 py-2 z-50 max-h-64 overflow-auto">
                    {projects.map((project: any) => (
                      <button
                        key={project.id}
                        onClick={() => handleSelectProject(project)}
                        className="w-full text-left px-4 py-3 hover:bg-gray-50 flex items-center justify-between group transition-colors"
                      >
                        <div>
                          <p className="font-medium text-gray-900 group-hover:text-violet-600 transition-colors">{project.name}</p>
                          <p className="text-xs text-gray-500">{project.domain}</p>
                        </div>
                        {currentProject?.id === project.id && (
                          <Check className="h-4 w-4 text-violet-500" />
                        )}
                      </button>
                    ))}
                    <div className="border-t border-gray-100 mt-2 pt-2 px-2">
                      <Link href="/dashboard/projects/new">
                        <button className="w-full text-left px-3 py-2 text-sm text-violet-600 hover:bg-violet-50 rounded-lg font-medium transition-colors">
                          + New Project
                        </button>
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Navigation */}
          <nav className="flex-1 flex flex-col gap-1 p-4 overflow-y-auto">
            {navigation.map((item) => {
              const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={isActive ? "nav-item-active" : "nav-item"}
                >
                  <item.icon className="h-5 w-5" />
                  {item.name}
                </Link>
              );
            })}

            {/* Tools Section */}
            <div className="mt-auto pt-6 border-t border-gray-100">
              {toolsNavigation.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`${isActive ? "nav-item-active" : "nav-item"} text-sm`}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.name}
                  </Link>
                );
              })}
            </div>

            {/* Support Section */}
            <div className="pt-4 border-t border-gray-100 mt-4">
              {supportNavigation.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={`${isActive ? "nav-item-active" : "nav-item"} text-sm`}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.name}
                  </Link>
                );
              })}
            </div>
          </nav>

          {/* User section */}
          <div className="border-t border-gray-100 p-4">
            <div className="flex items-center gap-3 p-3 rounded-xl bg-gradient-to-r from-gray-50 to-gray-100/50">
              <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/20">
                <span className="text-sm font-bold text-white">
                  {user?.full_name?.charAt(0) || "U"}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-semibold text-gray-900 truncate">
                  {user?.full_name || "User"}
                </p>
                <p className="text-xs text-gray-500 truncate">{user?.email}</p>
              </div>
              <button
                onClick={logout}
                className="p-2 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors"
                title="Logout"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="lg:pl-72">
        {/* Top bar */}
        <div className="sticky top-0 z-10 flex h-16 items-center gap-4 border-b border-gray-200/50 bg-white/70 backdrop-blur-xl px-4 lg:px-8">
          <button
            className="lg:hidden p-2 rounded-lg hover:bg-gray-100"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-5 w-5 text-gray-600" />
          </button>

          {/* Breadcrumb / Page title */}
          <div className="flex-1">
            <h1 className="text-lg font-semibold text-gray-900 capitalize">
              {pathname.split("/").pop() || "Dashboard"}
            </h1>
          </div>

          {/* Quick actions */}
          <div className="flex items-center gap-3">
            <button className="btn-primary text-sm">
              <Sparkles className="h-4 w-4 mr-2" />
              Run Analysis
            </button>
          </div>
        </div>

        {/* Page content */}
        <main className="p-4 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
