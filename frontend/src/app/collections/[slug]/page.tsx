import type { Metadata } from "next";
import { notFound } from "next/navigation";
import CollectionDetailClient from "@/components/collections/CollectionDetailClient";
import { getServerCollection } from "@/lib/server-api";
import { SITE_URL, absoluteUrl, jsonLd } from "@/lib/site";

// Same threshold as the sitemap: thin collections stay usable but out of the index.
const MIN_INDEXABLE_ITEMS = 3;
export const revalidate = 600;
type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const { collection } = await getServerCollection(slug);
  // Private or missing: the anonymous API view is unavailable, so never index it.
  if (!collection) return { title: "Collection — Promptally", robots: { index: false, follow: false } };
  const canonical = `${SITE_URL}/collections/${encodeURIComponent(collection.slug)}`;
  const description = (collection.description
    || `${collection.items.length} curated AI blueprints by @${collection.owner.username} on Promptally.`).slice(0, 300);
  const indexable = collection.visibility === "PUBLIC" && collection.is_indexable && collection.items.length >= MIN_INDEXABLE_ITEMS;
  return {
    title: `${collection.title} — Curated Collection | Promptally`,
    description,
    alternates: { canonical },
    robots: { index: indexable, follow: true, "max-snippet": -1, "max-image-preview": "large" },
    openGraph: { title: collection.title, description, url: canonical, type: "website", siteName: "Promptally",
      ...(collection.cover_image_url ? { images: [{ url: absoluteUrl(collection.cover_image_url) }] } : {}) },
  };
}

export default async function CollectionPage({ params }: Props) {
  const { slug } = await params;
  const { collection, missing } = await getServerCollection(slug);
  if (missing) notFound();
  const structured = collection && {
    "@context": "https://schema.org",
    "@graph": [
      { "@type": "BreadcrumbList", itemListElement: [
        { "@type": "ListItem", position: 1, name: "Home", item: `${SITE_URL}/` },
        { "@type": "ListItem", position: 2, name: "Curated collections", item: `${SITE_URL}/curated` },
        { "@type": "ListItem", position: 3, name: collection.title, item: `${SITE_URL}/collections/${collection.slug}` } ] },
      { "@type": "CollectionPage", name: collection.title, url: `${SITE_URL}/collections/${collection.slug}`,
        description: collection.description || undefined,
        author: { "@type": "Person", name: collection.owner.username },
        mainEntity: { "@type": "ItemList", numberOfItems: collection.items.length,
          itemListElement: collection.items.map((item, i) => ({ "@type": "ListItem", position: i + 1,
            url: `${SITE_URL}/p/${item.slug}`, name: item.seo_title })) } },
    ],
  };
  return (
    <>
      {structured && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(structured) }} />}
      <CollectionDetailClient slug={slug} initialCollection={collection} />
    </>
  );
}
