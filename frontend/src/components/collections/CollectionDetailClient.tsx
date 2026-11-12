"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { FolderHeart, Lock, Globe, ArrowLeft, Loader2, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { CollectionDetail } from "@/lib/types";
import { AssetCard } from "@/components/assets/AssetCard";
import { useAuth } from "@/context/AuthContext";

/**
 * `initialCollection` is the anonymous, server-rendered view of a public collection, so the
 * items and comparison table exist in the first HTML. The client fetch then layers on private
 * collections and owner-only actions exactly as before.
 */
export default function CollectionDetailClient({
  slug,
  initialCollection,
}: {
  slug: string;
  initialCollection: CollectionDetail | null;
}) {
  const { user } = useAuth();

  const [collection, setCollection] = useState<CollectionDetail | null>(initialCollection);
  const [loading, setLoading] = useState(initialCollection === null);
  const [error, setError] = useState<string | null>(null);

  const fetchDetail = () => {
    api
      .getCollectionDetail(slug)
      .then((data) => { setCollection(data); setError(null); })
      .catch((err) => { if (!collection) setError(err.message || "Failed to load collection"); })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchDetail();
  }, [slug, user?.id]);

  const handleRemoveItem = async (assetId: string) => {
    if (!collection) return;
    try {
      await api.removeItemFromCollection(collection.id, assetId);
      fetchDetail();
    } catch (err: any) {
      alert(err.message || "Failed to remove item");
    }
  };

  if (loading) {
    return (
      <div className="readable-interface py-24 text-center flex flex-col items-center justify-center">
        <Loader2 className="w-8 h-8 text-amber-600 animate-spin mb-2" />
        <p className="text-xs text-gray-500">Loading collection...</p>
      </div>
    );
  }

  if (error || !collection) {
    return (
      <div className="readable-interface max-w-md mx-auto py-24 px-4 text-center">
        <h2 className="text-xl font-bold text-gray-900 mb-2">Collection Not Found</h2>
        <p className="text-xs text-gray-500 mb-6">{error || "This collection is private or does not exist."}</p>
        <Link
          href="/collections"
          className="bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs px-5 py-2.5 rounded-xl shadow-sm transition-all"
        >
          Back to Collections
        </Link>
      </div>
    );
  }

  const isOwner = user && collection.owner && user.id === collection.owner.id;
  const matrix = collection.comparison_matrix ?? [];

  return (
    <div className="readable-interface max-w-6xl mx-auto px-4 sm:px-8 py-10">
      <nav aria-label="Breadcrumb" className="mb-6 flex flex-wrap items-center gap-2 text-xs font-bold text-gray-500">
        <Link href="/" className="hover:text-gray-900">Home</Link>
        <span aria-hidden="true">/</span>
        <Link href="/curated" className="hover:text-gray-900">Curated collections</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page" className="text-gray-900">{collection.title}</span>
      </nav>

      <Link
        href="/collections"
        className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 hover:text-gray-900 mb-6 transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        <span>Back to Collections</span>
      </Link>

      {/* Collection Header */}
      <header className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8 shadow-xs mb-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="bg-amber-100 text-amber-800 text-xs font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1">
                <FolderHeart className="w-3.5 h-3.5" />
                <span>Collection</span>
              </span>
              <span className="bg-gray-100 text-gray-700 text-xs font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1">
                {collection.visibility === "PUBLIC" ? <Globe className="w-3 h-3" /> : <Lock className="w-3 h-3" />}
                <span>{collection.visibility}</span>
              </span>
              <span className="text-xs text-gray-400 font-medium">
                {collection.items.length} items
              </span>
            </div>

            <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight">
              {collection.title}
            </h1>

            {collection.description && (
              <p className="text-xs text-gray-600 mt-2 max-w-2xl leading-relaxed">
                {collection.description}
              </p>
            )}

            <p className="text-xs text-gray-400 mt-3">
              Curated by <strong className="text-gray-700 font-semibold">@{collection.owner?.username}</strong>
            </p>
          </div>

          {collection.cover_image_url && (
            <div className="w-24 h-24 rounded-xl overflow-hidden border border-gray-200 flex-shrink-0">
              <img src={collection.cover_image_url} alt={collection.title} className="w-full h-full object-cover" />
            </div>
          )}
        </div>
      </header>

      {/* Comparison matrix: one table summarising every item, crawlable as plain HTML */}
      {matrix.length > 0 && (
        <section aria-labelledby="matrix-heading" className="mb-8">
          <h2 id="matrix-heading" className="font-bold text-gray-900 text-base mb-3">Comparison of {matrix.length} blueprints in this collection</h2>
          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 text-gray-500">
                <tr>
                  <th scope="col" className="py-2.5 px-4 font-bold">Name</th>
                  <th scope="col" className="py-2.5 px-4 font-bold">Type</th>
                  <th scope="col" className="py-2.5 px-4 font-bold">Primary use case</th>
                  <th scope="col" className="py-2.5 px-4 font-bold">Variables</th>
                  <th scope="col" className="py-2.5 px-4 font-bold">Access</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 text-gray-700">
                {matrix.map((row, i) => {
                  const item = collection.items[i];
                  return (
                    <tr key={row.url}>
                      <th scope="row" className="py-2.5 px-4 font-semibold">
                        {item ? <Link href={`/p/${item.slug}`} className="text-amber-700 hover:underline">{row.name}</Link> : row.name}
                      </th>
                      <td className="py-2.5 px-4">{row.modality.replace(/_/g, " ")}</td>
                      <td className="py-2.5 px-4">{row.use_case || row.category || "—"}</td>
                      <td className="py-2.5 px-4">{row.variables?.length ? row.variables.join(", ") : "None"}</td>
                      <td className="py-2.5 px-4">{row.access}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Collection Items Grid */}
      {collection.items.length === 0 ? (
        <div className="py-20 text-center bg-gray-50 rounded-2xl border border-gray-200 p-8">
          <FolderHeart className="w-10 h-10 text-gray-400 mx-auto mb-2" />
          <h2 className="text-base font-bold text-gray-900">This collection is empty</h2>
          <p className="text-xs text-gray-500 mt-1">
            Browse the registry and click "Add to collection" to add blueprints here.
          </p>
          <Link
            href="/directory"
            className="mt-4 inline-block bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs px-5 py-2 rounded-lg transition-colors"
          >
            Explore Blueprints
          </Link>
        </div>
      ) : (
        <section aria-labelledby="items-heading">
          <h2 id="items-heading" className="sr-only">Blueprints in {collection.title}</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {collection.items.map((asset) => (
              <div key={asset.id} className="relative group/item">
                <AssetCard asset={{ ...asset, id: asset.asset_id }} />
                {isOwner && (
                  <button
                    onClick={() => handleRemoveItem(asset.asset_id)}
                    title="Remove from collection"
                    className="absolute top-2 right-2 bg-red-600 hover:bg-red-700 text-white p-1.5 rounded-lg shadow-md opacity-0 group-hover/item:opacity-100 transition-opacity z-10"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
