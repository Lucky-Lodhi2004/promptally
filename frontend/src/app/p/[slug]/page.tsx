import type { Metadata } from "next";
import { AssetPageContent, assetMetadata } from "@/components/assets/asset-page";

// Per-request CSP nonces must never be served inside cached HTML. Public API
// data remains cached; signed-in viewers are rewritten to their private route.
export const dynamic = "force-dynamic";
type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  return assetMetadata((await params).slug);
}

export default async function AssetPage({ params }: Props) {
  return <AssetPageContent slug={(await params).slug} />;
}
