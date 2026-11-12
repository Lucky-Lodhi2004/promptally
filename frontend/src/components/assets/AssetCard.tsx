"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Copy, Check, Download, FolderHeart, Eye, ArrowUpRight } from "lucide-react";
import { AssetCard as AssetCardType } from "@/lib/types";
import { AddToCollectionModal } from "@/components/collections/AddToCollectionModal";
import { api } from "@/lib/api";

interface AssetCardProps {
  asset: AssetCardType;
}

export function AssetCard({ asset }: AssetCardProps) {
  const [actionError, setActionError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isColModalOpen, setIsColModalOpen] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      setActionError(null);
      const text = await api.copyAsset(asset.slug);
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not copy this artifact");
    }
  };

  const handleDownload = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setActionError(null);
    try { await api.downloadAsset(asset.slug); }
    catch (error) { setActionError(error instanceof Error ? error.message : "Download failed"); }
  };

  const handleOpenColModal = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsColModalOpen(true);
  };

  const mediaThumbnail = asset.gif_preview_url || asset.media_preview_url;

  return (
    <>
      <div className="group bg-white rounded-lg border border-[#e2e2e3] hover:border-[#f4b56a] hover:shadow-[0_3px_15px_rgba(0,0,0,0.08)] transition-all duration-200 flex flex-col justify-between overflow-hidden">
        {/* Card Header & Media preview */}
        <div>
          {mediaThumbnail && (
            <div className="relative w-full h-28 bg-gray-100 overflow-hidden border-b border-gray-100">
              <img
                src={mediaThumbnail}
                alt={asset.seo_title}
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                loading="lazy"
              />
              {asset.gif_preview_url && (
                <span className="absolute top-2 right-2 bg-black/70 text-white font-extrabold text-[9px] px-1.5 py-0.5 rounded tracking-wider backdrop-blur-xs">
                  GIF
                </span>
              )}
            </div>
          )}

          <div className="p-3.5">
            {/* Badges strip */}
            <div className="flex items-center justify-between gap-2 mb-2">
              <span className="text-[10px] font-bold text-[#777] uppercase tracking-wider bg-[#f1f1f2] px-2 py-0.5 rounded">
                {asset.asset_type.replace(/_/g, " ")}
              </span>

              {asset.is_paid ? (
                <span className="bg-[#fff3e2] text-[#f28c28] border border-[#f1c38d] text-xs font-bold px-2 py-0.5 rounded flex items-center gap-1">
                  <span>${asset.price_usd.toFixed(2)}</span>
                  <span className="text-[10px] font-medium text-amber-600 uppercase">Paid</span>
                </span>
              ) : (
                <span className="bg-[#eff7f7] text-[#568e8d] text-xs font-bold px-2 py-0.5 rounded">
                  Free
                </span>
              )}
            </div>

            {/* Title */}
            <Link href={`/p/${asset.slug}`} className="block group-hover:text-[#f28c28] transition-colors">
              <h3 className="font-bold text-[#55565a] text-[14px] leading-snug line-clamp-1">
                {asset.seo_title}
              </h3>
            </Link>

            {/* Description */}
            <p className="text-[#77777a] text-xs mt-1.5 line-clamp-1 leading-relaxed">
              {asset.short_description}
            </p>

          </div>
        </div>

        {actionError && <p role="alert" className="px-4 py-2 text-xs text-red-700">{actionError}</p>}
        {/* Footer Actions */}
        <div className="bg-[#fafafa] px-3.5 py-2 border-t border-[#e8e8e8] flex items-center justify-between gap-2">
          <div className="flex items-center gap-1">
            <button
              onClick={handleCopy}
              title="Copy prompt text"
              className="p-1.5 rounded-md hover:bg-white text-gray-600 hover:text-gray-900 border border-transparent hover:border-gray-200 transition-colors flex items-center gap-1 text-xs"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-amber-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline font-medium">{copied ? "Copied" : "Copy"}</span>
            </button>

            <button
              onClick={handleDownload}
              title="Download blueprint archive"
              className="p-1.5 rounded-md hover:bg-white text-gray-600 hover:text-gray-900 border border-transparent hover:border-gray-200 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
            </button>

            <button
              onClick={handleOpenColModal}
              title="Add to collection"
              className="p-1.5 rounded-md hover:bg-white text-gray-600 hover:text-amber-600 border border-transparent hover:border-gray-200 transition-colors"
            >
              <FolderHeart className="w-3.5 h-3.5" />
            </button>
          </div>

          <Link
            href={`/p/${asset.slug}`}
            className="text-xs font-bold text-[#f28c28] hover:text-[#d66f0f] flex items-center gap-1"
          >
            <span>View</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      <AddToCollectionModal
        assetId={asset.id}
        assetTitle={asset.seo_title}
        isOpen={isColModalOpen}
        onClose={() => setIsColModalOpen(false)}
      />
    </>
  );
}

