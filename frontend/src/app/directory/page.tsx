import Link from "next/link";
import type { Metadata } from "next";
import { Search } from "lucide-react";
import { AssetCard } from "@/components/assets/AssetCard";
import { getServerAssets, getServerTaxonomy } from "@/lib/server-api";
import { CATEGORIES } from "@/lib/constants";
import { SITE_URL, absoluteUrl, jsonLd } from "@/lib/site";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };
const first = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v) || "";

export async function generateMetadata({ searchParams }: Props): Promise<Metadata> {
  const q = first((await searchParams).q).trim();
  return {
    title: q ? `Search results for "${q.slice(0, 60)}" — Promptally` : "AI Blueprint Directory — Promptally",
    description: "Browse AI prompts, agentic skills, MCP configs, IDE rules, workflows and verification loops on Promptally.",
    alternates: { canonical: "/directory" },
    robots: { index: !q, follow: true, "max-snippet": -1, "max-image-preview": "large" },
  };
}

export default async function DirectoryPage({ searchParams }: Props) {
  const sp = await searchParams;
  const q = first(sp.q).trim().slice(0, 100);
  const taxonomy = await getServerTaxonomy();
  if (!taxonomy) throw new Error("The directory is temporarily unavailable");
  const results = q ? await getServerAssets({ q, sort: "popular", page: 1, page_size: 24 }, 60) : null;
  // Sections the UI knows about stay listed (with zero items) until they are seeded.
  const sections = CATEGORIES.map((c) => {
    const live = taxonomy.sections.find((s) => s.slug === c.slug);
    return { slug: c.slug, name: live?.name || c.name, description: live?.description || c.description, count: live?.item_count ?? 0,
      categories: (live?.categories ?? []).filter((x) => x.slug !== "all") };
  });
  const structured = {
    "@context": "https://schema.org", "@type": "CollectionPage", name: "AI Blueprint Directory", url: absoluteUrl("/directory"),
    isPartOf: { "@type": "WebSite", name: "Promptally", url: `${SITE_URL}/` },
    mainEntity: { "@type": "ItemList", itemListElement: sections.map((s, i) => ({ "@type": "ListItem", position: i + 1, name: s.name, url: absoluteUrl(`/directory/${s.slug}`) })) },
  };

  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(structured) }} />
      <h1 className="mb-4 text-3xl font-bold">{q ? `Search results for “${q}”` : "AI Blueprint Directory"}</h1>
      <form action="/directory" method="GET" role="search" className="relative mb-8 max-w-xl">
        <label htmlFor="directory-search" className="sr-only">Search every Promptally section</label>
        <Search aria-hidden="true" className="absolute left-3.5 top-3 h-4 w-4 text-gray-400" />
        <input id="directory-search" type="search" name="q" defaultValue={q} placeholder="Search prompts, skills, workflows…"
          className="w-full rounded border border-[#d8d8da] py-2.5 pl-10 pr-20 text-[15px] outline-none focus:ring-2 focus:ring-[#f4b56a]" />
        <button type="submit" className="absolute bottom-1.5 right-1.5 top-1.5 rounded bg-[#f28c28] px-4 text-sm font-bold text-white hover:bg-[#d66f0f]">Search</button>
      </form>

      {q ? (
        results && results.items.length > 0 ? (
          <>
            <p className="mb-4 text-sm text-gray-500">{results.total.toLocaleString()} matching blueprints</p>
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">{results.items.map((a) => <AssetCard key={a.id} asset={a} />)}</div>
          </>
        ) : <p className="text-gray-600">No blueprints match “{q}”. Try a broader search or browse a section below.</p>
      ) : null}

      <h2 className={`mb-4 text-xl font-semibold ${q ? "mt-12" : "sr-only"}`}>Browse by section</h2>
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {sections.map((section) => (
          <article key={section.slug} className="rounded-xl border p-6 hover:border-amber-500">
            <h3 className="text-lg font-semibold"><Link href={`/directory/${section.slug}`} className="hover:text-amber-700">{section.name}</Link></h3>
            <p className="my-3 text-sm text-gray-600">{section.description}</p>
            <span className="text-sm text-gray-500">{section.count.toLocaleString()} blueprints</span>
            {section.categories.length > 0 && (
              <ul className="mt-3 space-y-1 text-sm">
                {section.categories.map((c) => (
                  <li key={c.id}><Link href={`/directory/${section.slug}/${c.slug}`} className="text-amber-700 hover:underline">{c.name}</Link></li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
    </div>
  );
}
