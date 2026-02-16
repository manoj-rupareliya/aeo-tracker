"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/lib/store";
import { authApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { User, Bell, Key, Shield, Check, Loader2, X, Eye, EyeOff } from "lucide-react";

interface SavedKey {
  provider: string;
  masked_key: string;
  is_active: boolean;
}

export default function SettingsPage() {
  const { user } = useAuthStore();
  const [activeTab, setActiveTab] = useState("profile");
  const queryClient = useQueryClient();

  // API Key state
  const [apiKeys, setApiKeys] = useState<Record<string, string>>({
    openai: "",
    anthropic: "",
    google: "",
    perplexity: "",
  });
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({
    openai: false,
    anthropic: false,
    google: false,
    perplexity: false,
  });
  const [savingProvider, setSavingProvider] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const tabs = [
    { id: "profile", label: "Profile", icon: User },
    { id: "notifications", label: "Notifications", icon: Bell },
    { id: "api-keys", label: "API Keys", icon: Key },
    { id: "security", label: "Security", icon: Shield },
  ];

  // Fetch saved API keys
  const { data: savedKeys, isLoading: keysLoading } = useQuery({
    queryKey: ["api-keys"],
    queryFn: async () => {
      const response = await authApi.listApiKeys();
      return response.data;
    },
  });

  // Save API key mutation
  const saveKeyMutation = useMutation({
    mutationFn: async ({ provider, api_key }: { provider: string; api_key: string }) => {
      const response = await authApi.saveApiKey({ provider, api_key });
      return response.data;
    },
    onSuccess: (data, variables) => {
      setSaveSuccess(variables.provider);
      setSavingProvider(null);
      setApiKeys((prev) => ({ ...prev, [variables.provider]: "" }));
      queryClient.invalidateQueries({ queryKey: ["api-keys"] });
      setTimeout(() => setSaveSuccess(null), 3000);
    },
    onError: (error: any, variables) => {
      setSaveError(variables.provider);
      setSavingProvider(null);
      setTimeout(() => setSaveError(null), 3000);
    },
  });

  const handleSaveKey = (provider: string) => {
    const key = apiKeys[provider];
    if (!key.trim()) return;

    setSavingProvider(provider);
    setSaveSuccess(null);
    setSaveError(null);
    saveKeyMutation.mutate({ provider: provider.toLowerCase(), api_key: key });
  };

  const getKeyStatus = (provider: string) => {
    const saved = savedKeys?.items?.find(
      (k: SavedKey) => k.provider.toLowerCase() === provider.toLowerCase()
    );
    return saved;
  };

  const providerDisplayNames: Record<string, string> = {
    openai: "OpenAI",
    anthropic: "Anthropic",
    google: "Google",
    perplexity: "Perplexity",
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500">Manage your account settings</p>
      </div>

      <div className="flex gap-6">
        {/* Sidebar */}
        <div className="w-56 shrink-0">
          <Card className="p-2">
            <nav className="space-y-1">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 text-sm font-medium rounded-xl transition-all ${
                    activeTab === tab.id
                      ? "bg-gradient-to-r from-violet-500 to-indigo-600 text-white shadow-lg shadow-violet-500/25"
                      : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  <tab.icon className="h-4 w-4" />
                  {tab.label}
                </button>
              ))}
            </nav>
          </Card>
        </div>

        {/* Content */}
        <div className="flex-1">
          {activeTab === "profile" && (
            <Card>
              <CardHeader>
                <CardTitle>Profile Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <label className="label">Full Name</label>
                  <input
                    type="text"
                    defaultValue={user?.full_name || ""}
                    className="input mt-1"
                  />
                </div>
                <div>
                  <label className="label">Email</label>
                  <input
                    type="email"
                    defaultValue={user?.email || ""}
                    disabled
                    className="input mt-1 bg-gray-100"
                  />
                  <p className="text-xs text-gray-500 mt-1">Email cannot be changed</p>
                </div>
                <div>
                  <label className="label">Subscription</label>
                  <div className="mt-1 p-4 bg-gradient-to-r from-violet-50 to-indigo-50 rounded-xl ring-1 ring-violet-100">
                    <div className="flex items-center justify-between">
                      <p className="font-semibold text-primary-900 capitalize text-lg">
                        {user?.subscription_tier || "Free"} Plan
                      </p>
                      <Button variant="outline" size="sm">Upgrade</Button>
                    </div>
                    <div className="mt-3">
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-600">Token usage</span>
                        <span className="font-medium">{user?.tokens_used_this_month?.toLocaleString() || 0} / {user?.monthly_token_limit?.toLocaleString() || 0}</span>
                      </div>
                      <div className="h-2 bg-violet-200 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full"
                          style={{ width: `${Math.min(((user?.tokens_used_this_month || 0) / (user?.monthly_token_limit || 1)) * 100, 100)}%` }}
                        />
                      </div>
                    </div>
                  </div>
                </div>
                <Button>Save Changes</Button>
              </CardContent>
            </Card>
          )}

          {activeTab === "notifications" && (
            <Card>
              <CardHeader>
                <CardTitle>Notification Preferences</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Email Notifications</p>
                    <p className="text-sm text-gray-500">Receive weekly visibility reports</p>
                  </div>
                  <input type="checkbox" defaultChecked className="h-4 w-4" />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Drift Alerts</p>
                    <p className="text-sm text-gray-500">Get notified when visibility changes significantly</p>
                  </div>
                  <input type="checkbox" defaultChecked className="h-4 w-4" />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">New Recommendations</p>
                    <p className="text-sm text-gray-500">Receive alerts for new GEO recommendations</p>
                  </div>
                  <input type="checkbox" className="h-4 w-4" />
                </div>
                <Button>Save Preferences</Button>
              </CardContent>
            </Card>
          )}

          {activeTab === "api-keys" && (
            <Card>
              <CardHeader>
                <CardTitle>API Keys (BYOK)</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-gray-600">
                  Bring your own API keys for LLM providers. Your keys are encrypted and stored securely.
                </p>

                {keysLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-primary-500" />
                  </div>
                ) : (
                  <div className="space-y-4">
                    {["openai", "anthropic", "google", "perplexity"].map((provider) => {
                      const savedKey = getKeyStatus(provider);
                      const isSaving = savingProvider === provider;
                      const isSuccess = saveSuccess === provider;
                      const isError = saveError === provider;

                      return (
                        <div
                          key={provider}
                          className={`p-4 bg-gradient-to-r from-gray-50 to-white rounded-xl ring-1 transition-all ${
                            isSuccess ? "ring-success-300 bg-success-50" :
                            isError ? "ring-danger-300 bg-danger-50" :
                            "ring-gray-100 hover:ring-primary-200"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-3">
                            <p className="font-semibold text-gray-900">{providerDisplayNames[provider]}</p>
                            {savedKey ? (
                              <span className="text-xs px-2.5 py-1 bg-success-100 text-success-700 rounded-full font-medium flex items-center gap-1">
                                <Check className="h-3 w-3" />
                                Configured ({savedKey.masked_key})
                              </span>
                            ) : (
                              <span className="text-xs px-2.5 py-1 bg-warning-100 text-warning-700 rounded-full font-medium">
                                Not configured
                              </span>
                            )}
                          </div>
                          <div className="flex gap-2">
                            <div className="relative flex-1">
                              <input
                                type={showKeys[provider] ? "text" : "password"}
                                placeholder={savedKey ? "Enter new key to update" : `Enter your ${providerDisplayNames[provider]} API key`}
                                value={apiKeys[provider]}
                                onChange={(e) => setApiKeys((prev) => ({ ...prev, [provider]: e.target.value }))}
                                className="input w-full pr-10"
                              />
                              <button
                                type="button"
                                onClick={() => setShowKeys((prev) => ({ ...prev, [provider]: !prev[provider] }))}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                              >
                                {showKeys[provider] ? (
                                  <EyeOff className="h-4 w-4" />
                                ) : (
                                  <Eye className="h-4 w-4" />
                                )}
                              </button>
                            </div>
                            <Button
                              onClick={() => handleSaveKey(provider)}
                              disabled={!apiKeys[provider].trim() || isSaving}
                              size="sm"
                            >
                              {isSaving ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : isSuccess ? (
                                <Check className="h-4 w-4" />
                              ) : (
                                "Save"
                              )}
                            </Button>
                          </div>
                          {isSuccess && (
                            <p className="text-xs text-success-600 mt-2 flex items-center gap-1">
                              <Check className="h-3 w-3" />
                              API key saved successfully!
                            </p>
                          )}
                          {isError && (
                            <p className="text-xs text-danger-600 mt-2 flex items-center gap-1">
                              <X className="h-3 w-3" />
                              Failed to save API key. Please try again.
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {activeTab === "security" && (
            <Card>
              <CardHeader>
                <CardTitle>Security Settings</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                <div>
                  <h3 className="font-medium mb-2">Change Password</h3>
                  <div className="space-y-3">
                    <input
                      type="password"
                      placeholder="Current password"
                      className="input w-full"
                    />
                    <input
                      type="password"
                      placeholder="New password"
                      className="input w-full"
                    />
                    <input
                      type="password"
                      placeholder="Confirm new password"
                      className="input w-full"
                    />
                    <Button>Update Password</Button>
                  </div>
                </div>

                <div className="border-t pt-6">
                  <h3 className="font-medium mb-2">Two-Factor Authentication</h3>
                  <p className="text-sm text-gray-500 mb-3">
                    Add an extra layer of security to your account
                  </p>
                  <Button variant="outline">Enable 2FA</Button>
                </div>

                <div className="border-t pt-6">
                  <h3 className="font-medium text-danger-600 mb-2">Danger Zone</h3>
                  <p className="text-sm text-gray-500 mb-3">
                    Permanently delete your account and all associated data
                  </p>
                  <Button variant="outline" className="border-danger-300 text-danger-600 hover:bg-danger-50">
                    Delete Account
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
