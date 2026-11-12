import type { Metadata } from "next";
import { AssetPageContent, assetMetadata } from "@/components/assets/asset-page";

// Reached only through the middleware rewrite from /p/[slug] when a session cookie is present.
// It renders the viewer's own access (owner/buyer) per request and is never cached or indexed.
export const dynamic = "force-dynamic";
type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return assetMetadata((await params).slug, false, true);
}

export default async function AssetViewerPage({ params }: Props) {
  return <AssetPageContent slug={(await params).slug} authenticated />;
}
