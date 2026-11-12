"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { FolderHeart, Plus, Lock, Globe, Sparkles, Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { CollectionSummary } from "@/lib/types";

export default function CollectionsPage() {
  const { user, isPro, openAuthModal } = useAuth();
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  // New collection modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<"PRIVATE" | "PUBLIC">("PRIVATE");
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchCollections = () => {
    if (!user || !isPro) {
      setLoading(false);
      return;
    }
    setLoading(true);
    api
      .getCollections()
      .then((data) => setCollections(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCollections();
  }, [user, isPro]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setSubmitting(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("title", title.trim());
      if (description.trim()) formData.append("description", description.trim());
      formData.append("visibility", visibility);
      if (coverFile) formData.append("cover_image", coverFile);

      await api.createCollection(formData);
      setShowCreateModal(false);
      setTitle("");
      setDescription("");
      setCoverFile(null);
      fetchCollections();
    } catch (err: any) {
      setError(err.message || "Failed to create collection");
    } finally {
      setSubmitting(false);
    }
  };

  if (!user) {
    return (
      <div className="readable-interface max-w-md mx-auto py-24 px-4 text-center">
        <FolderHeart className="w-12 h-12 text-gray-400 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-gray-900 mb-2">My Collections</h2>
        <p className="text-xs text-gray-500 mb-6">Sign in to organize prompts and blueprints into custom collections.</p>
        <button
          onClick={() => openAuthModal("login")}
          className="bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs px-6 py-2.5 rounded-xl shadow-sm transition-all"
        >
          Sign In
        </button>
      </div>
    );
  }

  if (!isPro) {
    return (
      <div className="readable-interface max-w-xl mx-auto py-24 px-4 text-center">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center mb-4">
          <Sparkles className="w-7 h-7" />
        </div>
        <h2 className="text-2xl font-extrabold text-gray-900">Pro Feature: Collections</h2>
        <p className="text-xs text-gray-600 mt-2 max-w-md mx-auto leading-relaxed">
          Creating and curating private or public blueprint collections requires an active $1/month Pro subscription.
        </p>
        <Link
          href="/dashboard?tab=membership"
          className="mt-6 inline-block bg-amber-500 hover:bg-amber-400 text-gray-950 font-bold text-xs px-7 py-3 rounded-xl shadow-md transition-all"
        >
          Upgrade to Pro ($1 / mo)
        </Link>
      </div>
    );
  }

  return (
    <div className="readable-interface max-w-6xl mx-auto px-4 sm:px-8 py-10">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
            My Blueprint Collections
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Organize blueprints into themed stacks for your team, personal workflows, or public discovery.
          </p>
        </div>

        <button
          onClick={() => setShowCreateModal(true)}
          className="bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs px-5 py-2.5 rounded-xl flex items-center gap-1.5 shadow-sm transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>New Collection</span>
        </button>
      </div>

      {loading ? (
        <div className="py-20 text-center flex flex-col items-center justify-center">
          <Loader2 className="w-8 h-8 text-amber-600 animate-spin mb-2" />
          <p className="text-xs text-gray-500">Loading collections...</p>
        </div>
      ) : collections.length === 0 ? (
        <div className="py-20 text-center bg-gray-50 rounded-2xl border border-gray-200 p-8">
          <FolderHeart className="w-12 h-12 text-gray-400 mx-auto mb-3" />
          <h3 className="text-base font-bold text-gray-900">No collections yet</h3>
          <p className="text-xs text-gray-500 mt-1 max-w-sm mx-auto">
            Create your first collection to group your favorite prompts, agentic skills, and MCP configurations.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="mt-4 bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs px-5 py-2 rounded-lg transition-colors"
          >
            Create Collection
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {collections.map((col) => (
            <Link
              key={col.id}
              href={`/collections/${col.slug}`}
              className="group bg-white rounded-2xl border border-gray-200 overflow-hidden hover:border-amber-500/50 hover:shadow-lg transition-all"
            >
              <div className="h-36 bg-gradient-to-br from-amber-100 via-amber-50 to-amber-100 relative overflow-hidden flex items-center justify-center">
                {col.cover_image_url ? (
                  <img
                    src={col.cover_image_url}
                    alt={col.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                ) : (
                  <FolderHeart className="w-12 h-12 text-amber-400/60" />
                )}
                <span className="absolute top-3 right-3 bg-black/70 text-white font-bold text-[10px] px-2 py-0.5 rounded-full flex items-center gap-1 backdrop-blur-xs">
                  {col.visibility === "PUBLIC" ? <Globe className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
                  <span>{col.visibility}</span>
                </span>
              </div>

              <div className="p-5">
                <h3 className="font-bold text-gray-900 text-base group-hover:text-amber-600 transition-colors line-clamp-1">
                  {col.title}
                </h3>
                <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                  {col.description || "No description provided."}
                </p>
                <div className="mt-4 pt-3 border-t border-gray-100 flex items-center justify-between text-xs font-semibold text-gray-600">
                  <span>{col.item_count} items</span>
                  <span className="text-amber-600 group-hover:translate-x-0.5 transition-transform">View Stack →</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="bg-white rounded-2xl p-6 sm:p-8 max-w-md w-full border border-gray-100 shadow-2xl">
            <h3 className="text-lg font-bold text-gray-900 mb-4">Create New Collection</h3>
            {error && <div className="mb-3 p-2 bg-red-50 text-red-700 text-xs rounded">{error}</div>}
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Title *</label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="e.g. Production SWE Toolchain"
                  className="w-full p-2.5 text-xs border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">Description (optional)</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="What is this collection used for?"
                  className="w-full p-2.5 text-xs border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20 resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Visibility</label>
                  <select
                    value={visibility}
                    onChange={(e) => setVisibility(e.target.value as any)}
                    className="w-full p-2 text-xs border border-gray-300 rounded-lg outline-none"
                  >
                    <option value="PRIVATE">Private</option>
                    <option value="PUBLIC">Public</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-bold text-gray-700 mb-1">Cover Image</label>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(e) => setCoverFile(e.target.files?.[0] || null)}
                    className="text-[11px] text-gray-500 file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-[11px] file:bg-gray-100"
                  />
                </div>
              </div>

              <div className="flex items-center gap-2 pt-2">
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex-1 bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs py-2.5 rounded-lg transition-colors"
                >
                  {submitting ? "Creating..." : "Create Collection"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2.5 border border-gray-300 text-gray-700 font-bold text-xs rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

