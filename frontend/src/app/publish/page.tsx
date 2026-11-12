"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import JSZip from "jszip";
import {
  Upload,
  Sparkles,
  DollarSign,
  FileText,
  FolderArchive,
  Image as ImageIcon,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Lock,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { CATEGORIES } from "@/lib/constants";
import { api } from "@/lib/api";
import { SellerGatewayStatus } from "@/lib/types";

const MAX_PREVIEW_SOURCE_BYTES = 15 * 1024 * 1024;

export default function PublishPage() {
  const router = useRouter();
  const { user, isPro, openAuthModal } = useAuth();

  // Mode: Free vs Paid
  const [isPaid, setIsPaid] = useState<boolean>(false);
  const [priceUsd, setPriceUsd] = useState<string>("5.00");
  const [sellerGateways, setSellerGateways] = useState<SellerGatewayStatus | null>(null);
  const [loadingGateways, setLoadingGateways] = useState(false);

  useEffect(() => {
    if (!isPaid || !user) return;
    let active = true;
    setLoadingGateways(true);
    api.getSellerGateways().then(status => { if (active) setSellerGateways(status); })
      .catch(error => { if (active) setError(error.message || "Could not check seller connections"); })
      .finally(() => { if (active) setLoadingGateways(false); });
    return () => { active = false; };
  }, [isPaid, user?.id]);

  // Taxonomy
  const [selectedSection, setSelectedSection] = useState<string>("prompts");
  const [selectedSubcategory, setSelectedSubcategory] = useState<string>("");

  // Metadata
  const [heading, setHeading] = useState<string>("");
  const [description, setDescription] = useState<string>("");

  // Media
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [gifFile, setGifFile] = useState<File | null>(null);

  // Content input mode: "text" | "file" | "folder"
  const [contentMode, setContentMode] = useState<"text" | "file" | "folder">("text");
  const [rawText, setRawText] = useState<string>("");
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [folderFiles, setFolderFiles] = useState<FileList | null>(null);

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successResult, setSuccessResult] = useState<{
    slug: string;
    url: string;
  } | null>(null);

  const currentCategoryConfig =
    CATEGORIES.find((c) => c.slug === selectedSection) || CATEGORIES[0];
  const validSubcategories = currentCategoryConfig.subcategories.filter((s) => s.slug !== "all");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!user) {
      openAuthModal("login");
      return;
    }

    if (isPaid && !isPro) {
      setError("Active $1/month Pro subscription is required to sell paid blueprints.");
      return;
    }
    if (isPaid && (!sellerGateways || !(sellerGateways.razorpay_connected || sellerGateways.dodo_connected))) {
      setError("Connect a payment account below before publishing a paid prompt.");
      return;
    }

    if (isPaid && !imageFile) {
      setError("At least one preview image is mandatory when selling a paid blueprint.");
      return;
    }

    if (!heading.trim()) {
      setError("Heading / Title is required.");
      return;
    }

    const subcategoryToUse = selectedSubcategory || validSubcategories[0]?.slug;
    if (!subcategoryToUse) {
      setError("Please select a subcategory.");
      return;
    }

    setSubmitting(true);

    try {
      const formData = new FormData();
      formData.append("section_slug", selectedSection);
      formData.append("category_slug", subcategoryToUse);
      formData.append("heading", heading.trim());
      if (description.trim()) {
        formData.append("description", description.trim());
      }
      formData.append("is_paid", isPaid ? "true" : "false");
      formData.append("price_usd", isPaid ? priceUsd : "0.0");

      if (imageFile) {
        formData.append("image", imageFile);
      }
      if (gifFile) {
        formData.append("gif", gifFile);
      }

      // Handle Content depending on mode
      if (contentMode === "text") {
        if (!rawText.trim()) {
          throw new Error("Please paste your prompt or configuration text.");
        }
        formData.append("raw_text", rawText.trim());
      } else if (contentMode === "file") {
        if (!singleFile) {
          throw new Error("Please select a file to upload.");
        }
        formData.append("files", singleFile);
      } else if (contentMode === "folder") {
        if (!folderFiles || folderFiles.length === 0) {
          throw new Error("Please select a folder of files.");
        }
        // Client-side zip compression via JSZip
        const zip = new JSZip();
        for (let i = 0; i < folderFiles.length; i++) {
          const file = folderFiles[i];
          const relativePath = file.webkitRelativePath || file.name;
          zip.file(relativePath, file);
        }
        const zipBlob = await zip.generateAsync({ type: "blob" });
        const zipFile = new File([zipBlob], `${heading.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.zip`, {
          type: "application/zip",
        });
        formData.append("files", zipFile);
      }

      const res = await api.uploadAsset(formData);
      setSuccessResult({ slug: res.slug, url: res.url });
    } catch (err: any) {
      setError(err.message || "Failed to publish blueprint.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="readable-interface max-w-4xl mx-auto px-4 sm:px-8 py-10">
      {/* Header */}
      <div className="mb-8 text-center max-w-xl mx-auto">
        <div className="inline-flex items-center gap-1.5 bg-amber-100 text-amber-800 text-xs font-bold px-3 py-1 rounded-full mb-3">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Publish to Promptally Registry</span>
        </div>
        <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">
          Publish or Sell Your Blueprint
        </h1>
        <p className="text-sm text-gray-600 mt-2">
          Share your prompts, agentic skills, and MCP tools with 35,000+ engineers or sell directly to buyers with 0% platform fee.
        </p>
      </div>

      {successResult ? (
        <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center shadow-lg animate-in fade-in">
          <div className="w-16 h-16 rounded-2xl bg-amber-100 text-amber-600 flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900">Blueprint Published Successfully!</h2>
          <p className="text-xs text-gray-600 mt-2 max-w-md mx-auto">
            Your blueprint has been indexed and assigned its canonical intent-driven URL and .md twin.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <Link
              href={successResult.url}
              className="bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs px-6 py-2.5 rounded-xl shadow-sm transition-all"
            >
              View Live Blueprint Page
            </Link>
            <button
              onClick={() => {
                setSuccessResult(null);
                setHeading("");
                setDescription("");
                setRawText("");
              }}
              className="px-5 py-2.5 border border-gray-300 text-gray-700 font-bold text-xs rounded-xl hover:bg-gray-50 transition-colors"
            >
              Publish Another
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8 shadow-sm space-y-6">
          {error && (
            <div className="p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-5 h-5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Mode Switcher: Free vs Paid */}
          <div className="p-1.5 bg-gray-100 rounded-xl grid grid-cols-2 gap-1.5">
            <button
              type="button"
              onClick={() => setIsPaid(false)}
              className={`py-2.5 rounded-lg text-xs font-bold transition-all ${
                !isPaid ? "bg-white text-gray-900 shadow-sm" : "text-gray-600 hover:text-gray-900"
              }`}
            >
              Free Community Blueprint
            </button>
            <button
              type="button"
              onClick={() => setIsPaid(true)}
              className={`py-2.5 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                isPaid ? "bg-amber-600 text-white shadow-sm" : "text-gray-600 hover:text-gray-900"
              }`}
            >
              <DollarSign className="w-3.5 h-3.5" />
              <span>Sell for Direct Payouts (0% Cut)</span>
            </button>
          </div>

          {/* Paid warning if not Pro */}
          {isPaid && !isPro && (
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-900 text-xs flex items-center justify-between gap-4">
              <div>
                <p className="font-bold">Pro Subscription Required to Sell</p>
                <p className="text-amber-700 mt-0.5">
                  Pro subscribers ($1/mo) can connect their Razorpay/Dodo gateways and sell prompts with 0% platform fee.
                </p>
              </div>
              <Link
                href="/dashboard?tab=membership"
                className="bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs px-3.5 py-2 rounded-lg whitespace-nowrap transition-colors"
              >
                Upgrade ($1/mo)
              </Link>
            </div>
          )}

          {/* Price Input (if Paid) */}
          {isPaid && (
            <div className="bg-amber-50/60 p-4 rounded-xl border border-amber-200">
              <p className="text-xs font-semibold mb-2">Choose how buyers can pay you</p>
              <div className="grid sm:grid-cols-2 gap-3 mb-4">
                <Link href="/dashboard?tab=seller-studio#razorpay" className="rounded-lg border border-gray-200 bg-white p-3 text-xs">
                  <strong>Razorpay — Indian buyers</strong>
                  <p className={`mt-1 ${!loadingGateways && sellerGateways?.razorpay_connected ? "font-semibold text-green-700" : ""}`}>
                    {loadingGateways ? "Checking…" : sellerGateways?.razorpay_connected ? "Connected · INR payments" : "Connect your Razorpay account"}
                  </p>
                </Link>
                <Link href="/dashboard?tab=seller-studio#dodo" className="rounded-lg border border-gray-200 bg-white p-3 text-xs">
                  <strong>Dodo — Foreign buyers</strong>
                  <p className={`mt-1 ${!loadingGateways && sellerGateways?.dodo_connected ? "font-semibold text-green-700" : ""}`}>
                    {loadingGateways ? "Checking…" : sellerGateways?.dodo_connected ? "Connected · USD payments" : "Connect with an API key; setup is automatic"}
                  </p>
                </Link>
              </div>
              <p className="text-xs text-gray-600 mb-4">Connect both to sell to both groups. Promptally charges no platform commission; provider fees apply.</p>
              <label className="block text-xs font-bold text-gray-900 mb-1">
                Price in USD ($) <span className="text-red-500">*</span>
              </label>
              <div className="relative max-w-xs">
                <span className="absolute left-3.5 top-2.5 text-sm font-bold text-gray-500">$</span>
                <input
                  type="number"
                  step="0.50"
                  min="0.50"
                  max="500.00"
                  required={isPaid}
                  value={priceUsd}
                  onChange={(e) => setPriceUsd(e.target.value)}
                  className="w-full pl-8 pr-3 py-2 text-sm font-bold text-gray-900 bg-white border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                />
              </div>
              <p className="text-[11px] text-gray-500 mt-1.5">
                Indian buyers pay via Razorpay in INR; foreign buyers pay via Dodo Payments in USD. 100% settles directly to your account.
              </p>
            </div>
          )}

          {/* Classification Selection */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1.5">
                Category <span className="text-red-500">*</span>
              </label>
              <select
                value={selectedSection}
                onChange={(e) => {
                  setSelectedSection(e.target.value);
                  setSelectedSubcategory("");
                }}
                className="w-full p-2.5 text-xs font-semibold bg-white border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.name} ({c.itemCountLabel})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1.5">
                Subcategory <span className="text-red-500">*</span>
              </label>
              <select
                value={selectedSubcategory || validSubcategories[0]?.slug}
                onChange={(e) => setSelectedSubcategory(e.target.value)}
                className="w-full p-2.5 text-xs font-semibold bg-white border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
              >
                {validSubcategories.map((sub) => (
                  <option key={sub.slug} value={sub.slug}>
                    {sub.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Heading */}
          <div>
            <label className="block text-xs font-bold text-gray-700 mb-1.5">
              Blueprint Title / Heading <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              required
              value={heading}
              onChange={(e) => setHeading(e.target.value)}
              placeholder="e.g. Next.js 15 App Router Production Optimization Engine"
              className="w-full p-2.5 text-xs font-medium border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-xs font-bold text-gray-700 mb-1.5">
              Description (optional)
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief summary of what this blueprint accomplishes..."
              className="w-full p-2.5 text-xs font-medium border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 resize-none"
            />
          </div>

          {/* Media Attachments */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 border-t border-gray-100">
            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">
                Preview Image {isPaid ? <span className="text-red-500">(Required for Paid)</span> : <span className="text-gray-400 font-normal">(Optional)</span>}
              </label>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                required={isPaid}
                onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  if (file && file.size > MAX_PREVIEW_SOURCE_BYTES) {
                    setImageFile(null);
                    e.target.value = "";
                    setError("Preview image source must be 15 MiB or smaller. It will be optimized to 5 MiB or less.");
                    return;
                  }
                  setError(null);
                  setImageFile(file);
                }}
                className="w-full text-xs text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-gray-100 hover:file:bg-gray-200"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">
                Animated GIF <span className="text-gray-400 font-normal">(Optional)</span>
              </label>
              <input
                type="file"
                accept="image/gif"
                onChange={(e) => {
                  const file = e.target.files?.[0] || null;
                  if (file && file.size > MAX_PREVIEW_SOURCE_BYTES) {
                    setGifFile(null);
                    e.target.value = "";
                    setError("Animated GIF source must be 15 MiB or smaller. It will be optimized to 10 MiB or less.");
                    return;
                  }
                  setError(null);
                  setGifFile(file);
                }}
                className="w-full text-xs text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-gray-100 hover:file:bg-gray-200"
              />
            </div>
          </div>

          {/* Content Payload Mode */}
          <div className="pt-2 border-t border-gray-100">
            <label className="block text-xs font-bold text-gray-700 mb-2">
              Blueprint Payload Mode <span className="text-red-500">*</span>
            </label>
            <div className="grid grid-cols-3 gap-2 mb-3">
              <button
                type="button"
                onClick={() => setContentMode("text")}
                className={`py-2 px-3 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 border transition-all ${
                  contentMode === "text"
                    ? "bg-gray-900 text-white border-gray-900 shadow-sm"
                    : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>Paste Text</span>
              </button>

              <button
                type="button"
                onClick={() => setContentMode("file")}
                className={`py-2 px-3 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 border transition-all ${
                  contentMode === "file"
                    ? "bg-gray-900 text-white border-gray-900 shadow-sm"
                    : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                }`}
              >
                <Upload className="w-3.5 h-3.5" />
                <span>Single File</span>
              </button>

              <button
                type="button"
                onClick={() => setContentMode("folder")}
                className={`py-2 px-3 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 border transition-all ${
                  contentMode === "folder"
                    ? "bg-gray-900 text-white border-gray-900 shadow-sm"
                    : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                }`}
              >
                <FolderArchive className="w-3.5 h-3.5" />
                <span>Folder (.zip)</span>
              </button>
            </div>

            {contentMode === "text" && (
              <textarea
                rows={8}
                required
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder="Paste prompt template, SKILL.md, mcpServers config, or rule directives with {{variables}}..."
                className="w-full p-3 font-mono text-xs border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 resize-y"
              />
            )}

            {contentMode === "file" && (
              <div className="p-4 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50 text-center">
                <input
                  type="file"
                  required
                  onChange={(e) => setSingleFile(e.target.files?.[0] || null)}
                  className="text-xs text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-gray-200 hover:file:bg-gray-300"
                />
              </div>
            )}

            {contentMode === "folder" && (
              <div className="p-4 border-2 border-dashed border-gray-300 rounded-xl bg-gray-50 text-center space-y-2">
                <p className="text-xs text-gray-600 font-medium">
                  Select a directory. It will be compressed client-side into a .zip archive.
                </p>
                <input
                  type="file"
                  /* @ts-ignore */
                  webkitdirectory=""
                  directory=""
                  required
                  onChange={(e) => setFolderFiles(e.target.files)}
                  className="text-xs text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-gray-200 hover:file:bg-gray-300"
                />
              </div>
            )}
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-bold text-sm py-3 rounded-xl shadow-md transition-all flex items-center justify-center gap-2"
          >
            {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            <span>{submitting ? "Processing & Compiling..." : isPaid ? "Publish Paid Listing" : "Publish Free Blueprint"}</span>
          </button>
        </form>
      )}
    </div>
  );
}

