/**
 * Global State Management with Zustand
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import Cookies from "js-cookie";

// Types
interface User {
  id: string;
  email: string;
  full_name: string;
  subscription_tier: string;
  monthly_token_limit: number;
  tokens_used_this_month: number;
}

interface Project {
  id: string;
  name: string;
  domain: string;
  industry: string;
  enabled_llms: string[];
  brands: { id: string; name: string; is_primary: boolean }[];
  competitors: { id: string; name: string }[];
  keyword_count: number;
  total_runs: number;
  last_crawl_at: string | null;
}

// Auth Store
interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setLoading: (loading: boolean) => void;
  login: (accessToken: string, refreshToken: string, user: User) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      isLoading: true,

      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setLoading: (isLoading) => set({ isLoading }),

      login: (accessToken, refreshToken, user) => {
        Cookies.set("access_token", accessToken, { expires: 1 });
        Cookies.set("refresh_token", refreshToken, { expires: 7 });
        set({ user, isAuthenticated: true, isLoading: false });
      },

      logout: () => {
        Cookies.remove("access_token");
        Cookies.remove("refresh_token");
        set({ user: null, isAuthenticated: false });
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
);

// Project Store
interface ProjectState {
  currentProject: Project | null;
  projects: Project[];
  setCurrentProject: (project: Project | null) => void;
  setProjects: (projects: Project[]) => void;
  updateProject: (projectId: string, updates: Partial<Project>) => void;
}

export const useProjectStore = create<ProjectState>()((set) => ({
  currentProject: null,
  projects: [],

  setCurrentProject: (project) => set({ currentProject: project }),
  setProjects: (projects) => set({ projects }),

  updateProject: (projectId, updates) =>
    set((state) => ({
      projects: state.projects.map((p) =>
        p.id === projectId ? { ...p, ...updates } : p
      ),
      currentProject:
        state.currentProject?.id === projectId
          ? { ...state.currentProject, ...updates }
          : state.currentProject,
    })),
}));

// UI Store
interface UIState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>()((set) => ({
  sidebarOpen: true,
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
}));
