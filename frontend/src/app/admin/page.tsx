"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Shield, Users, CreditCard, Globe, Sparkles, Loader2, Search } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

export default function AdminPage() {
  const { user, isAdmin } = useAuth();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<"all" | "subscribed">("all");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");

  const fetchAdminData = () => {
    if (!isAdmin) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api
      .getAdminUsers({
        status: filterStatus,
        page,
        page_size: 50,
      })
      .then((res) => setData(res))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchAdminData();
  }, [isAdmin, filterStatus, page]);

  if (!user || !isAdmin) {
    return (
      <div className="max-w-md mx-auto py-24 px-4 text-center">
        <Shield className="w-12 h-12 text-red-500 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-gray-900 mb-2">Access Denied</h2>
        <p className="text-xs text-gray-500 mb-6">Administrator privileges are required to access this panel.</p>
        <Link
          href="/"
          className="bg-gray-900 text-white font-bold text-xs px-6 py-2.5 rounded-xl"
        >
          Return Home
        </Link>
      </div>
    );
  }

  const filteredUsers = (data?.users || []).filter((u: any) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return (
      u.email.toLowerCase().includes(q) ||
      u.username.toLowerCase().includes(q) ||
      (u.name && u.name.toLowerCase().includes(q))
    );
  });

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-10">
      <div className="flex items-center gap-3 mb-8">
        <div className="w-10 h-10 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center font-bold">
          <Shield className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">Admin Operations Panel</h1>
          <p className="text-xs text-gray-500 mt-0.5">Platform growth telemetry, active subscriptions, and user management.</p>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-gray-500 font-bold uppercase">Total Signed Up</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{data?.total_signed_up?.toLocaleString() || 0}</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center">
            <Sparkles className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-gray-500 font-bold uppercase">Active Subscribers</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{data?.total_subscribed?.toLocaleString() || 0}</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center">
            <CreditCard className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-gray-500 font-bold uppercase">Razorpay (India)</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{data?.razorpay_subscribers?.toLocaleString() || 0}</p>
          </div>
        </div>

        <div className="bg-white p-5 rounded-2xl border border-gray-200 shadow-xs flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center">
            <Globe className="w-6 h-6" />
          </div>
          <div>
            <p className="text-xs text-gray-500 font-bold uppercase">Dodo (Global)</p>
            <p className="text-2xl font-extrabold text-gray-900 mt-0.5">{data?.dodo_subscribers?.toLocaleString() || 0}</p>
          </div>
        </div>
      </div>

      {/* Table filters */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-xs overflow-hidden">
        <div className="p-4 sm:p-5 border-b border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setFilterStatus("all")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                filterStatus === "all" ? "bg-gray-900 text-white" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              All Users
            </button>
            <button
              onClick={() => setFilterStatus("subscribed")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                filterStatus === "subscribed" ? "bg-amber-600 text-white" : "text-gray-600 hover:bg-gray-100"
              }`}
            >
              Pro Subscribers Only
            </button>
          </div>

          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search user email or handle..."
              className="w-full pl-9 pr-3 py-1.5 text-xs border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-purple-500/20"
            />
          </div>
        </div>

        {/* Users Table */}
        {loading ? (
          <div className="py-20 text-center flex flex-col items-center justify-center">
            <Loader2 className="w-6 h-6 text-purple-600 animate-spin mb-2" />
            <p className="text-xs text-gray-500">Querying platform database...</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 text-gray-500 font-bold uppercase tracking-wider text-[10px] border-b border-gray-200">
                <tr>
                  <th className="py-3 px-4">User</th>
                  <th className="py-3 px-4">Tier</th>
                  <th className="py-3 px-4">Country</th>
                  <th className="py-3 px-4">Signup IP</th>
                  <th className="py-3 px-4">Device Fingerprint</th>
                  <th className="py-3 px-4">Subscription</th>
                  <th className="py-3 px-4">Joined Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filteredUsers.map((u: any) => (
                  <tr key={u.id} className="hover:bg-gray-50/80 transition-colors">
                    <td className="py-3 px-4">
                      <p className="font-bold text-gray-900">{u.name || u.username}</p>
                      <p className="text-[11px] text-gray-500">{u.email}</p>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`font-bold px-2 py-0.5 rounded text-[10px] uppercase ${
                          u.tier === "ADMIN"
                            ? "bg-purple-100 text-purple-800"
                            : u.tier === "PRO"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-gray-100 text-gray-600"
                        }`}
                      >
                        {u.tier}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono font-medium">{u.country_code || "US"}</td>
                    <td className="py-3 px-4 font-mono text-gray-600">{u.signup_ip || "127.0.0.1"}</td>
                    <td className="py-3 px-4 font-mono text-[10px] text-gray-400 max-w-[120px] truncate" title={u.device_fingerprint}>
                      {u.device_fingerprint || "none"}
                    </td>
                    <td className="py-3 px-4">
                      {u.subscription_gateway ? (
                        <div>
                          <span className="font-bold text-gray-800 uppercase text-[10px]">
                            {u.subscription_gateway}
                          </span>
                          <span className="block text-[10px] text-amber-600 font-semibold">
                            {u.subscription_status}
                          </span>
                        </div>
                      ) : (
                        <span className="text-gray-400">—</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-gray-500 whitespace-nowrap">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

