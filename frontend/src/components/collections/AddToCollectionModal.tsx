"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { X, FolderHeart, Plus, Check, Sparkles, AlertCircle, Image as ImageIcon } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { CollectionSummary } from "@/lib/types";

interface AddToCollectionModalProps {
  assetId: string;
  assetTitle: string;
  isOpen: boolean;
  onClose: () => void;
}

export function AddToCollectionModal({
  assetId,
  assetTitle,
  isOpen,
  onClose,
}: AddToCollectionModalProps) {
  const { user, isPro, openAuthModal } = useAuth();
  const [collections, setCollections] = useState<CollectionSummary[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [selectedColId, setSelectedColId] = useState<string>("");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // New collection form state
  const [isCreatingNew, setIsCreatingNew] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newVisibility, setNewVisibility] = useState<"PRIVATE" | "PUBLIC">("PRIVATE");
  const [newCoverFile, setNewCoverFile] = useState<File | null>(null);

  useEffect(() => {
    if (isOpen && user && isPro) {
      setLoading(true);
      setError(null);
      setSuccessMessage(null);
      api
        .getCollections()
        .then((cols) => {
          setCollections(cols);
          if (cols.length > 0) {
            setSelectedColId(cols[0].id);
          }
        })
        .catch((err) => {
          setError(err.message || "Failed to load collections");
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, user, isPro]);

  if (!isOpen) return null;

  const handleAddToExisting = async () => {
    if (!selectedColId) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.addItemToCollection(selectedColId, assetId);
      setSuccessMessage("Added to collection successfully!");
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err: any) {
      setError(err.message || "Failed to add artifact to collection");
    } finally {
      setSubmitting(false);
    }
  };

  const handleCreateAndAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) {
      setError("Collection title is required");
      return;
    }
    setSubmitting(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("title", newTitle.trim());
      if (newDescription.trim()) {
        formData.append("description", newDescription.trim());
      }
      formData.append("visibility", newVisibility);
      if (newCoverFile) {
        formData.append("cover_image", newCoverFile);
      }

      const newCol = await api.createCollection(formData);
      // Immediately add asset to the new collection
      await api.addItemToCollection(newCol.collection_id, assetId);
      setSuccessMessage(`Created "${newCol.title}" and added artifact!`);
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err: any) {
      setError(err.message || "Failed to create collection");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-gray-100 overflow-hidden">
        {/* Top bar */}
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <FolderHeart className="w-5 h-5 text-amber-600" />
            <h3 className="font-bold text-gray-900 text-sm">Add to Collection</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          <p className="text-xs text-gray-500 mb-4 truncate font-medium">
            Artifact: <span className="text-gray-800 font-semibold">{assetTitle}</span>
          </p>

          {!user ? (
            <div className="text-center py-6">
              <p className="text-sm text-gray-700 mb-3">Please sign in to organize blueprints into collections.</p>
              <button
                onClick={() => {
                  onClose();
                  openAuthModal("login");
                }}
                className="bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs px-5 py-2.5 rounded-lg transition-colors shadow-sm"
              >
                Sign In to Promptally
              </button>
            </div>
          ) : !isPro ? (
            <div className="bg-amber-50/70 border border-amber-200 rounded-xl p-5 text-center">
              <div className="w-10 h-10 mx-auto rounded-full bg-amber-100 text-amber-700 flex items-center justify-center mb-3">
                <Sparkles className="w-5 h-5" />
              </div>
              <h4 className="font-bold text-gray-900 text-sm">Pro Subscription Required</h4>
              <p className="text-xs text-gray-600 mt-1 mb-4">
                Creating and managing personal or public blueprint collections requires an active $1/month Pro subscription.
              </p>
              <Link
                href="/dashboard?tab=membership"
                onClick={onClose}
                className="inline-block bg-amber-500 hover:bg-amber-400 text-gray-950 font-bold text-xs px-5 py-2.5 rounded-lg transition-colors shadow-sm"
              >
                Upgrade to Pro ($1 / mo)
              </Link>
            </div>
          ) : (
            <div>
              {error && (
                <div className="mb-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {successMessage && (
                <div className="mb-4 p-3 rounded-lg bg-amber-50 border border-amber-200 text-amber-700 text-xs flex items-center gap-2">
                  <Check className="w-4 h-4 flex-shrink-0" />
                  <span>{successMessage}</span>
                </div>
              )}

              {!isCreatingNew ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1.5">
                      Select Existing Collection
                    </label>
                    {loading ? (
                      <div className="py-4 text-center text-xs text-gray-500">Loading your collections...</div>
                    ) : collections.length === 0 ? (
                      <p className="text-xs text-gray-500 italic py-2">
                        You have not created any collections yet. Click "Create New Collection" below.
                      </p>
                    ) : (
                      <select
                        value={selectedColId}
                        onChange={(e) => setSelectedColId(e.target.value)}
                        className="w-full p-2.5 text-xs border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 font-medium"
                      >
                        {collections.map((col) => (
                          <option key={col.id} value={col.id}>
                            {col.title} ({col.item_count} items) — {col.visibility}
                          </option>
                        ))}
                      </select>
                    )}
                  </div>

                  <div className="flex items-center gap-2 pt-2">
                    {collections.length > 0 && (
                      <button
                        onClick={handleAddToExisting}
                        disabled={submitting || !selectedColId}
                        className="flex-1 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg text-xs shadow-sm transition-all"
                      >
                        {submitting ? "Adding..." : "Add to Selected"}
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => setIsCreatingNew(true)}
                      className="px-4 py-2.5 border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-colors"
                    >
                      <Plus className="w-4 h-4" />
                      <span>New Collection</span>
                    </button>
                  </div>
                </div>
              ) : (
                <form onSubmit={handleCreateAndAdd} className="space-y-3">
                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">
                      Collection Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      required
                      value={newTitle}
                      onChange={(e) => setNewTitle(e.target.value)}
                      placeholder="e.g. Next.js 15 Fullstack Mastery"
                      className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 font-medium"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-gray-700 mb-1">
                      Description (optional)
                    </label>
                    <textarea
                      rows={2}
                      value={newDescription}
                      onChange={(e) => setNewDescription(e.target.value)}
                      placeholder="Brief notes about what this collection contains..."
                      className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 font-medium resize-none"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-semibold text-gray-700 mb-1">
                        Visibility
                      </label>
                      <select
                        value={newVisibility}
                        onChange={(e) => setNewVisibility(e.target.value as any)}
                        className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 font-medium"
                      >
                        <option value="PRIVATE">Private (Only you)</option>
                        <option value="PUBLIC">Public (Publicly indexable)</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-xs font-semibold text-gray-700 mb-1">
                        Cover Image (optional)
                      </label>
                      <input
                        type="file"
                        accept="image/*"
                        onChange={(e) => setNewCoverFile(e.target.files?.[0] || null)}
                        className="text-[11px] text-gray-600 file:mr-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-[11px] file:bg-gray-100 hover:file:bg-gray-200"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-2 pt-3">
                    <button
                      type="submit"
                      disabled={submitting}
                      className="flex-1 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg text-xs shadow-sm transition-all"
                    >
                      {submitting ? "Creating & Adding..." : "Create & Add Artifact"}
                    </button>
                    <button
                      type="button"
                      onClick={() => setIsCreatingNew(false)}
                      className="px-4 py-2.5 border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-lg text-xs font-semibold transition-colors"
                    >
                      Back
                    </button>
                  </div>
                </form>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

