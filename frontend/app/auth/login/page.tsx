"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Button } from "@/components/ui/button";
import { Sparkles, ArrowRight } from "lucide-react";

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((state) => state.login);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await authApi.login({ email, password });
      const { access_token, refresh_token } = response.data;

      // Save tokens first so getMe can use them
      const Cookies = (await import("js-cookie")).default;
      Cookies.set("access_token", access_token, { expires: 1 });
      Cookies.set("refresh_token", refresh_token, { expires: 7 });

      // Get user data
      const userResponse = await authApi.getMe();

      login(access_token, refresh_token, userResponse.data);
      router.push("/dashboard");
    } catch (err: unknown) {
      const error = err as { response?: { data?: { detail?: string } } };
      setError(error.response?.data?.detail || "Login failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex mesh-gradient">
      {/* Left side - Branding */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-violet-600 via-indigo-600 to-purple-700 p-12 flex-col justify-between relative overflow-hidden">
        {/* Decorative elements */}
        <div className="absolute top-0 left-0 w-96 h-96 bg-white/10 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2" />
        <div className="absolute bottom-0 right-0 w-96 h-96 bg-pink-500/20 rounded-full blur-3xl translate-x-1/2 translate-y-1/2" />
        <div className="absolute top-1/2 left-1/2 w-64 h-64 bg-indigo-400/20 rounded-full blur-3xl -translate-x-1/2 -translate-y-1/2" />

        <div className="relative z-10">
          <Link href="/" className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <Sparkles className="h-6 w-6 text-white" />
            </div>
            <span className="text-2xl font-bold text-white">llmscm</span>
          </Link>
        </div>

        <div className="relative z-10 space-y-6">
          <h1 className="text-4xl font-bold text-white leading-tight">
            Know How AI<br />
            <span className="text-violet-200">Sees Your Brand</span>
          </h1>
          <p className="text-lg text-violet-100/80 max-w-md">
            Track your visibility across ChatGPT, Claude, Gemini, and Perplexity. Get actionable insights to improve your AI presence.
          </p>
          <div className="flex items-center gap-4 pt-4">
            <div className="flex -space-x-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-300 to-indigo-400 ring-2 ring-white/20" />
              ))}
            </div>
            <p className="text-sm text-violet-200">
              <span className="font-semibold text-white">2,500+</span> brands tracking their AI visibility
            </p>
          </div>
        </div>

        <div className="relative z-10 flex items-center gap-8 text-violet-200/60 text-sm">
          <span>Trusted by industry leaders</span>
        </div>
      </div>

      {/* Right side - Form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex justify-center mb-8">
            <Link href="/" className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-500/30">
                <Sparkles className="h-6 w-6 text-white" />
              </div>
              <span className="text-2xl font-bold gradient-text">llmscm</span>
            </Link>
          </div>

          <div className="text-center mb-8">
            <h2 className="text-2xl font-bold text-gray-900">Welcome back</h2>
            <p className="text-gray-500 mt-2">
              Sign in to your account to continue
            </p>
          </div>

          <div className="card">
            <form className="space-y-5" onSubmit={handleSubmit}>
              {error && (
                <div className="bg-rose-50 text-rose-600 px-4 py-3 rounded-xl text-sm ring-1 ring-rose-200">
                  {error}
                </div>
              )}

              <div>
                <label htmlFor="email" className="label">
                  Email address
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="input mt-2"
                  placeholder="you@company.com"
                />
              </div>

              <div>
                <label htmlFor="password" className="label">
                  Password
                </label>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="input mt-2"
                  placeholder="Enter your password"
                />
              </div>

              <Button type="submit" className="w-full" loading={loading}>
                Sign in
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </form>

            <div className="mt-6 text-center">
              <p className="text-sm text-gray-500">
                Don't have an account?{" "}
                <Link
                  href="/auth/register"
                  className="font-semibold text-violet-600 hover:text-violet-500 transition-colors"
                >
                  Sign up free
                </Link>
              </p>
            </div>
          </div>

          <p className="mt-8 text-center text-xs text-gray-400">
            By signing in, you agree to our{" "}
            <a href="#" className="text-gray-500 hover:text-gray-700">Terms of Service</a>
            {" "}and{" "}
            <a href="#" className="text-gray-500 hover:text-gray-700">Privacy Policy</a>
          </p>
        </div>
      </div>
    </div>
  );
}
