"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  Shield,
  Users,
  CreditCard,
  Globe,
  Sparkles,
  Loader2,
  Search,
  Layers,
  PlusCircle,
  Trash2,
  ArrowUpToLine,
  ArrowUp,
  ArrowDown,
  PinOff,
  Pin,
  ExternalLink,
  Upload,
  Link2,
  FileText,
  FolderArchive,
  Image as ImageIcon,
  CheckCircle2,
  AlertCircle,
  Ban,
  UserX,
  ChevronLeft,
  ChevronRight,
  X,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { CATEGORIES } from "@/lib/constants";
import type {
  AdminAssetItem,
  AdminAssetsResponse,
  AdminUserCard,
  AdminUsersResponse,
  TaxonomySection,
} from "@/lib/types";

type AdminTab = "artifacts" | "add" | "users";
type MediaMode = "upload" | "cdn";
type ContentMode = "text" | "file" | "folder";

type ConfirmModalState =
  | null
  | {
      kind: "delete-asset";
      asset: AdminAssetItem;
    }
  | {
      kind: "end-subscription";
      targetUser: AdminUserCard;
    }
  | {
      kind: "delete-user";
      targetUser: AdminUserCard;
    };

export default function AdminPage() {
  const { user, loading: authLoading, isAdmin } = useAuth();
  const [activeTab, setActiveTab] = useState<AdminTab>("artifacts");

  // Toast feedback
  const [notice, setNotice] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const showNotice = (type: "success" | "error", text: string) => {
    setNotice({ type, text });
  };

  // Confirmation modal
  const [confirmModal, setConfirmModal] = useState<ConfirmModalState>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);

  // Taxonomy (live from API with static fallback)
  const [taxonomySections, setTaxonomySections] = useState<TaxonomySection[]>([]);

  // Users state
  const [usersData, setUsersData] = useState<AdminUsersResponse | null>(null);
  const [usersLoading, setUsersLoading] = useState(false);
  const [userFilterStatus, setUserFilterStatus] = useState<"all" | "subscribed">("all");
  const [userPage, setUserPage] = useState(1);
  const [userSearchInput, setUserSearchInput] = useState("");
  const [userSearchQuery, setUserSearchQuery] = useState("");

  // Artifacts state
  const [assetsData, setAssetsData] = useState<AdminAssetsResponse | null>(null);
  const [assetsLoading, setAssetsLoading] = useState(false);
  const [assetSection, setAssetSection] = useState<string>("all");
  const [assetSubcategory, setAssetSubcategory] = useState<string>("all");
  const [assetPricing, setAssetPricing] = useState<"all" | "free" | "paid">("all");
  const [assetPinnedOnly, setAssetPinnedOnly] = useState(false);
  const [assetSearchInput, setAssetSearchInput] = useState("");
  const [assetSearchQuery, setAssetSearchQuery] = useState("");
  const [assetPage, setAssetPage] = useState(1);
  const [busyAssetId, setBusyAssetId] = useState<string | null>(null);

  // Add Artifact form state
  const [addSection, setAddSection] = useState<string>("prompts");
  const [addSubcategory, setAddSubcategory] = useState<string>("");
  const [addHeading, setAddHeading] = useState<string>("");
  const [addDescription, setAddDescription] = useState<string>("");
  const [addExampleOutput, setAddExampleOutput] = useState<string>("");
  const [addPinToTop, setAddPinToTop] = useState<boolean>(false);

  // Media mode: CDN URL vs Upload for both Image and GIF
  const [imageMode, setImageMode] = useState<MediaMode>("upload");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string>("");
  const [imageObjectUrl, setImageObjectUrl] = useState<string | null>(null);

  const [gifMode, setGifMode] = useState<MediaMode>("upload");
  const [gifFile, setGifFile] = useState<File | null>(null);
  const [gifUrl, setGifUrl] = useState<string>("");
  const [gifObjectUrl, setGifObjectUrl] = useState<string | null>(null);

  // Content input mode
  const [contentMode, setContentMode] = useState<ContentMode>("text");
  const [rawText, setRawText] = useState<string>("");
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [folderFiles, setFolderFiles] = useState<FileList | null>(null);

  const [creatingAsset, setCreatingAsset] = useState(false);
  const [createdAsset, setCreatedAsset] = useState<{
    slug: string;
    url: string;
    display_priority: number;
  } | null>(null);

  // Preview object URLs cleanup
  useEffect(() => {
    if (!imageFile) {
      setImageObjectUrl(null);
      return;
    }
    const url = URL.createObjectURL(imageFile);
    setImageObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [imageFile]);

  useEffect(() => {
    if (!gifFile) {
      setGifObjectUrl(null);
      return;
    }
    const url = URL.createObjectURL(gifFile);
    setGifObjectUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [gifFile]);

  const sectionOptions = useMemo(() => {
    if (taxonomySections.length > 0) {
      return taxonomySections.map((s) => ({
        slug: s.slug,
        name: s.name,
        subcategories: s.categories
          .filter((c) => c.slug !== "all")
          .map((c) => ({ slug: c.slug, name: c.name })),
      }));
    }
    return CATEGORIES.map((c) => ({
      slug: c.slug,
      name: c.name,
      subcategories: c.subcategories
        .filter((s) => s.slug !== "all")
        .map((s) => ({ slug: s.slug, name: s.name })),
    }));
  }, [taxonomySections]);

  const filterSubcategories = useMemo(() => {
    const match = sectionOptions.find((s) => s.slug === assetSection);
    return match ? match.subcategories : [];
  }, [sectionOptions, assetSection]);

  const addSubcategories = useMemo(() => {
    const match = sectionOptions.find((s) => s.slug === addSection) || sectionOptions[0];
    return match ? match.subcategories : [];
  }, [sectionOptions, addSection]);

  useEffect(() => {
    if (addSubcategories.length > 0 && !addSubcategories.some((s) => s.slug === addSubcategory)) {
      setAddSubcategory(addSubcategories[0].slug);
    }
  }, [addSubcategories, addSubcategory]);

  useEffect(() => {
    if (!isAdmin) return;
    api
      .getTaxonomy()
      .then((res) => setTaxonomySections(res.sections || []))
      .catch(() => {
        /* falls back to static CATEGORIES */
      });
  }, [isAdmin]);

  const fetchUsers = useCallback(async () => {
    if (!isAdmin) return;
    setUsersLoading(true);
    try {
      const res = await api.getAdminUsers({
        status: userFilterStatus,
        q: userSearchQuery,
        page: userPage,
        page_size: 30,
      });
      setUsersData(res);
    } catch (err: any) {
      showNotice("error", err?.message || "Failed to load users.");
    } finally {
      setUsersLoading(false);
    }
  }, [isAdmin, userFilterStatus, userSearchQuery, userPage]);

  const fetchAssets = useCallback(async () => {
    if (!isAdmin) return;
    setAssetsLoading(true);
    try {
      const res = await api.getAdminAssets({
        section: assetSection,
        subcategory: assetSubcategory,
        pricing: assetPricing,
        q: assetSearchQuery,
        pinned_only: assetPinnedOnly,
        page: assetPage,
        page_size: 25,
      });
      setAssetsData(res);
    } catch (err: any) {
      showNotice("error", err?.message || "Failed to load artifacts.");
    } finally {
      setAssetsLoading(false);
    }
  }, [isAdmin, assetSection, assetSubcategory, assetPricing, assetSearchQuery, assetPinnedOnly, assetPage]);

  useEffect(() => {
    if (isAdmin) {
      fetchUsers();
    }
  }, [isAdmin, fetchUsers]);

  useEffect(() => {
    if (isAdmin) {
      fetchAssets();
    }
  }, [isAdmin, fetchAssets]);

  // Artifact ordering actions
  const handleMoveToTop = async (asset: AdminAssetItem) => {
    setBusyAssetId(asset.id);
    setNotice(null);
    try {
      const res = await api.moveAdminAssetToTop(asset.id);
      showNotice("success", `Moved "${asset.seo_title}" to the top (priority #${res.display_priority}).`);
      await fetchAssets();
    } catch (err: any) {
      showNotice("error", err?.message || "Could not move artifact to top.");
    } finally {
      setBusyAssetId(null);
    }
  };

  const handleUnpin = async (asset: AdminAssetItem) => {
    setBusyAssetId(asset.id);
    setNotice(null);
    try {
      await api.setAdminAssetPriority(asset.id, 0);
      showNotice("success", `Unpinned "${asset.seo_title}" back to default ordering.`);
      await fetchAssets();
    } catch (err: any) {
      showNotice("error", err?.message || "Could not unpin artifact.");
    } finally {
      setBusyAssetId(null);
    }
  };

  const handleShiftRelative = async (index: number, direction: -1 | 1) => {
    const items = assetsData?.items || [];
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= items.length) return;

    const current = items[index];
    const neighbor = items[targetIndex];
    setBusyAssetId(current.id);
    setNotice(null);

    try {
      // If both items are pinned, swap just the pair so nothing else shifts.
      // If moving an unpinned item upward, pass the prefix through the moved item
      // so it cleanly slots right into its new position.
      if (current.display_priority > 0 && neighbor.display_priority > 0) {
        const pair = direction === -1 ? [current.id, neighbor.id] : [neighbor.id, current.id];
        await api.reorderAdminAssets(pair);
      } else {
        const reordered = [...items];
        const [moved] = reordered.splice(index, 1);
        reordered.splice(targetIndex, 0, moved);
        const cutoff = Math.max(index, targetIndex) + 1;
        await api.reorderAdminAssets(reordered.slice(0, cutoff).map((item) => item.id));
      }
      await fetchAssets();
      showNotice("success", `Updated position for "${current.seo_title}".`);
    } catch (err: any) {
      showNotice("error", err?.message || "Could not rearrange artifacts.");
    } finally {
      setBusyAssetId(null);
    }
  };

  // Confirmation modal handler
  const handleConfirmAction = async () => {
    if (!confirmModal) return;
    setConfirmBusy(true);
    setNotice(null);
    try {
      if (confirmModal.kind === "delete-asset") {
        const res = await api.deleteAdminAsset(confirmModal.asset.id);
        showNotice("success", res.message || `Deleted "${confirmModal.asset.seo_title}".`);
        setConfirmModal(null);
        await fetchAssets();
      } else if (confirmModal.kind === "end-subscription") {
        const res = await api.endAdminUserSubscription(confirmModal.targetUser.id, true);
        showNotice("success", res.message);
        setConfirmModal(null);
        await fetchUsers();
      } else if (confirmModal.kind === "delete-user") {
        const res = await api.deleteAdminUser(confirmModal.targetUser.id);
        showNotice("success", res.message);
        setConfirmModal(null);
        await Promise.all([fetchUsers(), fetchAssets()]);
      }
    } catch (err: any) {
      showNotice("error", err?.message || "Action failed.");
    } finally {
      setConfirmBusy(false);
    }
  };

  // Add artifact handler (as @promptally)
  const handleCreateArtifact = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotice(null);
    setCreatedAsset(null);

    if (!addHeading.trim()) {
      showNotice("error", "Heading / Title is required.");
      return;
    }
    const subcat = addSubcategory || addSubcategories[0]?.slug;
    if (!subcat) {
      showNotice("error", "Please select a subcategory.");
      return;
    }
    if (contentMode === "text" && !rawText.trim()) {
      showNotice("error", "Please enter the prompt / skill / workflow content.");
      return;
    }
    if (contentMode === "file" && !singleFile) {
      showNotice("error", "Please select a file to upload.");
      return;
    }
    if (contentMode === "folder" && (!folderFiles || folderFiles.length === 0)) {
      showNotice("error", "Please select files or a folder to upload.");
      return;
    }

    setCreatingAsset(true);
    try {
      const formData = new FormData();
      formData.append("section_slug", addSection);
      formData.append("category_slug", subcat);
      formData.append("heading", addHeading.trim());
      if (addDescription.trim()) formData.append("description", addDescription.trim());
      if (addExampleOutput.trim()) formData.append("example_output", addExampleOutput.trim());
      formData.append("pin_to_top", addPinToTop ? "true" : "false");

      if (imageMode === "upload" && imageFile) {
        formData.append("image", imageFile);
      } else if (imageMode === "cdn" && imageUrl.trim()) {
        formData.append("image_url", imageUrl.trim());
      }

      if (gifMode === "upload" && gifFile) {
        formData.append("gif", gifFile);
      } else if (gifMode === "cdn" && gifUrl.trim()) {
        formData.append("gif_url", gifUrl.trim());
      }

      if (contentMode === "text") {
        formData.append("raw_text", rawText.trim());
      } else if (contentMode === "file" && singleFile) {
        formData.append("files", singleFile);
      } else if (contentMode === "folder" && folderFiles) {
        Array.from(folderFiles).forEach((file) => {
          formData.append("files", file);
        });
      }

      const res = await api.createAdminAsset(formData);
      setCreatedAsset({
        slug: res.slug,
        url: res.url,
        display_priority: res.display_priority,
      });
      showNotice("success", `Published "${addHeading.trim()}" as @promptally.`);
      // Reset form fields for quick next entry
      setAddHeading("");
      setAddDescription("");
      setAddExampleOutput("");
      setRawText("");
      setSingleFile(null);
      setFolderFiles(null);
      setImageFile(null);
      setImageUrl("");
      setGifFile(null);
      setGifUrl("");
      setAddPinToTop(false);
      await fetchAssets();
    } catch (err: any) {
      showNotice("error", err?.message || "Failed to publish artifact.");
    } finally {
      setCreatingAsset(false);
    }
  };

  if (authLoading) {
    return (
      <div className="max-w-md mx-auto py-28 px-4 text-center flex flex-col items-center">
        <Loader2 className="w-8 h-8 text-[#f28c28] animate-spin mb-3" />
        <p className="text-xs text-gray-500">Verifying administrator access...</p>
      </div>
    );
  }

  if (!user || !isAdmin) {
    return (
      <div className="max-w-md mx-auto py-24 px-4 text-center">
        <Shield className="w-12 h-12 text-red-500 mx-auto mb-3" />
        <h2 className="text-xl font-bold text-gray-900 mb-2">Access Denied</h2>
        <p className="text-xs text-gray-500 mb-6">
          Administrator privileges are required to access this panel.
        </p>
        <Link
          href="/"
          className="bg-gray-900 text-white font-bold text-xs px-6 py-2.5 rounded-xl"
        >
          Return Home
        </Link>
      </div>
    );
  }

  const activeImagePreview = imageMode === "upload" ? imageObjectUrl : imageUrl.trim() || null;
  const activeGifPreview = gifMode === "upload" ? gifObjectUrl : gifUrl.trim() || null;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-8 py-8 sm:py-10">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-7">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center">
            <Shield className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-gray-900 tracking-tight">
              Admin Operations Panel
            </h1>
            <p className="text-xs text-gray-500 mt-0.5">
              Curate &amp; rearrange registry artifacts, publish official{" "}
              <span className="font-mono font-semibold text-gray-700">@promptally</span> blueprints,
              and manage user subscriptions &amp; accounts.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setActiveTab("add")}
          className="inline-flex items-center justify-center gap-2 bg-[#f28c28] hover:bg-[#d66f0f] text-white font-bold text-xs px-4 py-2.5 rounded-xl shadow-sm transition-colors"
        >
          <PlusCircle className="w-4 h-4" />
          <span>Add @promptally Artifact</span>
        </button>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4 mb-7">
        <div className="bg-white p-4 rounded-2xl border border-gray-200 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-100 text-amber-700 flex items-center justify-center shrink-0">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[10px] text-gray-500 font-bold uppercase">Published</p>
            <p className="text-xl font-extrabold text-gray-900">
              {assetsData?.total_published?.toLocaleString() ?? "—"}
            </p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-gray-200 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-purple-100 text-purple-700 flex items-center justify-center shrink-0">
            <Pin className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[10px] text-gray-500 font-bold uppercase">Pinned Top</p>
            <p className="text-xl font-extrabold text-gray-900">
              {assetsData?.total_pinned?.toLocaleString() ?? "—"}
            </p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-gray-200 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center shrink-0">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[10px] text-gray-500 font-bold uppercase">Total Users</p>
            <p className="text-xl font-extrabold text-gray-900">
              {usersData?.total_signed_up?.toLocaleString() ?? "—"}
            </p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-gray-200 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center shrink-0">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[10px] text-gray-500 font-bold uppercase">Active Pro</p>
            <p className="text-xl font-extrabold text-gray-900">
              {usersData?.total_subscribed?.toLocaleString() ?? "—"}
            </p>
          </div>
        </div>

        <div className="bg-white p-4 rounded-2xl border border-gray-200 flex items-center gap-3 col-span-2 lg:col-span-1">
          <div className="w-10 h-10 rounded-xl bg-gray-100 text-gray-700 flex items-center justify-center shrink-0">
            <Globe className="w-5 h-5" />
          </div>
          <div className="text-[11px] font-semibold text-gray-700">
            <p className="text-[10px] text-gray-500 font-bold uppercase">Gateways</p>
            <p className="mt-0.5">
              RZP: <span className="font-extrabold text-gray-900">{usersData?.razorpay_subscribers ?? 0}</span> · Dodo:{" "}
              <span className="font-extrabold text-gray-900">{usersData?.dodo_subscribers ?? 0}</span>
            </p>
          </div>
        </div>
      </div>

      {/* Feedback Banner */}
      {notice && (
        <div
          role="alert"
          className={`mb-6 flex items-center justify-between gap-3 rounded-xl border px-4 py-3 text-xs font-medium ${
            notice.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-red-50 border-red-200 text-red-800"
          }`}
        >
          <div className="flex items-center gap-2">
            {notice.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 shrink-0" />
            )}
            <span>{notice.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setNotice(null)}
            aria-label="Dismiss message"
            className="opacity-70 hover:opacity-100"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Navigation Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-gray-200 mb-6 pb-3">
        <button
          type="button"
          onClick={() => setActiveTab("artifacts")}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors ${
            activeTab === "artifacts"
              ? "bg-gray-900 text-white"
              : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Artifacts &amp; Ordering</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("add")}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors ${
            activeTab === "add"
              ? "bg-[#f28c28] text-white"
              : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
          }`}
        >
          <PlusCircle className="w-4 h-4" />
          <span>Add Artifact (@promptally)</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("users")}
          className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-bold transition-colors ${
            activeTab === "users"
              ? "bg-purple-700 text-white"
              : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
          }`}
        >
          <Users className="w-4 h-4" />
          <span>Users &amp; Subscriptions</span>
        </button>
      </div>

      {/* ================================================================ */}
      {/* TAB 1: ARTIFACTS & ORDERING                                      */}
      {/* ================================================================ */}
      {activeTab === "artifacts" && (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-gray-100 flex flex-col gap-3">
            <div className="flex flex-wrap items-center gap-2.5">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  setAssetPage(1);
                  setAssetSearchQuery(assetSearchInput);
                }}
                className="relative flex-1 min-w-[220px]"
              >
                <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
                <input
                  type="text"
                  value={assetSearchInput}
                  onChange={(e) => setAssetSearchInput(e.target.value)}
                  placeholder="Search title, slug, or @author (press Enter)..."
                  className="w-full pl-9 pr-20 py-2 text-xs border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-[#f28c28]/25"
                />
                <button
                  type="submit"
                  className="absolute right-1.5 top-1 bottom-1 px-3 rounded-md bg-gray-900 text-white text-[11px] font-bold hover:bg-gray-800"
                >
                  Search
                </button>
              </form>

              <select
                value={assetSection}
                onChange={(e) => {
                  setAssetSection(e.target.value);
                  setAssetSubcategory("all");
                  setAssetPage(1);
                }}
                aria-label="Filter by section"
                className="px-3 py-2 text-xs font-semibold border border-gray-200 rounded-lg bg-white text-gray-700 outline-none"
              >
                <option value="all">All Sections</option>
                {sectionOptions.map((s) => (
                  <option key={s.slug} value={s.slug}>
                    {s.name}
                  </option>
                ))}
              </select>

              {assetSection !== "all" && filterSubcategories.length > 0 && (
                <select
                  value={assetSubcategory}
                  onChange={(e) => {
                    setAssetSubcategory(e.target.value);
                    setAssetPage(1);
                  }}
                  aria-label="Filter by subcategory"
                  className="px-3 py-2 text-xs font-semibold border border-gray-200 rounded-lg bg-white text-gray-700 outline-none"
                >
                  <option value="all">All Subcategories</option>
                  {filterSubcategories.map((sub) => (
                    <option key={sub.slug} value={sub.slug}>
                      {sub.name}
                    </option>
                  ))}
                </select>
              )}

              <select
                value={assetPricing}
                onChange={(e) => {
                  setAssetPricing(e.target.value as "all" | "free" | "paid");
                  setAssetPage(1);
                }}
                aria-label="Filter by pricing"
                className="px-3 py-2 text-xs font-semibold border border-gray-200 rounded-lg bg-white text-gray-700 outline-none"
              >
                <option value="all">All Pricing</option>
                <option value="free">Free Only</option>
                <option value="paid">Paid Only</option>
              </select>

              <button
                type="button"
                onClick={() => {
                  setAssetPinnedOnly((v) => !v);
                  setAssetPage(1);
                }}
                className={`inline-flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-bold border transition-colors ${
                  assetPinnedOnly
                    ? "bg-purple-100 text-purple-800 border-purple-300"
                    : "bg-white text-gray-600 border-gray-200 hover:bg-gray-50"
                }`}
              >
                <Pin className="w-3.5 h-3.5" />
                <span>Pinned Only</span>
              </button>
            </div>

            <p className="text-[11px] text-gray-500">
              Showing{" "}
              <span className="font-bold text-gray-800">
                {assetsData?.items.length ?? 0}
              </span>{" "}
              of{" "}
              <span className="font-bold text-gray-800">
                {assetsData?.total_filtered?.toLocaleString() ?? 0}
              </span>{" "}
              matching artifacts. Use <span className="font-semibold">Top</span> or arrows to pin
              and rearrange artifacts at the top of the registry.
            </p>
          </div>

          {assetsLoading ? (
            <div className="py-20 text-center flex flex-col items-center">
              <Loader2 className="w-6 h-6 text-[#f28c28] animate-spin mb-2" />
              <p className="text-xs text-gray-500">Loading artifacts...</p>
            </div>
          ) : !assetsData || assetsData.items.length === 0 ? (
            <div className="py-16 text-center text-xs text-gray-500">
              No artifacts match your current filters.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-500 font-bold uppercase tracking-wider text-[10px] border-b border-gray-200">
                  <tr>
                    <th className="py-3 px-4">Order</th>
                    <th className="py-3 px-4">Artifact</th>
                    <th className="py-3 px-4">Category</th>
                    <th className="py-3 px-4">Author</th>
                    <th className="py-3 px-4">Access</th>
                    <th className="py-3 px-4">Stats</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {assetsData.items.map((item, idx) => {
                    const thumb = item.gif_preview_url || item.media_preview_url;
                    const busy = busyAssetId === item.id;
                    return (
                      <tr
                        key={item.id}
                        className={`hover:bg-gray-50/80 transition-colors ${
                          item.display_priority > 0 ? "bg-purple-50/30" : ""
                        }`}
                      >
                        <td className="py-3 px-4 whitespace-nowrap">
                          {item.display_priority > 0 ? (
                            <span className="inline-flex items-center gap-1 bg-purple-100 text-purple-800 border border-purple-200 font-bold px-2 py-0.5 rounded text-[10px]">
                              <Pin className="w-3 h-3" />
                              #{item.display_priority}
                            </span>
                          ) : (
                            <span className="text-[11px] text-gray-400 font-mono">default</span>
                          )}
                        </td>

                        <td className="py-3 px-4">
                          <div className="flex items-center gap-3 min-w-[240px]">
                            {thumb ? (
                              <img
                                src={thumb}
                                alt={item.seo_title}
                                className="w-12 h-9 rounded-md object-cover border border-gray-200 shrink-0 bg-gray-100"
                              />
                            ) : (
                              <div className="w-12 h-9 rounded-md bg-gray-100 border border-gray-200 flex items-center justify-center text-gray-400 shrink-0">
                                <FileText className="w-4 h-4" />
                              </div>
                            )}
                            <div className="min-w-0">
                              <Link
                                href={`/p/${item.slug}`}
                                target="_blank"
                                className="font-bold text-gray-900 hover:text-[#f28c28] line-clamp-1 inline-flex items-center gap-1"
                              >
                                <span className="truncate max-w-[280px]">{item.seo_title}</span>
                                <ExternalLink className="w-3 h-3 shrink-0 opacity-60" />
                              </Link>
                              <p className="text-[11px] text-gray-400 font-mono truncate max-w-[300px]">
                                /{item.slug}
                              </p>
                            </div>
                          </div>
                        </td>

                        <td className="py-3 px-4 whitespace-nowrap">
                          <span className="block font-semibold text-gray-800">
                            {item.section_name || item.section_slug || "—"}
                          </span>
                          <span className="text-[11px] text-gray-500">
                            {item.category_name || item.category_slug || "—"}
                          </span>
                        </td>

                        <td className="py-3 px-4 whitespace-nowrap font-mono text-[11px] text-gray-700">
                          @{item.author_username}
                        </td>

                        <td className="py-3 px-4 whitespace-nowrap">
                          {item.is_paid ? (
                            <span className="bg-amber-100 text-amber-800 font-bold px-2 py-0.5 rounded text-[10px]">
                              ${item.price_usd.toFixed(2)}
                            </span>
                          ) : (
                            <span className="bg-emerald-50 text-emerald-700 font-bold px-2 py-0.5 rounded text-[10px]">
                              Free
                            </span>
                          )}
                        </td>

                        <td className="py-3 px-4 whitespace-nowrap text-[11px] text-gray-600 font-mono">
                          {item.copy_count}c / {item.download_count}d
                        </td>

                        <td className="py-3 px-4 whitespace-nowrap text-right">
                          <div className="inline-flex items-center gap-1">
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => handleMoveToTop(item)}
                              title="Shift to Top (#1)"
                              className="inline-flex items-center gap-1 px-2 py-1.5 rounded-lg bg-[#fff4e5] hover:bg-[#f28c28] text-[#c6600a] hover:text-white font-bold text-[11px] transition-colors disabled:opacity-50"
                            >
                              <ArrowUpToLine className="w-3.5 h-3.5" />
                              <span>Top</span>
                            </button>

                            <button
                              type="button"
                              disabled={busy || idx === 0}
                              onClick={() => handleShiftRelative(idx, -1)}
                              title="Move Up"
                              className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-100 text-gray-600 disabled:opacity-30"
                            >
                              <ArrowUp className="w-3.5 h-3.5" />
                            </button>

                            <button
                              type="button"
                              disabled={busy || idx === assetsData.items.length - 1}
                              onClick={() => handleShiftRelative(idx, 1)}
                              title="Move Down"
                              className="p-1.5 rounded-lg border border-gray-200 hover:bg-gray-100 text-gray-600 disabled:opacity-30"
                            >
                              <ArrowDown className="w-3.5 h-3.5" />
                            </button>

                            {item.display_priority > 0 && (
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => handleUnpin(item)}
                                title="Unpin (reset to default order)"
                                className="p-1.5 rounded-lg border border-purple-200 hover:bg-purple-50 text-purple-700 disabled:opacity-50"
                              >
                                <PinOff className="w-3.5 h-3.5" />
                              </button>
                            )}

                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => setConfirmModal({ kind: "delete-asset", asset: item })}
                              title="Delete artifact"
                              className="p-1.5 rounded-lg border border-red-200 hover:bg-red-50 text-red-600 disabled:opacity-50"
                            >
                              <Trash2 className="w-3.5 h-3.5" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {assetsData && assetsData.total_pages > 1 && (
            <div className="px-5 py-3.5 border-t border-gray-100 flex items-center justify-between text-xs text-gray-600">
              <span>
                Page <strong>{assetsData.page}</strong> of <strong>{assetsData.total_pages}</strong>
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={assetPage <= 1}
                  onClick={() => setAssetPage((p) => Math.max(1, p - 1))}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-200 font-bold hover:bg-gray-50 disabled:opacity-40"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  <span>Prev</span>
                </button>
                <button
                  type="button"
                  disabled={assetPage >= assetsData.total_pages}
                  onClick={() => setAssetPage((p) => p + 1)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-200 font-bold hover:bg-gray-50 disabled:opacity-40"
                >
                  <span>Next</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ================================================================ */}
      {/* TAB 2: ADD ARTIFACT (AS @promptally)                             */}
      {/* ================================================================ */}
      {activeTab === "add" && (
        <div className="bg-white rounded-2xl border border-gray-200 p-6 sm:p-8 max-w-4xl">
          <div className="flex flex-wrap items-center justify-between gap-3 pb-5 mb-6 border-b border-gray-100">
            <div>
              <h2 className="text-lg font-extrabold text-gray-900">Add Official Artifact</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Published artifacts from this panel automatically appear as{" "}
                <span className="font-mono font-bold text-[#f28c28]">@promptally</span> under{" "}
                <em>Created by</em>.
              </p>
            </div>
            <span className="inline-flex items-center gap-1.5 bg-[#fff4e5] text-[#c6600a] border border-[#f4b56a] px-3 py-1 rounded-full text-xs font-bold">
              <Shield className="w-3.5 h-3.5" />
              Added by @promptally
            </span>
          </div>

          {createdAsset && (
            <div className="mb-6 rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-emerald-800 text-xs font-semibold">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>
                  Artifact published as <strong>@promptally</strong>
                  {createdAsset.display_priority > 0
                    ? ` and pinned to top (#${createdAsset.display_priority})`
                    : ""}
                  .
                </span>
              </div>
              <Link
                href={createdAsset.url}
                target="_blank"
                className="inline-flex items-center gap-1 text-xs font-bold text-emerald-900 underline"
              >
                <span>Open Artifact Page</span>
                <ExternalLink className="w-3.5 h-3.5" />
              </Link>
            </div>
          )}

          <form onSubmit={handleCreateArtifact} className="space-y-6">
            {/* Taxonomy */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1.5">
                  Section / Modality *
                </label>
                <select
                  value={addSection}
                  onChange={(e) => setAddSection(e.target.value)}
                  className="w-full px-3 py-2.5 text-xs font-semibold border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-[#f28c28]/30"
                >
                  {sectionOptions.map((sec) => (
                    <option key={sec.slug} value={sec.slug}>
                      {sec.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1.5">
                  Subcategory *
                </label>
                <select
                  value={addSubcategory}
                  onChange={(e) => setAddSubcategory(e.target.value)}
                  className="w-full px-3 py-2.5 text-xs font-semibold border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-[#f28c28]/30"
                >
                  {addSubcategories.map((sub) => (
                    <option key={sub.slug} value={sub.slug}>
                      {sub.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Metadata */}
            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1.5">
                Heading / Title *
              </label>
              <input
                type="text"
                required
                value={addHeading}
                onChange={(e) => setAddHeading(e.target.value)}
                placeholder="e.g., Full-Stack FastAPI + Next.js Security Review Skill"
                className="w-full px-3.5 py-2.5 text-sm border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-[#f28c28]/30"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1.5">
                Short Description
              </label>
              <textarea
                rows={2}
                value={addDescription}
                onChange={(e) => setAddDescription(e.target.value)}
                placeholder="Concise summary shown on cards and search results..."
                className="w-full px-3.5 py-2.5 text-xs border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-[#f28c28]/30"
              />
            </div>

            {/* Preview Media: Image & GIF (Upload OR CDN URL) */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Image Preview */}
              <div className="rounded-xl border border-gray-200 p-4 bg-gray-50/60">
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-800">
                    <ImageIcon className="w-4 h-4 text-[#f28c28]" />
                    Preview Image (Optional)
                  </span>
                  <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5 text-[11px] font-bold">
                    <button
                      type="button"
                      onClick={() => {
                        setImageMode("upload");
                        setImageUrl("");
                      }}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                        imageMode === "upload" ? "bg-gray-900 text-white" : "text-gray-600"
                      }`}
                    >
                      <Upload className="w-3 h-3" />
                      Upload
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setImageMode("cdn");
                        setImageFile(null);
                      }}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                        imageMode === "cdn" ? "bg-gray-900 text-white" : "text-gray-600"
                      }`}
                    >
                      <Link2 className="w-3 h-3" />
                      CDN Link
                    </button>
                  </div>
                </div>

                {imageMode === "upload" ? (
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    onChange={(e) => setImageFile(e.target.files?.[0] || null)}
                    className="block w-full text-xs text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-[#fff4e5] file:text-[#c6600a] hover:file:bg-[#ffe7c7]"
                  />
                ) : (
                  <input
                    type="url"
                    value={imageUrl}
                    onChange={(e) => setImageUrl(e.target.value)}
                    placeholder="https://cdn.example.com/previews/blueprint.webp"
                    className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg bg-white outline-none focus:ring-2 focus:ring-[#f28c28]/30"
                  />
                )}

                {activeImagePreview && (
                  <div className="mt-3 relative rounded-lg overflow-hidden border border-gray-200 bg-white h-28">
                    <img
                      src={activeImagePreview}
                      alt="Image preview"
                      className="w-full h-full object-cover"
                    />
                  </div>
                )}
              </div>

              {/* GIF Preview */}
              <div className="rounded-xl border border-gray-200 p-4 bg-gray-50/60">
                <div className="flex items-center justify-between gap-2 mb-3">
                  <span className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-800">
                    <Sparkles className="w-4 h-4 text-[#f28c28]" />
                    Preview GIF (Optional)
                  </span>
                  <div className="inline-flex rounded-lg border border-gray-200 bg-white p-0.5 text-[11px] font-bold">
                    <button
                      type="button"
                      onClick={() => {
                        setGifMode("upload");
                        setGifUrl("");
                      }}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                        gifMode === "upload" ? "bg-gray-900 text-white" : "text-gray-600"
                      }`}
                    >
                      <Upload className="w-3 h-3" />
                      Upload
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        setGifMode("cdn");
                        setGifFile(null);
                      }}
                      className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md transition-colors ${
                        gifMode === "cdn" ? "bg-gray-900 text-white" : "text-gray-600"
                      }`}
                    >
                      <Link2 className="w-3 h-3" />
                      CDN Link
                    </button>
                  </div>
                </div>

                {gifMode === "upload" ? (
                  <input
                    type="file"
                    accept="image/gif"
                    onChange={(e) => setGifFile(e.target.files?.[0] || null)}
                    className="block w-full text-xs text-gray-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-[#fff4e5] file:text-[#c6600a] hover:file:bg-[#ffe7c7]"
                  />
                ) : (
                  <input
                    type="url"
                    value={gifUrl}
                    onChange={(e) => setGifUrl(e.target.value)}
                    placeholder="https://cdn.example.com/demos/workflow.gif"
                    className="w-full px-3 py-2 text-xs border border-gray-300 rounded-lg bg-white outline-none focus:ring-2 focus:ring-[#f28c28]/30"
                  />
                )}

                {activeGifPreview && (
                  <div className="mt-3 relative rounded-lg overflow-hidden border border-gray-200 bg-white h-28">
                    <img
                      src={activeGifPreview}
                      alt="GIF preview"
                      className="w-full h-full object-cover"
                    />
                  </div>
                )}
              </div>
            </div>

            {/* Artifact Payload */}
            <div>
              <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
                <label className="text-xs font-bold text-gray-700">Artifact Payload *</label>
                <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-0.5 text-[11px] font-bold">
                  <button
                    type="button"
                    onClick={() => setContentMode("text")}
                    className={`inline-flex items-center gap-1 px-3 py-1 rounded-md ${
                      contentMode === "text" ? "bg-gray-900 text-white" : "text-gray-600"
                    }`}
                  >
                    <FileText className="w-3 h-3" />
                    Paste Text
                  </button>
                  <button
                    type="button"
                    onClick={() => setContentMode("file")}
                    className={`inline-flex items-center gap-1 px-3 py-1 rounded-md ${
                      contentMode === "file" ? "bg-gray-900 text-white" : "text-gray-600"
                    }`}
                  >
                    <Upload className="w-3 h-3" />
                    Single File
                  </button>
                  <button
                    type="button"
                    onClick={() => setContentMode("folder")}
                    className={`inline-flex items-center gap-1 px-3 py-1 rounded-md ${
                      contentMode === "folder" ? "bg-gray-900 text-white" : "text-gray-600"
                    }`}
                  >
                    <FolderArchive className="w-3 h-3" />
                    Folder / Multiple
                  </button>
                </div>
              </div>

              {contentMode === "text" && (
                <textarea
                  rows={8}
                  value={rawText}
                  onChange={(e) => setRawText(e.target.value)}
                  placeholder="Paste prompt template (supports {{variables}}), SKILL.md, mcp.json, workflow JSON, or loop config..."
                  className="w-full px-3.5 py-3 text-xs font-mono border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-[#f28c28]/30"
                />
              )}

              {contentMode === "file" && (
                <div className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center">
                  <input
                    type="file"
                    onChange={(e) => setSingleFile(e.target.files?.[0] || null)}
                    className="text-xs text-gray-600"
                  />
                  {singleFile && (
                    <p className="mt-2 text-xs font-semibold text-gray-800">{singleFile.name}</p>
                  )}
                </div>
              )}

              {contentMode === "folder" && (
                <div className="border-2 border-dashed border-gray-200 rounded-xl p-6 text-center">
                  <input
                    type="file"
                    multiple
                    onChange={(e) => setFolderFiles(e.target.files)}
                    className="text-xs text-gray-600"
                  />
                  {folderFiles && folderFiles.length > 0 && (
                    <p className="mt-2 text-xs font-semibold text-gray-800">
                      {folderFiles.length} file(s) selected (will be packaged into a .zip bundle)
                    </p>
                  )}
                </div>
              )}
            </div>

            {/* Optional Example Output */}
            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1.5">
                Example Output (Optional)
              </label>
              <textarea
                rows={3}
                value={addExampleOutput}
                onChange={(e) => setAddExampleOutput(e.target.value)}
                placeholder="Optional sample benchmark output or usage trace..."
                className="w-full px-3.5 py-2.5 text-xs font-mono border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-[#f28c28]/30"
              />
            </div>

            {/* Pin to Top checkbox + Submit */}
            <div className="flex flex-wrap items-center justify-between gap-4 pt-2 border-t border-gray-100">
              <label className="inline-flex items-center gap-2 text-xs font-bold text-gray-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={addPinToTop}
                  onChange={(e) => setAddPinToTop(e.target.checked)}
                  className="rounded border-gray-300 text-[#f28c28] focus:ring-[#f28c28]"
                />
                <span>Shift to top (#1) immediately after publishing</span>
              </label>

              <button
                type="submit"
                disabled={creatingAsset}
                className="inline-flex items-center gap-2 bg-[#f28c28] hover:bg-[#d66f0f] text-white font-bold text-xs px-6 py-3 rounded-xl shadow-sm transition-colors disabled:opacity-50"
              >
                {creatingAsset ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Publishing...</span>
                  </>
                ) : (
                  <>
                    <PlusCircle className="w-4 h-4" />
                    <span>Publish as @promptally</span>
                  </>
                )}
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ================================================================ */}
      {/* TAB 3: USERS & SUBSCRIPTIONS                                     */}
      {/* ================================================================ */}
      {activeTab === "users" && (
        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden">
          <div className="p-4 sm:p-5 border-b border-gray-100 flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  setUserFilterStatus("all");
                  setUserPage(1);
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  userFilterStatus === "all"
                    ? "bg-gray-900 text-white"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                All Users
              </button>
              <button
                type="button"
                onClick={() => {
                  setUserFilterStatus("subscribed");
                  setUserPage(1);
                }}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all ${
                  userFilterStatus === "subscribed"
                    ? "bg-amber-600 text-white"
                    : "text-gray-600 hover:bg-gray-100"
                }`}
              >
                Pro Subscribers Only
              </button>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                setUserPage(1);
                setUserSearchQuery(userSearchInput);
              }}
              className="relative w-full sm:w-80"
            >
              <Search className="w-4 h-4 text-gray-400 absolute left-3 top-2.5" />
              <input
                type="text"
                value={userSearchInput}
                onChange={(e) => setUserSearchInput(e.target.value)}
                placeholder="Search email, username, or name..."
                className="w-full pl-9 pr-20 py-2 text-xs border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-purple-500/20"
              />
              <button
                type="submit"
                className="absolute right-1.5 top-1 bottom-1 px-3 rounded-md bg-gray-900 text-white text-[11px] font-bold hover:bg-gray-800"
              >
                Search
              </button>
            </form>
          </div>

          {usersLoading ? (
            <div className="py-20 text-center flex flex-col items-center justify-center">
              <Loader2 className="w-6 h-6 text-purple-600 animate-spin mb-2" />
              <p className="text-xs text-gray-500">Querying platform database...</p>
            </div>
          ) : !usersData || usersData.users.length === 0 ? (
            <div className="py-16 text-center text-xs text-gray-500">No matching users found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-gray-50 text-gray-500 font-bold uppercase tracking-wider text-[10px] border-b border-gray-200">
                  <tr>
                    <th className="py-3 px-4">User</th>
                    <th className="py-3 px-4">Tier</th>
                    <th className="py-3 px-4">Country / IP</th>
                    <th className="py-3 px-4">Subscription</th>
                    <th className="py-3 px-4">Assets</th>
                    <th className="py-3 px-4">Joined</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {usersData.users.map((u) => {
                    const isSelf = u.id === user.id;
                    const canEndSub =
                      u.tier === "PRO" ||
                      Boolean(u.subscription_status && u.subscription_status !== "CANCELED");

                    return (
                      <tr key={u.id} className="hover:bg-gray-50/80 transition-colors">
                        <td className="py-3 px-4">
                          <p className="font-bold text-gray-900">
                            {u.name || u.username}{" "}
                            <span className="font-mono font-normal text-gray-500">
                              @{u.username}
                            </span>
                            {isSelf && (
                              <span className="ml-1.5 text-[10px] bg-purple-100 text-purple-700 font-bold px-1.5 py-0.5 rounded">
                                YOU
                              </span>
                            )}
                          </p>
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

                        <td className="py-3 px-4 font-mono text-[11px] text-gray-600">
                          <span className="font-bold text-gray-800">{u.country_code || "US"}</span>
                          <span className="block text-[10px] text-gray-400">
                            {u.signup_ip || "—"}
                          </span>
                        </td>

                        <td className="py-3 px-4">
                          {u.subscription_gateway ? (
                            <div>
                              <span className="font-bold text-gray-800 uppercase text-[10px]">
                                {u.subscription_gateway}
                              </span>
                              <span
                                className={`block text-[10px] font-semibold ${
                                  u.subscription_status === "ACTIVE"
                                    ? "text-emerald-600"
                                    : u.subscription_status === "CANCELED"
                                    ? "text-gray-400"
                                    : "text-amber-600"
                                }`}
                              >
                                {u.subscription_status}
                                {u.cancel_at_period_end ? " (ending)" : ""}
                              </span>
                            </div>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </td>

                        <td className="py-3 px-4 font-mono text-gray-700">{u.asset_count}</td>

                        <td className="py-3 px-4 text-gray-500 whitespace-nowrap">
                          {u.created_at ? new Date(u.created_at).toLocaleDateString() : "—"}
                        </td>

                        <td className="py-3 px-4 whitespace-nowrap text-right">
                          <div className="inline-flex items-center gap-1.5">
                            {canEndSub && (
                              <button
                                type="button"
                                onClick={() =>
                                  setConfirmModal({ kind: "end-subscription", targetUser: u })
                                }
                                className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-amber-300 bg-amber-50 hover:bg-amber-100 text-amber-800 font-bold text-[11px] transition-colors"
                              >
                                <Ban className="w-3.5 h-3.5" />
                                <span>End Sub</span>
                              </button>
                            )}

                            <button
                              type="button"
                              disabled={isSelf}
                              onClick={() =>
                                setConfirmModal({ kind: "delete-user", targetUser: u })
                              }
                              title={isSelf ? "You cannot delete your own admin account" : "Delete user account"}
                              className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-red-200 bg-red-50 hover:bg-red-100 text-red-700 font-bold text-[11px] transition-colors disabled:opacity-35 disabled:cursor-not-allowed"
                            >
                              <UserX className="w-3.5 h-3.5" />
                              <span>Delete</span>
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {usersData && usersData.total_pages > 1 && (
            <div className="px-5 py-3.5 border-t border-gray-100 flex items-center justify-between text-xs text-gray-600">
              <span>
                Page <strong>{usersData.page}</strong> of <strong>{usersData.total_pages}</strong>
              </span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  disabled={userPage <= 1}
                  onClick={() => setUserPage((p) => Math.max(1, p - 1))}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-200 font-bold hover:bg-gray-50 disabled:opacity-40"
                >
                  <ChevronLeft className="w-3.5 h-3.5" />
                  <span>Prev</span>
                </button>
                <button
                  type="button"
                  disabled={userPage >= usersData.total_pages}
                  onClick={() => setUserPage((p) => p + 1)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg border border-gray-200 font-bold hover:bg-gray-50 disabled:opacity-40"
                >
                  <span>Next</span>
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ================================================================ */}
      {/* CONFIRMATION MODAL                                               */}
      {/* ================================================================ */}
      {confirmModal && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center bg-black/50 px-4">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-2xl max-w-md w-full p-6">
            {confirmModal.kind === "delete-asset" && (
              <>
                <h3 className="text-base font-extrabold text-gray-900">Delete Artifact?</h3>
                <p className="text-xs text-gray-600 mt-2 leading-relaxed">
                  Are you sure you want to remove{" "}
                  <strong className="text-gray-900">{confirmModal.asset.seo_title}</strong> from
                  Promptally? It will be removed from public browsing and search immediately.
                </p>
              </>
            )}

            {confirmModal.kind === "end-subscription" && (
              <>
                <h3 className="text-base font-extrabold text-gray-900">End Pro Subscription?</h3>
                <p className="text-xs text-gray-600 mt-2 leading-relaxed">
                  This will immediately cancel{" "}
                  <strong className="text-gray-900">
                    @{confirmModal.targetUser.username} ({confirmModal.targetUser.email})
                  </strong>
                  &apos;s Pro subscription (including remote Razorpay/Dodo cancellation if
                  configured) and downgrade them to Free.
                </p>
              </>
            )}

            {confirmModal.kind === "delete-user" && (
              <>
                <h3 className="text-base font-extrabold text-red-700">Delete User Account?</h3>
                <p className="text-xs text-gray-600 mt-2 leading-relaxed">
                  Permanently delete{" "}
                  <strong className="text-gray-900">
                    @{confirmModal.targetUser.username} ({confirmModal.targetUser.email})
                  </strong>
                  ? Their sessions will be revoked, active subscription ended, and their account
                  removed. This cannot be undone.
                </p>
              </>
            )}

            <div className="mt-6 flex items-center justify-end gap-2">
              <button
                type="button"
                disabled={confirmBusy}
                onClick={() => setConfirmModal(null)}
                className="px-4 py-2 rounded-xl border border-gray-200 text-xs font-bold text-gray-700 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={confirmBusy}
                onClick={handleConfirmAction}
                className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white disabled:opacity-50 ${
                  confirmModal.kind === "end-subscription"
                    ? "bg-amber-600 hover:bg-amber-700"
                    : "bg-red-600 hover:bg-red-700"
                }`}
              >
                {confirmBusy && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>
                  {confirmModal.kind === "delete-asset"
                    ? "Delete Artifact"
                    : confirmModal.kind === "end-subscription"
                    ? "End Subscription"
                    : "Delete Account"}
                </span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
