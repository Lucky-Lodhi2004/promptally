import { ImageResponse } from "next/og";
import { getServerAsset } from "@/lib/server-api";

export const alt = "Promptally blueprint";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const revalidate = 3600;
export const runtime = "edge";

export default async function OpenGraphImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const asset = await getServerAsset(slug);
  const title = asset.seo_title.length > 90 ? `${asset.seo_title.slice(0, 87)}...` : asset.seo_title;
  const kind = asset.asset_type.replace(/_/g, " ");
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between",
        background: "#fff8ef", padding: 72, fontFamily: "sans-serif" }}>
        <div style={{ display: "flex", alignItems: "center", fontSize: 36, color: "#4b4b4d" }}>
          <div style={{ width: 56, height: 56, borderRadius: 12, background: "#f28c28", color: "#fff", display: "flex",
            alignItems: "center", justifyContent: "center", fontSize: 36, fontWeight: 700, marginRight: 18 }}>P</div>
          promptally
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 28, color: "#d66f0f", fontWeight: 700, textTransform: "uppercase", marginBottom: 18 }}>
            {kind}{asset.is_paid ? ` · $${asset.price_usd.toFixed(2)}` : " · Free"}
          </div>
          <div style={{ fontSize: 66, fontWeight: 700, color: "#2f3032", lineHeight: 1.1 }}>{title}</div>
        </div>
        <div style={{ fontSize: 28, color: "#77777a" }}>
          {asset.section?.name || "AI Blueprint Registry"} · by @{asset.author?.username || "promptally"}
        </div>
      </div>
    ),
    size,
  );
}
