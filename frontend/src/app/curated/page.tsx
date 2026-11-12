import Link from "next/link";
import type { Metadata } from "next";
import { FolderHeart } from "lucide-react";
import { getServerPublicCollections } from "@/lib/server-api";
import { SITE_URL, jsonLd } from "@/lib/site";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

export const metadata: Metadata = {
  title: "Curated AI Prompt & Skill Collections — Promptally",
  description: "Hand-picked collections of the best AI prompts, agent skills, MCP configs and workflows, curated by Promptally members.",
  alternates: { canonical: "/curated" },
  robots: { index: true, follow: true, "max-snippet": -1, "max-image-preview": "large" },
};

export default async function CuratedPage({ searchParams }: Props) {
  const raw = (await searchParams).page;
  const page = Math.max(1, parseInt((Array.isArray(raw) ? raw[0] : raw) || "1", 10) || 1);
  const data = await getServerPublicCollections(page);
  const items = data?.items ?? [];
  const structured = {
    "@context": "https://schema.org", "@type": "CollectionPage", name: "Curated collections", url: `${SITE_URL}/curated`,
    mainEntity: { "@type": "ItemList", itemListElement: items.map((c, i) => ({ "@type": "ListItem", position: i + 1, name: c.title, url: `${SITE_URL}/collections/${c.slug}` })) },
  };
  return (
    <div className="mx-auto max-w-6xl px-6 py-12">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(structured) }} />
      <nav aria-label="Breadcrumb" className="mb-4 text-xs text-gray-500">
        <Link href="/" className="font-medium hover:text-gray-900">Home</Link> <span aria-hidden="true">/</span>{" "}
        <span aria-current="page" className="font-bold text-gray-900">Curated collections</span>
      </nav>
      <h1 className="mb-2 text-3xl font-bold">Curated collections</h1>
      <p className="mb-8 max-w-2xl text-gray-600">Hand-picked sets of prompts, skills, configs and workflows, each with a side-by-side comparison table.</p>
      {items.length === 0 ? (
        <div className="rounded-2xl border border-gray-200 bg-gray-50 p-10 text-center">
          <FolderHeart aria-hidden="true" className="mx-auto mb-3 h-10 w-10 text-gray-400" />
          <p className="text-gray-600">No public collections yet. Pro members can publish one from <Link href="/collections" className="font-semibold text-amber-700 hover:underline">My Collections</Link>.</p>
        </div>
      ) : (
        <ul className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((c) => (
            <li key={c.id} className="rounded-xl border p-6 hover:border-amber-500">
              <h2 className="text-lg font-semibold"><Link href={`/collections/${c.slug}`} className="hover:text-amber-700">{c.title}</Link></h2>
              {c.description && <p className="my-2 line-clamp-3 text-sm text-gray-600">{c.description}</p>}
              <p className="text-xs text-gray-500">{c.item_count} blueprints · by @{c.owner.username}</p>
            </li>
          ))}
        </ul>
      )}
      {data && data.total_pages > 1 && (
        <nav aria-label="Pagination" className="mt-10 flex items-center justify-center gap-3 text-sm">
          {page > 1 && <Link rel="prev" href={page === 2 ? "/curated" : `/curated?page=${page - 1}`} className="rounded-lg border px-4 py-2 font-semibold">Previous</Link>}
          <span>Page {page} of {data.total_pages}</span>
          {page < data.total_pages && <Link rel="next" href={`/curated?page=${page + 1}`} className="rounded-lg border px-4 py-2 font-semibold">Next</Link>}
        </nav>
      )}
    </div>
  );
}
