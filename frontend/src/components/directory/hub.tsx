import Link from "next/link";
import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { Search, Sparkles } from "lucide-react";
import { AssetCard } from "@/components/assets/AssetCard";
import { SubcategoryStrip } from "@/components/layout/SubcategoryStrip";
import { CATEGORIES } from "@/lib/constants";
import { SITE_URL, absoluteUrl, hubPath, jsonLd } from "@/lib/site";
import { getServerAssets, getServerTaxonomy } from "@/lib/server-api";
import type { AssetListResponse, TaxonomyCategory, TaxonomySection } from "@/lib/types";

export type SearchParams = Record<string, string | string[] | undefined>;

const SORTS = ["popular", "downloads", "newest"] as const;
const PRICING = ["all", "free", "paid"] as const;
const PAGE_SIZE = 24;
const SORT_LABELS: Record<string, string> = { popular: "Most Popular", downloads: "Most Downloaded", newest: "Recently Added" };

const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) || "";

interface HubState {
  sectionSlug: string;
  categorySlug?: string;
  sectionName: string;
  sectionDescription: string;
  section: TaxonomySection | null;
  category: TaxonomyCategory | null;
  categoryName: string | null;
  q: string;
  pricing: (typeof PRICING)[number];
  sort: (typeof SORTS)[number];
  page: number;
  filtered: boolean;
}

/** Legacy `?subcategory=` URLs permanently redirect to the clean path so each hub has one URL. */
function redirectLegacy(sectionSlug: string, categorySlug: string | undefined, sp: SearchParams) {
  const legacy = first(sp.subcategory);
  if (!legacy && categorySlug !== "all") return;
  const target = categorySlug === "all" ? undefined : legacy && legacy !== "all" ? legacy : undefined;
  const rest = new URLSearchParams();
  for (const [key, value] of Object.entries(sp)) {
    if (key !== "subcategory" && value !== undefined) rest.set(key, first(value));
  }
  const qs = rest.toString();
  permanentRedirect(`${hubPath(sectionSlug, categorySlug === undefined ? target : undefined)}${qs ? `?${qs}` : ""}`);
}

async function resolveHub(sectionSlug: string, categorySlug: string | undefined, sp: SearchParams): Promise<HubState> {
  redirectLegacy(sectionSlug, categorySlug, sp);
  const taxonomy = await getServerTaxonomy();
  if (!taxonomy) throw new Error("The directory is temporarily unavailable. Please try again.");
  const section = taxonomy.sections.find((s) => s.slug === sectionSlug) || null;
  const known = CATEGORIES.find((c) => c.slug === sectionSlug);
  // Unknown slugs are real 404s; sections defined in the UI but not yet seeded render an empty, noindexed hub.
  if (!section && !known) notFound();
  const category = categorySlug ? section?.categories.find((c) => c.slug === categorySlug) || null : null;
  const knownSub = known?.subcategories.find((s) => s.slug === categorySlug);
  if (categorySlug && !category && !knownSub) notFound();

  const q = first(sp.q).trim().slice(0, 100);
  const pricingRaw = first(sp.pricing);
  const sortRaw = first(sp.sort);
  const pricing = (PRICING as readonly string[]).includes(pricingRaw) ? (pricingRaw as HubState["pricing"]) : "all";
  const sort = (SORTS as readonly string[]).includes(sortRaw) ? (sortRaw as HubState["sort"]) : "popular";
  const page = Math.max(1, parseInt(first(sp.page) || "1", 10) || 1);
  return {
    sectionSlug, categorySlug, section, category, q, pricing, sort, page,
    sectionName: section?.name || known?.name || sectionSlug,
    sectionDescription: section?.description || known?.description || "",
    categoryName: category?.name || knownSub?.name || null,
    filtered: Boolean(q) || pricing !== "all" || sort !== "popular",
  };
}

function headingFor(h: HubState, count: number) {
  const label = h.categoryName ? `${h.categoryName} — ${h.sectionName}` : h.sectionName;
  return {
    title: h.categoryName ? `${h.category?.seo_title || `${h.categoryName} ${h.sectionName}`}` : `${h.sectionName} Directory`,
    h1: count > 0 ? `Browse ${count.toLocaleString()} ${label}` : label,
    description: (h.category?.seo_description || h.sectionDescription || `Browse ${label} on Promptally.`)
      + (count > 0 ? ` ${count.toLocaleString()} free and paid blueprints with pre-filled examples.` : ""),
  };
}

export async function hubMetadata(sectionSlug: string, categorySlug: string | undefined, sp: SearchParams): Promise<Metadata> {
  const h = await resolveHub(sectionSlug, categorySlug, sp);
  const count = (h.category || h.section)?.item_count ?? 0;
  const copy = headingFor(h, count);
  const base = hubPath(sectionSlug, categorySlug);
  const canonical = !h.filtered && h.page > 1 ? `${base}?page=${h.page}` : base;
  const title = h.page > 1 ? `${copy.title} (Page ${h.page}) — Promptally` : /Promptally/.test(copy.title) ? copy.title : `${copy.title} — Promptally`;
  return {
    title,
    description: copy.description.slice(0, 300),
    alternates: { canonical },
    // Filter/sort/search permutations never compete with the clean hub; empty hubs stay out of the index.
    robots: { index: !h.filtered && count > 0, follow: true, "max-snippet": -1, "max-image-preview": "large" },
    openGraph: { title: copy.title, description: copy.description.slice(0, 200), url: canonical, type: "website", siteName: "Promptally" },
  };
}

function href(h: HubState, overrides: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  const merged: Record<string, string | number | undefined> = {
    q: h.q || undefined, pricing: h.pricing !== "all" ? h.pricing : undefined,
    sort: h.sort !== "popular" ? h.sort : undefined, page: h.page > 1 ? h.page : undefined, ...overrides,
  };
  for (const [key, value] of Object.entries(merged)) if (value !== undefined && value !== "" && !(key === "page" && Number(value) <= 1)) params.set(key, String(value));
  const qs = params.toString();
  return `${hubPath(h.sectionSlug, h.categorySlug)}${qs ? `?${qs}` : ""}`;
}

export async function DirectoryHub({ sectionSlug, categorySlug, searchParams }: {
  sectionSlug: string; categorySlug?: string; searchParams: SearchParams;
}) {
  const h = await resolveHub(sectionSlug, categorySlug, searchParams);
  let list: AssetListResponse | null = null;
  if (h.section && (!h.categorySlug || h.category)) {
    list = await getServerAssets({
      section: h.sectionSlug, subcategory: h.categorySlug, q: h.q || undefined, pricing: h.pricing,
      sort: h.sort, page: h.page, page_size: PAGE_SIZE,
    }, h.q ? 60 : 300);
    if (!list) throw new Error("The directory is temporarily unavailable. Please try again.");
    if (h.page > 1 && list.items.length === 0) notFound();
  }
  const items = list?.items ?? [];
  const total = list?.total ?? 0;
  const totalPages = list?.total_pages ?? 1;
  const hubCount = (h.category || h.section)?.item_count ?? 0;
  const copy = headingFor(h, hubCount);
  const known = CATEGORIES.find((c) => c.slug === sectionSlug);
  const siblings = (h.section?.categories ?? []).filter((c) => c.slug !== "all");
  const pageUrl = absoluteUrl(hubPath(sectionSlug, categorySlug));

  const crumbs = [
    { name: "Home", path: "/" }, { name: "Directory", path: "/directory" },
    { name: h.sectionName, path: hubPath(sectionSlug) },
    ...(h.categoryName ? [{ name: h.categoryName, path: hubPath(sectionSlug, categorySlug) }] : []),
  ];
  const structured = {
    "@context": "https://schema.org",
    "@graph": [
      { "@type": "BreadcrumbList", itemListElement: crumbs.map((c, i) => ({ "@type": "ListItem", position: i + 1, name: c.name, item: absoluteUrl(c.path) })) },
      { "@type": "CollectionPage", "@id": `${pageUrl}#page`, name: copy.h1, description: copy.description, url: pageUrl,
        isPartOf: { "@type": "WebSite", name: "Promptally", url: `${SITE_URL}/` },
        mainEntity: { "@type": "ItemList", numberOfItems: total,
          itemListElement: items.map((a, i) => ({ "@type": "ListItem", position: (h.page - 1) * PAGE_SIZE + i + 1, url: absoluteUrl(`/p/${a.slug}`), name: a.seo_title })) } },
    ],
  };

  return (
    <div>
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(structured) }} />
      <SubcategoryStrip currentSectionSlug={sectionSlug} currentSubcategorySlug={categorySlug || "all"} />

      <div className="max-w-[1600px] mx-auto px-5 sm:px-9 py-5 sm:py-6">
        <nav aria-label="Breadcrumb" className="mb-4 flex flex-wrap items-center gap-x-2 text-xs text-gray-500">
          {crumbs.map((c, i) => (
            <span key={c.path} className="flex items-center gap-2">
              {i < crumbs.length - 1 ? <Link href={c.path} className="font-medium hover:text-gray-900">{c.name}</Link>
                : <span aria-current="page" className="font-bold text-gray-900">{c.name}</span>}
              {i < crumbs.length - 1 && <span aria-hidden="true">/</span>}
            </span>
          ))}
        </nav>

        <header className="bg-white p-0 pb-4 border-b-2 border-[#f4b56a] mb-5">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
            <div>
              <h1 className="text-[24px] sm:text-[26px] font-medium leading-tight text-[#5f6063] tracking-tight">{copy.h1}</h1>
              <p className="text-base text-[#77777a] mt-1.5 max-w-2xl leading-relaxed">{copy.description}</p>
            </div>
            <form action={hubPath(sectionSlug, categorySlug)} method="GET" role="search" className="relative w-full md:w-80 flex-shrink-0">
              <label htmlFor="hub-search" className="sr-only">Search in {h.categoryName || h.sectionName}</label>
              <Search aria-hidden="true" className="w-4 h-4 text-gray-400 absolute left-3.5 top-3" />
              <input id="hub-search" type="search" name="q" defaultValue={h.q} placeholder={`Search in ${h.categoryName || h.sectionName}...`}
                className="w-full pl-10 pr-20 py-2.5 text-[15px] bg-white border border-[#d8d8da] rounded outline-none focus:ring-2 focus:ring-[#f4b56a] shadow-sm" />
              <button type="submit" className="absolute right-1.5 top-1.5 bottom-1.5 bg-[#f28c28] hover:bg-[#d66f0f] text-white font-bold text-sm px-4 rounded transition-colors">Find</button>
            </form>
          </div>
        </header>

        {siblings.length > 0 && (
          <nav aria-label={`${h.sectionName} categories`} className="mb-5">
            <h2 className="sr-only">Browse {h.sectionName} by category</h2>
            <ul className="flex flex-wrap gap-2">
              {siblings.map((c) => (
                <li key={c.id}>
                  <Link href={hubPath(sectionSlug, c.slug)} aria-current={c.slug === categorySlug ? "page" : undefined}
                    className={`inline-block rounded-full border px-3 py-1 text-sm font-semibold ${c.slug === categorySlug ? "border-[#f4b56a] bg-[#fff3e2] text-[#d66f0f]" : "border-gray-200 text-gray-600 hover:border-[#f4b56a]"}`}>
                    {c.name} <span className="text-xs font-normal text-gray-400">({c.item_count.toLocaleString()})</span>
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
        )}

        <div className="flex flex-wrap items-center justify-between gap-4 mb-5 pb-3 border-b border-gray-200">
          <nav aria-label="Pricing filter" className="flex items-center gap-1.5">
            <span className="text-sm font-bold text-gray-500 uppercase tracking-wider mr-1">Pricing:</span>
            {PRICING.map((p) => (
              <Link key={p} href={href(h, { pricing: p === "all" ? undefined : p, page: undefined })} rel="nofollow" aria-current={h.pricing === p ? "true" : undefined}
                className={`px-3 py-1.5 rounded-lg text-sm font-semibold capitalize transition-all ${h.pricing === p ? "bg-[#f4b56a] text-white" : "bg-white text-gray-600 border border-gray-200 hover:border-[#f4b56a] hover:text-gray-900"}`}>{p}</Link>
            ))}
          </nav>
          <div className="flex flex-wrap items-center gap-4">
            <span className="text-sm text-gray-500 font-medium">Showing <strong className="text-gray-900">{total.toLocaleString()}</strong> blueprints</span>
            <nav aria-label="Sort order" className="flex items-center gap-1.5 text-sm">
              {SORTS.map((s) => (
                <Link key={s} href={href(h, { sort: s === "popular" ? undefined : s, page: undefined })} rel="nofollow" aria-current={h.sort === s ? "true" : undefined}
                  className={`rounded-lg border px-2.5 py-1.5 font-semibold ${h.sort === s ? "border-amber-500 text-gray-900" : "border-gray-200 text-gray-600 hover:border-amber-500"}`}>{SORT_LABELS[s]}</Link>
              ))}
            </nav>
          </div>
        </div>

        {items.length === 0 ? (
          <div className="py-20 text-center bg-gray-50 rounded-2xl border border-gray-200 p-8">
            <Sparkles aria-hidden="true" className="w-10 h-10 text-gray-400 mx-auto mb-3" />
            <h2 className="text-lg font-bold text-gray-800">{h.section ? "No blueprints match your filter" : "No blueprints published here yet"}</h2>
            <p className="text-base text-gray-500 mt-1.5 max-w-md mx-auto leading-relaxed">
              {h.section ? "Try another category or clear the filters." : `${known?.name || h.sectionName} will appear here as soon as the first blueprint is published.`}
            </p>
            <Link href={hubPath(sectionSlug, categorySlug)} className="mt-4 inline-block bg-amber-600 hover:bg-amber-500 text-white font-semibold text-sm px-5 py-2.5 rounded-lg transition-colors">
              {h.filtered ? "Reset filters" : "Browse the directory"}
            </Link>
          </div>
        ) : (
          <section aria-label="Blueprints">
            <h2 className="sr-only">{h.categoryName || h.sectionName} blueprints</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 sm:gap-6">
              {items.map((asset) => <AssetCard key={asset.id} asset={asset} />)}
            </div>
          </section>
        )}

        {totalPages > 1 && (
          <nav aria-label="Pagination" className="flex items-center justify-center gap-2 mt-12 pt-6 border-t border-gray-200">
            {h.page > 1 ? <Link href={href(h, { page: h.page - 1 })} rel="prev" className="px-4 py-2 rounded-lg border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50">Previous</Link>
              : <span aria-disabled="true" className="px-4 py-2 rounded-lg border border-gray-200 text-sm font-semibold text-gray-400">Previous</span>}
            <span className="text-sm text-gray-600 font-medium px-4">Page <strong className="text-gray-900">{h.page}</strong> of <strong className="text-gray-900">{totalPages}</strong></span>
            {h.page < totalPages ? <Link href={href(h, { page: h.page + 1 })} rel="next" className="px-4 py-2 rounded-lg border border-gray-200 text-sm font-semibold text-gray-700 hover:bg-gray-50">Next</Link>
              : <span aria-disabled="true" className="px-4 py-2 rounded-lg border border-gray-200 text-sm font-semibold text-gray-400">Next</span>}
          </nav>
        )}
      </div>
    </div>
  );
}
