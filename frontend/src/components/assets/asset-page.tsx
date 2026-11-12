import type { Metadata } from "next";
import { Suspense } from "react";
import AssetDetailView from "@/components/assets/AssetDetailView";
import { ArtifactSemanticOverview, ArtifactSemanticSupplement } from "@/components/assets/ArtifactSemanticContent";
import { getServerAsset } from "@/lib/server-api";
import { SITE_URL, absoluteUrl, jsonLd } from "@/lib/site";

/** Shared by the public route (/p/[slug]) and the private signed-in viewer route. */
export async function assetMetadata(slug: string, indexable = true, authenticated = false): Promise<Metadata> {
  const asset = await getServerAsset(slug, authenticated);
  const canonical = `${SITE_URL}/p/${encodeURIComponent(asset.slug)}`;
  const description = (asset.tldr_summary || asset.short_description).slice(0, 300);
  // Without an uploaded preview the generated opengraph-image route supplies the social card.
  const image = asset.media_preview_url ? absoluteUrl(asset.media_preview_url) : null;
  return {
    title: `${asset.seo_title} — Promptally`,
    description,
    alternates: { canonical, types: { "text/markdown": `${canonical}.md` } },
    robots: {
      index: indexable && asset.is_indexable,
      follow: true,
      "max-snippet": -1,
      "max-image-preview": "large",
      "max-video-preview": -1,
      googleBot: {
        index: indexable && asset.is_indexable,
        follow: true,
        "max-snippet": -1,
        "max-image-preview": "large",
        "max-video-preview": -1,
      },
    },
    openGraph: {
      title: asset.seo_title, description, url: canonical, type: "article", siteName: "Promptally",
      ...(image ? { images: [{ url: image, alt: asset.seo_title }] } : {}),
      ...(asset.updated_at ? { modifiedTime: asset.updated_at } : {}),
      ...(asset.created_at ? { publishedTime: asset.created_at } : {}),
    },
    twitter: { card: "summary_large_image", title: asset.seo_title, description, ...(image ? { images: [image] } : {}) },
  };
}

export async function AssetPageContent({ slug, authenticated = false }: { slug: string; authenticated?: boolean }) {
  // Fetch the authorized view directly: a purchased, delisted listing no longer
  // has a public representation. Never gate buyer access on an anonymous fetch.
  const asset = await getServerAsset(slug, authenticated);
  // Only public pages publish structured data. Private buyer/owner responses may
  // include unlocked content and must never become machine-readable SEO metadata.
  return <>
    {!authenticated && asset.json_ld && <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(asset.json_ld) }} />}
    <Suspense fallback={<h1>{asset.seo_title}</h1>}>
      <AssetDetailView
        initialAsset={asset}
        overviewContent={<ArtifactSemanticOverview asset={asset} />}
        supplementalContent={<ArtifactSemanticSupplement asset={asset} />}
      />
    </Suspense>
  </>;
}
