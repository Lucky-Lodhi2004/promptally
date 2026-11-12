"use client";

import React, { useEffect, useMemo, useState, useRef } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import Script from "next/script";
import {
  Copy,
  Check,
  Download,
  FolderHeart,
  Lock,
  Unlock,
  Eye,
  FileText,
  Share2,
  Calendar,
  Sparkles,
  ShieldCheck,
  Loader2,
  ExternalLink,
  Code,
  Tag,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { AssetDetail } from "@/lib/types";
import { useAuth } from "@/context/AuthContext";
import { AddToCollectionModal } from "@/components/collections/AddToCollectionModal";
import { UserAvatar } from "@/components/ui/UserAvatar";

type PreviewMediaItem = {
  url: string;
  kind: "image" | "gif" | "video";
};

export default function AssetDetailView({
  initialAsset,
  overviewContent,
  supplementalContent,
}: {
  initialAsset: AssetDetail;
  overviewContent?: React.ReactNode;
  supplementalContent?: React.ReactNode;
}) {
  const slug = initialAsset.slug;
  const searchParams = useSearchParams();
  const router = useRouter();
  const { user, openAuthModal } = useAuth();

  const [asset, setAsset] = useState<AssetDetail | null>(initialAsset);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [isColModalOpen, setIsColModalOpen] = useState(false);
  const [activeMediaIndex, setActiveMediaIndex] = useState(0);

  const previewMedia = useMemo(() => {
    if (!asset) return [];

    let candidates: PreviewMediaItem[];
    if (asset.preview_media?.length) {
      candidates = asset.preview_media;
    } else {
      candidates = [];
      if (asset.media_preview_url) {
        candidates.push({ url: asset.media_preview_url, kind: "image" });
      }
      if (asset.gif_preview_url) {
        candidates.push({ url: asset.gif_preview_url, kind: "gif" });
      }
      for (const url of asset.reference_media || []) {
        candidates.push({
          url,
          kind: url.toLowerCase().split("?", 1)[0].endsWith(".gif") ? "gif" : "image",
        });
      }
    }

    return candidates.filter(
      (item, index, all) => item.url && all.findIndex((candidate) => candidate.url === item.url) === index,
    );
  }, [asset]);

  const activeMedia = previewMedia[activeMediaIndex] || previewMedia[0];

  useEffect(() => {
    setActiveMediaIndex(0);
  }, [asset?.id]);

  const moveMedia = (direction: number) => {
    setActiveMediaIndex((current) =>
      (current + direction + previewMedia.length) % previewMedia.length,
    );
  };

  // Variables Playground
  const [variableValues, setVariableValues] = useState<Record<string, string>>(Object.fromEntries((initialAsset.variables_schema || []).map(v => [v.name, v.default_value || v.default || v.example || ""])));
  const [interpolatedContent, setInterpolatedContent] = useState(initialAsset.prefilled_preview_text || initialAsset.raw_content || "");

  // Direct checkout state
  const [buying, setBuying] = useState(false);
  const [buyError, setBuyError] = useState<string | null>(null);

  // The page itself is served from the shared public cache; this client fetch layers on
  // the viewer's own access (owner/buyer) and counts exactly one view per page load.
  const viewCounted = useRef(false);

  const fetchAsset = async (countView = false) => {
    try {
      if (!asset) setLoading(true);
      setError(null);
      const data = await api.getAssetDetail(slug, countView);
      setAsset(data);

      // Initialize variables
      const initialVars: Record<string, string> = {};
      (data.variables_schema || []).forEach((v) => {
        initialVars[v.name] = v.default_value || v.default || v.example || "";
      });
      setVariableValues(initialVars);
      setInterpolatedContent(data.prefilled_preview_text || data.raw_content || "");
    } catch (err: any) {
      setError(err.message || "Failed to load blueprint");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const countView = !viewCounted.current;
    viewCounted.current = true;
    fetchAsset(countView);
  }, [slug, user?.id]);

  // Update live preview when variable inputs change
  const handleVariableChange = (name: string, value: string) => {
    const updated = { ...variableValues, [name]: value };
    setVariableValues(updated);

    if (asset?.raw_content) {
      let text = asset.raw_content;
      Object.entries(updated).forEach(([k, v]) => {
        const regex = new RegExp(`\\{\\{\\s*${k}\\s*\\}\\}`, "g");
        text = text.replace(regex, v || `{{${k}}}`);
      });
      setInterpolatedContent(text);
    }
  };

  const handleCopy = async () => {
    try {
      const textToCopy = interpolatedContent || asset?.prefilled_preview_text || asset?.raw_content || "";
      await api.copyAsset(slug);
      await navigator.clipboard.writeText(textToCopy);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      setBuyError(error instanceof Error ? error.message : "Copy failed");
    }
  };

  const handleDownload = async () => {
    try { await api.downloadAsset(slug); }
    catch (error) { setBuyError(error instanceof Error ? error.message : "Download failed"); }
  };

  const [paymentStatus, setPaymentStatus] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);
  const pollingRun = useRef(0);
  const pendingCheckout = useRef<{userId: string; reference: string} | null>(null);

  const startPaymentPolling = async () => {
    const run = ++pollingRun.current;
    setPolling(true);
    setPaymentStatus("Waiting for payment confirmation…");
    try {
      const storageKey = `promptally-checkout:${user?.id}:${slug}`;
      const reference = (pendingCheckout.current?.userId === user?.id ? pendingCheckout.current?.reference : null)
        || searchParams.get("checkout_reference") || sessionStorage.getItem(storageKey);
      for (let attempt = 0; attempt < 12 && run === pollingRun.current; attempt++) {
        // Provider reconciliation supplements webhooks within the shared request budget.
        if (reference && attempt % 3 === 0) {
          try {
            const result = await api.verifyPurchase(slug, {payment_reference: reference});
            if (result.status === "failed") {
              setPaymentStatus(null);
              setBuyError("Payment failed. You can start a new checkout with another test card or payment method.");
              sessionStorage.removeItem(storageKey);
              pendingCheckout.current = null;
              return;
            }
          } catch (error) {
            if (error instanceof ApiError && error.status === 429) {
              await new Promise(resolve => setTimeout(resolve, Math.max(20, error.retryAfter) * 1000));
              continue;
            }
            // A temporary provider error must not suppress access granted by
            // an independently delivered webhook.
          }
        }
        const confirmed = await api.getAssetDetail(slug);
        if (run !== pollingRun.current) return;
        setAsset(confirmed);
        if (confirmed.has_access) {
          sessionStorage.removeItem(storageKey);
          pendingCheckout.current = null;
          setInterpolatedContent(confirmed.prefilled_preview_text || confirmed.raw_content || "");
          setPaymentStatus("Payment confirmed. Your artifact is unlocked.");
          return;
        }
        await new Promise(resolve => setTimeout(resolve, 20000));
      }
      if (run === pollingRun.current) setPaymentStatus("Confirmation is still pending. Check again shortly; do not pay again.");
    } catch (error) {
      if (run === pollingRun.current) setPaymentStatus(error instanceof Error ? error.message : "Could not check payment status");
    } finally {
      if (run === pollingRun.current) setPolling(false);
    }
  };

  useEffect(() => {
    if (searchParams.get("payment") === "pending" && user) startPaymentPolling();
    return () => { pollingRun.current++; };
  }, [slug, user?.id, searchParams]);

  // Direct-to-Seller Checkout
  const handleDirectBuy = async () => {
    if (polling) return;
    if (!user) {
      openAuthModal("login");
      return;
    }
    setBuying(true);
    setBuyError(null);

    try {
      const res = await api.buyAssetDirect(slug);

      if (res.status === "completed") {
        // Already purchased, refresh to view unlocked payload
        await fetchAsset();
        return;
      }
      pendingCheckout.current = {userId: user.id, reference: res.payment_reference};
      sessionStorage.setItem(`promptally-checkout:${user.id}:${slug}`, res.payment_reference);

      if (res.gateway === "razorpay" && res.key_id && res.order_id) {
        // Open Razorpay Standard Checkout modal for Indian buyers in INR
        const options = {
          key: res.key_id,
          amount: res.amount,
          currency: res.currency,
          name: "Promptally Direct Marketplace",
          description: `Direct purchase of ${asset?.seo_title} (100% to seller @${res.seller_username})`,
          order_id: res.order_id,
          handler: async function (payment: {razorpay_payment_id: string; razorpay_signature: string}) {
            try {
              await api.verifyPurchase(slug, {payment_reference: res.payment_reference,
                payment_id: payment.razorpay_payment_id, signature: payment.razorpay_signature});
            } catch {
              // An interrupted response does not imply an unpaid order. Retry
              // server reconciliation and allow webhook confirmation to arrive.
            }
            await startPaymentPolling();
          },
          prefill: {
            name: user.name || user.username,
            email: user.email,
          },
          theme: {
            color: "#ea580c",
          },
        };

        if ((window as any).Razorpay) {
          const rzp = new (window as any).Razorpay(options);
          rzp.open();
        } else {
          setBuyError("Payment SDK loading. Please retry in a moment.");
        }
      } else if (res.checkout_url) {
        // Dodo Payments hosted session redirect for Foreign buyers in USD
        window.location.href = res.checkout_url;
      } else {
        setBuyError("Could not initialize seller checkout session.");
      }
    } catch (err: any) {
      setBuyError(err.message || "Failed to initiate direct seller checkout.");
    } finally {
      setBuying(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center">
        <Loader2 className="w-8 h-8 text-amber-600 animate-spin mb-3" />
        <p className="text-xs font-semibold text-gray-500">Loading verified blueprint details...</p>
      </div>
    );
  }

  if (error || !asset) {
    return (
      <div className="max-w-2xl mx-auto py-20 px-4 text-center">
        <h2 className="text-xl font-bold text-gray-900 mb-2">Blueprint Not Found</h2>
        <p className="text-xs text-gray-600 mb-6">{error || "The requested artifact could not be found."}</p>
        <Link
          href="/directory"
          className="bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs px-5 py-2.5 rounded-lg transition-colors shadow-sm"
        >
          Return to Registry
        </Link>
      </div>
    );
  }

  return (
    <>
      {/* Razorpay script for Indian checkout */}
      <Script src="https://checkout.razorpay.com/v1/checkout.js" strategy="lazyOnload" />

      {buyError && asset.has_access && <p role="alert" className="mx-auto max-w-4xl p-3 text-red-700">{buyError}</p>}
      <div className="asset-detail-readable max-w-[1400px] mx-auto px-4 sm:px-8 py-8">
        {/* Breadcrumbs (crawlable anchors; mirrors the BreadcrumbList JSON-LD) */}
        <nav aria-label="Breadcrumb" className="flex items-center space-x-2 text-xs text-gray-500 mb-6 flex-wrap">
          <Link href="/" className="hover:text-gray-900 font-medium">Home</Link>
          <span aria-hidden="true">/</span>
          {asset.section && (
            <>
              <Link href={`/directory/${asset.section.slug}`} className="hover:text-gray-900 font-medium">
                {asset.section.name}
              </Link>
              <span aria-hidden="true">/</span>
            </>
          )}
          {asset.section && asset.category && (
            <>
              <Link
                href={`/directory/${asset.section.slug}/${asset.category.slug}`}
                className="hover:text-gray-900 font-medium"
              >
                {asset.category.name}
              </Link>
              <span aria-hidden="true">/</span>
            </>
          )}
          <span aria-current="page" className="text-gray-900 font-bold truncate max-w-xs">{asset.seo_title}</span>
        </nav>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Left Column (2 Cols) */}
          <article className="lg:col-span-2 space-y-8">
            {overviewContent ?? (
            <>
            {/* Title & Metadata Header */}
            <header>
              <div className="flex items-center gap-2 mb-3">
                <span className="bg-amber-100 text-amber-800 text-xs font-bold px-2.5 py-0.5 rounded-full">
                  {asset.asset_type.replace(/_/g, " ")}
                </span>

                {asset.is_paid ? (
                  <span className="bg-amber-100 text-amber-800 border border-amber-300 text-xs font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1">
                    <Lock className="w-3 h-3 text-amber-700" />
                    <span>${asset.price_usd.toFixed(2)} USD</span>
                  </span>
                ) : (
                  <span className="bg-gray-100 text-gray-800 text-xs font-bold px-2.5 py-0.5 rounded-full flex items-center gap-1">
                    <Unlock className="w-3 h-3 text-gray-600" />
                    <span>Free Blueprint</span>
                  </span>
                )}

                <span className="text-xs text-gray-500 font-medium ml-auto">
                  License: {asset.source_license}
                </span>
              </div>

              <h1 className="text-2xl sm:text-3xl font-extrabold text-gray-900 tracking-tight leading-tight">
                {asset.seo_title}
              </h1>

              {/* Atomic citation block: a self-contained answer for snippet and RAG extractors. */}
              <p data-aeo="citation-summary" className="text-sm text-gray-600 mt-3 leading-relaxed">
                {asset.tldr_summary || asset.short_description}
              </p>

              {/* Author & Stats strip */}
              <div className="flex flex-wrap items-center justify-between gap-4 mt-5 pt-4 border-t border-gray-100 text-xs text-gray-500">
                <div className="flex items-center gap-2.5">
                  <UserAvatar
                    src={asset.author?.avatar_url}
                    alt={asset.author?.username || "Promptally user"}
                    className="h-7 w-7 border border-gray-300"
                  />
                  <div>
                    <span className="text-gray-400">Created by </span>
                    <span className="font-bold text-gray-900">@{asset.author?.username || "promptally"}</span>
                  </div>
                </div>

                <div className="flex items-center gap-4 text-xs font-medium text-gray-500">
                  <span className="flex items-center gap-1">
                    <Eye className="w-3.5 h-3.5" />
                    <span>{asset.view_count.toLocaleString()} views</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <Copy className="w-3.5 h-3.5" />
                    <span>{asset.copy_count.toLocaleString()} copies</span>
                  </span>
                  <span className="flex items-center gap-1">
                    <Download className="w-3.5 h-3.5" />
                    <span>{asset.download_count.toLocaleString()} downloads</span>
                  </span>
                </div>
              </div>
            </header>

            {/* Specifications: native table so extractors keep the key/value pairs */}
            <section aria-labelledby="specs-heading">
              <h2 id="specs-heading" className="font-bold text-gray-900 text-base mb-3">Technical Specifications</h2>
              <div className="overflow-x-auto rounded-xl border border-gray-200">
                <table className="w-full text-left text-xs">
                  <thead className="bg-gray-50 text-gray-500">
                    <tr><th scope="col" className="py-2.5 px-4 font-bold">Attribute</th><th scope="col" className="py-2.5 px-4 font-bold">Value</th></tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 text-gray-700">
                    <tr><th scope="row" className="py-2.5 px-4 font-semibold">Artifact type</th><td className="py-2.5 px-4">{asset.asset_type.replace(/_/g, " ")}{asset.category ? ` (${asset.category.name})` : ""}</td></tr>
                    <tr><th scope="row" className="py-2.5 px-4 font-semibold">Compatible models</th><td className="py-2.5 px-4">Universal / Model Agnostic</td></tr>
                    <tr><th scope="row" className="py-2.5 px-4 font-semibold">Dynamic variables</th><td className="py-2.5 px-4">{asset.variables_schema?.length ? asset.variables_schema.map((v) => v.name).join(", ") : "None (static blueprint)"}</td></tr>
                    <tr><th scope="row" className="py-2.5 px-4 font-semibold">Approx. token length</th><td className="py-2.5 px-4">{asset.token_count.toLocaleString()}</td></tr>
                    <tr><th scope="row" className="py-2.5 px-4 font-semibold">File</th><td className="py-2.5 px-4 font-mono">{asset.file_name}</td></tr>
                    <tr><th scope="row" className="py-2.5 px-4 font-semibold">License</th><td className="py-2.5 px-4">{asset.source_license}</td></tr>
                    <tr><th scope="row" className="py-2.5 px-4 font-semibold">Access</th><td className="py-2.5 px-4">{asset.is_paid ? `Creator marketplace ($${asset.price_usd.toFixed(2)} USD)` : "Free public registry (no login required)"}</td></tr>
                    <tr><th scope="row" className="py-2.5 px-4 font-semibold">Author</th><td className="py-2.5 px-4">@{asset.author?.username || "promptally"}</td></tr>
                  </tbody>
                </table>
              </div>
            </section>
            </>
            )}

            {/* Media Gallery (Image / GIF if available) */}
            {activeMedia && (
              <div className="mx-auto w-full max-w-3xl bg-gray-100 rounded-2xl overflow-hidden border border-gray-200">
                <div className="p-3 bg-white border-b border-gray-200 flex items-center justify-between">
                  <span className="text-xs font-bold text-gray-800">Visual Artifact Preview</span>
                  <span className="bg-black/80 text-white font-extrabold text-[9px] px-2 py-0.5 rounded tracking-wider">
                    {activeMedia.kind === "gif" ? "ANIMATED GIF" : activeMedia.kind.toUpperCase()}
                  </span>
                </div>
                <div
                  className="relative flex h-[260px] sm:h-[340px] items-center justify-center overflow-hidden bg-gray-950"
                  tabIndex={previewMedia.length > 1 ? 0 : undefined}
                  onKeyDown={(event) => {
                    if (event.key === "ArrowLeft") moveMedia(-1);
                    if (event.key === "ArrowRight") moveMedia(1);
                  }}
                  aria-label={`Preview ${activeMediaIndex + 1} of ${previewMedia.length}`}
                >
                  {activeMedia.kind === "video" ? (
                    <video
                      key={activeMedia.url}
                      src={activeMedia.url}
                      controls
                      className="h-full w-full object-contain"
                    />
                  ) : (
                    <img
                      key={activeMedia.url}
                      src={activeMedia.url}
                      alt={`${asset.seo_title} preview ${activeMediaIndex + 1}`}
                      className="h-full w-full object-contain"
                    />
                  )}

                  {previewMedia.length > 1 && (
                    <>
                      <button
                        type="button"
                        onClick={() => moveMedia(-1)}
                        className="absolute left-3 top-1/2 -translate-y-1/2 rounded-full bg-white/95 p-2 text-gray-900 shadow-lg transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500"
                        aria-label="Show previous preview"
                      >
                        <ChevronLeft className="h-5 w-5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => moveMedia(1)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full bg-white/95 p-2 text-gray-900 shadow-lg transition hover:bg-white focus:outline-none focus:ring-2 focus:ring-amber-500"
                        aria-label="Show next preview"
                      >
                        <ChevronRight className="h-5 w-5" />
                      </button>
                      <div className="absolute bottom-3 left-1/2 flex -translate-x-1/2 items-center gap-1.5 rounded-full bg-black/65 px-3 py-1.5 text-xs font-semibold text-white">
                        {previewMedia.map((media, index) => (
                          <button
                            key={`${media.url}-${index}`}
                            type="button"
                            onClick={() => setActiveMediaIndex(index)}
                            className={`h-2 w-2 rounded-full transition ${index === activeMediaIndex ? "bg-white" : "bg-white/45 hover:bg-white/75"}`}
                            aria-label={`Show preview ${index + 1}`}
                            aria-current={index === activeMediaIndex ? "true" : undefined}
                          />
                        ))}
                        <span className="ml-1 tabular-nums">{activeMediaIndex + 1}/{previewMedia.length}</span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}

            {/* Dynamic Variables Form (If template contains {{variables}}) */}
            {asset.variables_schema && asset.variables_schema.length > 0 && asset.has_access && (
              <div className="bg-amber-50/60 rounded-2xl p-5 border border-amber-200/80">
                <div className="flex items-center gap-2 mb-3">
                  <Sparkles className="w-4 h-4 text-amber-600" />
                  <h2 className="font-bold text-gray-900 text-sm">Interactive Variables Playground</h2>
                </div>
                <p className="text-xs text-gray-600 mb-4">
                  Customize the dynamic variables below to test real-time interpolation before copying.
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {asset.variables_schema.map((v) => (
                    <div key={v.name}>
                      <label className="block text-xs font-semibold text-gray-700 mb-1">
                        {`{{${v.name}}}`}
                      </label>
                      <input
                        type="text"
                        value={variableValues[v.name] || ""}
                        onChange={(e) => handleVariableChange(v.name, e.target.value)}
                        placeholder={v.default_value || v.default || v.example || `Enter ${v.name}...`}
                        className="w-full px-3 py-2 text-xs bg-white border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500 font-mono"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Content Payload / Paywall Box */}
            <section aria-labelledby="payload-heading">
            <h2 id="payload-heading" className="font-bold text-gray-900 text-base mb-3">
              {asset.has_access ? "Pre-Filled Template" : "Protected Blueprint Preview"}
            </h2>
            <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-xs">
              <div className="px-5 py-3.5 bg-gray-50/80 border-b border-gray-200 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <FileText className="w-4 h-4 text-gray-500" />
                  <span className="font-mono text-xs font-bold text-gray-800">
                    {asset.file_name || `${asset.slug}${asset.file_extension || ".txt"}`}
                  </span>
                </div>

                {asset.has_access && (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleCopy}
                      className="bg-white hover:bg-gray-100 text-gray-700 border border-gray-200 text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors shadow-xs"
                    >
                      {copied ? <Check className="w-3.5 h-3.5 text-amber-600" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copied ? "Copied!" : "Copy Raw"}</span>
                    </button>

                    <button
                      onClick={handleDownload}
                      className="bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold px-3 py-1.5 rounded-lg flex items-center gap-1.5 transition-colors shadow-xs"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>Download</span>
                    </button>
                  </div>
                )}
              </div>

              {/* Body */}
              <div className="relative p-5">
                {asset.has_access ? (
                  <pre className="font-mono text-xs text-gray-800 whitespace-pre-wrap break-words leading-relaxed select-all max-h-[600px] overflow-y-auto">
                    {interpolatedContent || asset.raw_content}
                  </pre>
                ) : (
                  /* Zero-leak paywall overlay */
                  <div data-paywall="locked" className="py-12 px-4 text-center">
                    <div className="w-14 h-14 mx-auto rounded-2xl bg-amber-100 text-amber-700 flex items-center justify-center mb-4 shadow-xs">
                      <Lock className="w-7 h-7" />
                    </div>
                    <p className="text-xl font-extrabold text-gray-900">
                      Protected Marketplace Blueprint
                    </p>
                    <p className="text-xs text-gray-600 mt-2 max-w-md mx-auto leading-relaxed">
                      This premium blueprint is sold directly by <strong>@{asset.author?.username}</strong>. 100% of your payment goes directly to the creator.
                    </p>

                    {asset.preview_snippet && (
                      <div className="mt-4 p-4 rounded-xl bg-gray-50 border border-gray-200 max-w-md mx-auto text-left">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400 mb-1">
                          Public Preview Snippet
                        </p>
                        <p className="text-xs text-gray-700 font-mono line-clamp-3">
                          {asset.preview_snippet}
                        </p>
                      </div>
                    )}

                    {paymentStatus && <div role="status" className="mt-4 text-xs text-gray-700">
                      <p>{paymentStatus}</p>
                      <button disabled={polling} onClick={startPaymentPolling} className="mt-2 underline disabled:opacity-50">Check payment status</button>
                    </div>}
                    {buyError && (
                      <div className="mt-4 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs max-w-md mx-auto">
                        {buyError}
                      </div>
                    )}

                    <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-3">
                      <button
                        onClick={handleDirectBuy}
                        disabled={buying || polling || paymentStatus !== null}
                        className="w-full sm:w-auto bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-bold text-sm px-8 py-3 rounded-xl shadow-md shadow-amber-600/20 transition-all flex items-center justify-center gap-2"
                      >
                        {buying ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Lock className="w-4 h-4" />
                        )}
                        <span>Unlock for ${asset.price_usd.toFixed(2)} USD</span>
                      </button>

                      <button
                        onClick={() => setIsColModalOpen(true)}
                        className="w-full sm:w-auto px-5 py-3 border border-gray-300 hover:bg-gray-50 text-gray-700 rounded-xl text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                      >
                        <FolderHeart className="w-4 h-4" />
                        <span>Save to Collection</span>
                      </button>
                    </div>

                    <p className="text-[11px] text-gray-500 mt-4">
                      Indian buyers pay via UPI/Cards in INR (Razorpay). International buyers pay in USD (Dodo Payments).
                    </p>
                  </div>
                )}
              </div>
            </div>
            </section>

            {/* Raw template with {{placeholders}}, next to the pre-filled example above */}
            {asset.has_access && asset.raw_content && asset.variables_schema?.length > 0
              && asset.prefilled_preview_text && asset.prefilled_preview_text !== asset.raw_content && (
              <section aria-labelledby="raw-template-heading">
                <h2 id="raw-template-heading" className="font-bold text-gray-900 text-base mb-3">Raw Template with Variables</h2>
                <pre className="font-mono text-xs bg-gray-50 p-4 rounded-xl border border-gray-200 whitespace-pre-wrap break-words text-gray-700 max-h-[400px] overflow-y-auto"><code>{asset.raw_content}</code></pre>
              </section>
            )}

            {supplementalContent}

            {!supplementalContent && (
            <>
            {/* Example Output / Benchmark trace */}
            {asset.sample_output_markdown && (
              <section aria-labelledby="benchmark-heading" className="bg-white rounded-2xl p-6 border border-gray-200">
                <h2 id="benchmark-heading" className="font-bold text-gray-900 text-base mb-3 flex items-center gap-2">
                  <Code aria-hidden="true" className="w-4 h-4 text-amber-600" />
                  <span>Verified Execution Output &amp; Benchmark</span>
                </h2>
                <pre className="font-mono text-xs bg-gray-50 p-4 rounded-xl border border-gray-200 whitespace-pre-wrap break-words text-gray-700"><code>{asset.sample_output_markdown}</code></pre>
              </section>
            )}

            <section aria-labelledby="how-to-heading">
              <h2 id="how-to-heading" className="font-bold text-gray-900 text-base mb-3">How to use this {asset.asset_type.replace(/_/g, " ").toLowerCase()}</h2>
              <ol className="list-decimal space-y-1.5 pl-5 text-sm text-gray-700 leading-relaxed">
                <li>{asset.is_paid && !asset.has_access ? "Review the public specifications, benchmark output and preview above, then unlock the blueprint from its creator." : "Review the pre-filled example above."}</li>
                {asset.variables_schema?.length > 0 && <li>Replace each variable ({asset.variables_schema.map((v) => `{{${v.name}}}`).join(", ")}) with your own value.</li>}
                <li>Copy the template or download <code>{asset.file_name}</code>, then paste it into your model, IDE or workflow tool.</li>
                <li>Compare your result with the sample output to confirm it behaves as expected.</li>
              </ol>
            </section>

            {asset.faq?.length > 0 && (
              <section aria-labelledby="faq-heading">
                <h2 id="faq-heading" className="font-bold text-gray-900 text-base mb-3">Frequently Asked Questions</h2>
                <div className="space-y-4">
                  {asset.faq.map((item) => (
                    <div key={item.question}>
                      <h3 className="font-semibold text-gray-900 text-sm">{item.question}</h3>
                      <p className="mt-1 text-sm text-gray-600 leading-relaxed">{item.answer}</p>
                    </div>
                  ))}
                </div>
              </section>
            )}
            </>
            )}
          </article>

          {/* Right Sidebar Column (1 Col) */}
          <div className="space-y-6">
            {/* Quick Actions Card */}
            <div className="bg-white rounded-2xl p-6 border border-gray-200 shadow-xs space-y-4">
              <h3 className="font-bold text-gray-900 text-sm">Quick Actions</h3>

              <button
                onClick={() => setIsColModalOpen(true)}
                className="w-full bg-amber-50 hover:bg-amber-100 text-amber-700 font-bold text-xs py-2.5 px-4 rounded-xl transition-colors flex items-center justify-center gap-2 border border-amber-200"
              >
                <FolderHeart className="w-4 h-4 text-amber-600" />
                <span>Add to Collection</span>
              </button>

              {asset.has_access && (
                <>
                  <button
                    onClick={handleCopy}
                    className="w-full bg-gray-900 hover:bg-gray-800 text-white font-bold text-xs py-2.5 px-4 rounded-xl transition-colors flex items-center justify-center gap-2"
                  >
                    {copied ? <Check className="w-4 h-4 text-amber-400" /> : <Copy className="w-4 h-4" />}
                    <span>{copied ? "Copied to Clipboard" : "Copy Prompt Text"}</span>
                  </button>

                  <button
                    onClick={handleDownload}
                    className="w-full bg-white hover:bg-gray-50 text-gray-700 font-bold text-xs py-2.5 px-4 rounded-xl transition-colors flex items-center justify-center gap-2 border border-gray-200"
                  >
                    <Download className="w-4 h-4" />
                    <span>Download Source File</span>
                  </button>
                </>
              )}

              {/* Developer / AI Agent Twin Links */}
              <div className="pt-4 border-t border-gray-100 space-y-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
                  Developer & AI Crawlers
                </p>
                <a
                  href={`/p/${asset.slug}.md`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between text-xs text-gray-600 hover:text-amber-600 py-1 transition-colors"
                >
                  <span className="font-mono">.md Markdown Twin</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
                <a
                  href="/llms.txt"
                  target="_blank"
                  rel="noreferrer"
                  className="flex items-center justify-between text-xs text-gray-600 hover:text-amber-600 py-1 transition-colors"
                >
                  <span className="font-mono">/llms.txt Manifest</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
            </div>

            {/* Related Blueprints Mesh */}
            {asset.related_artifacts && asset.related_artifacts.length > 0 && (
              <aside aria-labelledby="related-heading" className="bg-white rounded-2xl p-6 border border-gray-200 shadow-xs">
                <h2 id="related-heading" className="font-bold text-gray-900 text-sm mb-3">
                  Related {asset.category?.name || asset.section?.name || "Blueprints"}
                </h2>
                <ul className="space-y-1">
                  {asset.related_artifacts.slice(0, 12).map((rel) => (
                    <li key={rel.slug}>
                      <Link
                        href={`/p/${rel.slug}`}
                        className="block p-2 rounded-xl hover:bg-amber-50 border border-transparent hover:border-amber-200 transition-all group"
                      >
                        <span className="block text-xs font-bold text-gray-900 group-hover:text-amber-600 line-clamp-2">
                          {rel.title}
                        </span>
                        {rel.section_slug && (
                          <span className="text-[10px] text-gray-400 uppercase tracking-wider font-semibold">
                            {rel.section_slug}
                          </span>
                        )}
                      </Link>
                    </li>
                  ))}
                </ul>
              </aside>
            )}
          </div>
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

