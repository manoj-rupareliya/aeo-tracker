"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/lib/store";
import {
  Building2, Users, Mail, Plus, Settings, Crown, Shield,
  MoreHorizontal, Trash2, Edit2, Check, X, Copy, ExternalLink
} from "lucide-react";

interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: "owner" | "admin" | "member";
  avatar?: string;
  joinedAt: string;
  lastActive: string;
}

export default function OrganizationPage() {
  const { user } = useAuthStore();
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"admin" | "member">("member");
  const [copied, setCopied] = useState(false);

  // Mock organization data
  const organization = {
    name: user?.full_name ? `${user.full_name.split(" ")[0]}'s Organization` : "My Organization",
    plan: "Pro",
    projectsCount: 3,
    keywordsCount: 47,
    membersCount: 4,
  };

  // Mock team members
  const teamMembers: TeamMember[] = [
    {
      id: "1",
      name: user?.full_name || "You",
      email: user?.email || "you@example.com",
      role: "owner",
      joinedAt: "Jan 2024",
      lastActive: "Now",
    },
    {
      id: "2",
      name: "Rahul Sharma",
      email: "rahul@company.com",
      role: "admin",
      joinedAt: "Feb 2024",
      lastActive: "2 hours ago",
    },
    {
      id: "3",
      name: "Priya Patel",
      email: "priya@company.com",
      role: "member",
      joinedAt: "Mar 2024",
      lastActive: "1 day ago",
    },
    {
      id: "4",
      name: "Amit Kumar",
      email: "amit@company.com",
      role: "member",
      joinedAt: "Mar 2024",
      lastActive: "3 days ago",
    },
  ];

  const getRoleIcon = (role: string) => {
    switch (role) {
      case "owner":
        return <Crown className="w-4 h-4 text-amber-500" />;
      case "admin":
        return <Shield className="w-4 h-4 text-violet-500" />;
      default:
        return <Users className="w-4 h-4 text-gray-400" />;
    }
  };

  const getRoleBadge = (role: string) => {
    switch (role) {
      case "owner":
        return "bg-amber-100 text-amber-700";
      case "admin":
        return "bg-violet-100 text-violet-700";
      default:
        return "bg-gray-100 text-gray-600";
    }
  };

  const handleCopyInviteLink = () => {
    navigator.clipboard.writeText("https://llmscm.com/invite/abc123xyz");
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-4">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg">
            <Building2 className="h-8 w-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{organization.name}</h1>
            <p className="text-gray-500">Manage your organization settings and team members</p>
          </div>
        </div>
        <button className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
          <Settings className="w-4 h-4" />
          Settings
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Plan", value: organization.plan, icon: Crown, color: "text-amber-600" },
          { label: "Projects", value: organization.projectsCount, icon: Building2, color: "text-violet-600" },
          { label: "Keywords", value: organization.keywordsCount, icon: Settings, color: "text-blue-600" },
          { label: "Members", value: organization.membersCount, icon: Users, color: "text-green-600" },
        ].map((stat) => (
          <div key={stat.label} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">{stat.label}</p>
                <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
              </div>
              <stat.icon className={`w-8 h-8 ${stat.color} opacity-20`} />
            </div>
          </div>
        ))}
      </div>

      {/* Team Members */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900">Team Members</h2>
            <p className="text-sm text-gray-500">{teamMembers.length} members in your organization</p>
          </div>
          <button
            onClick={() => setShowInviteModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Invite Member
          </button>
        </div>

        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Member</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Role</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Joined</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Last Active</th>
              <th className="text-right px-6 py-3 text-xs font-semibold text-gray-500 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {teamMembers.map((member) => (
              <tr key={member.id} className="hover:bg-gray-50">
                <td className="px-6 py-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center text-white font-bold">
                      {member.name.charAt(0)}
                    </div>
                    <div>
                      <p className="font-medium text-gray-900">{member.name}</p>
                      <p className="text-sm text-gray-500">{member.email}</p>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${getRoleBadge(member.role)}`}>
                    {getRoleIcon(member.role)}
                    {member.role.charAt(0).toUpperCase() + member.role.slice(1)}
                  </span>
                </td>
                <td className="px-6 py-4 text-sm text-gray-500">{member.joinedAt}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{member.lastActive}</td>
                <td className="px-6 py-4 text-right">
                  {member.role !== "owner" && (
                    <div className="flex items-center justify-end gap-1">
                      <button className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors">
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button className="p-2 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors">
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pending Invites */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="font-bold text-gray-900 mb-4">Pending Invitations</h3>
        <div className="text-center py-8 text-gray-500">
          <Mail className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <p>No pending invitations</p>
        </div>
      </div>

      {/* Invite Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">Invite Team Member</h2>
              <button
                onClick={() => setShowInviteModal(false)}
                className="p-2 hover:bg-gray-100 rounded-lg"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Email Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="colleague@company.com"
                  className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                />
              </div>

              {/* Role Select */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Role
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    onClick={() => setInviteRole("member")}
                    className={`p-3 border rounded-lg text-left transition-colors ${
                      inviteRole === "member"
                        ? "border-violet-500 bg-violet-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Users className="w-4 h-4 text-gray-500" />
                      <span className="font-medium text-gray-900">Member</span>
                    </div>
                    <p className="text-xs text-gray-500">Can view and analyze keywords</p>
                  </button>
                  <button
                    onClick={() => setInviteRole("admin")}
                    className={`p-3 border rounded-lg text-left transition-colors ${
                      inviteRole === "admin"
                        ? "border-violet-500 bg-violet-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <Shield className="w-4 h-4 text-violet-500" />
                      <span className="font-medium text-gray-900">Admin</span>
                    </div>
                    <p className="text-xs text-gray-500">Full access to all features</p>
                  </button>
                </div>
              </div>

              {/* Invite Link */}
              <div className="pt-4 border-t border-gray-100">
                <p className="text-sm text-gray-600 mb-2">Or share invite link</p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    readOnly
                    value="https://llmscm.com/invite/abc123xyz"
                    className="flex-1 px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm text-gray-600"
                  />
                  <button
                    onClick={handleCopyInviteLink}
                    className="px-3 py-2 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
                  >
                    {copied ? (
                      <Check className="w-4 h-4 text-green-500" />
                    ) : (
                      <Copy className="w-4 h-4 text-gray-500" />
                    )}
                  </button>
                </div>
              </div>

              {/* Send Button */}
              <button
                disabled={!inviteEmail}
                className="w-full py-3 bg-violet-600 text-white rounded-lg font-medium hover:bg-violet-700 transition-colors disabled:opacity-50"
              >
                Send Invitation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
