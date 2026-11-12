import "server-only";
import { cache } from "react";
import { cookies } from "next/headers";
import { notFound, permanentRedirect } from "next/navigation";
import type { AssetDetail, AssetListResponse, CollectionDetail, TaxonomyResponse } from "./types";

export const backendApi = (process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1")
  .replace(/\/$/, "").replace(/\/api\/v1$/, "") + "/api/v1";

/**
 * Server-to-server GET against FastAPI. Responses are cached by Next's data cache for
 * `revalidate` seconds, so crawler traffic fans in to a handful of API calls. When
 * INTERNAL_RENDER_TOKEN is configured on both sides the API also exempts these renders
 * from the per-IP read budget (otherwise every render shares the proxy's single IP).
 */
export async function backendFetch(path: string, revalidate = 300, headers: Record<string, string> = {}): Promise<Response> {
  const token = process.env.INTERNAL_RENDER_TOKEN;
  return fetch(`${backendApi}${path}`, {
    headers: { Accept: "application/json", ...(token ? { "X-Internal-Render": token } : {}), ...headers },
    next: { revalidate },
    redirect: "manual",
  });
}

/**
 * `authenticated` renders the signed-in viewer's own access (owner/buyer) and is never cached or shared.
 * Anonymous renders are identical for every visitor, so they are cached and edge-friendly.
 */
export const getServerAsset = cache(async (slug: string, authenticated = false): Promise<AssetDetail> => {
  const headers: Record<string, string> = {};
  if (authenticated) {
    // RequestCookies.toString() URL-encodes spaces, which would turn the legacy
    // "Bearer <JWT>" cookie into an invalid token at the API. Forward the parsed
    // session as Authorization instead; no unrelated cookies leave this server.
    const token = (await cookies()).get("access_token")?.value.replace(/^"(.*)"$/, "$1");
    if (token) headers.Authorization = token.startsWith("Bearer ") ? token : `Bearer ${token}`;
  }
  const res = await backendFetch(`/assets/${encodeURIComponent(slug)}`, authenticated ? 0 : 300, headers);
  if (res.status === 404 || res.status === 410) notFound();
  if (res.status === 301) {
    const target = res.headers.get("location");
    const nextSlug = target?.split("/").pop();
    if (nextSlug) permanentRedirect(`/p/${encodeURIComponent(nextSlug)}`);
  }
  if (!res.ok) throw new Error("The registry is temporarily unavailable. Please try again.");
  return res.json();
});

export const getServerTaxonomy = cache(async (): Promise<TaxonomyResponse | null> => {
  try {
    const res = await backendFetch("/taxonomy", 600);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
});

export async function getServerAssets(params: Record<string, string | number | undefined>, revalidate = 300): Promise<AssetListResponse | null> {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) if (value !== undefined && value !== "") search.set(key, String(value));
  try {
    const res = await backendFetch(`/assets?${search.toString()}`, revalidate);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

/**
 * Anonymous view of a collection. `missing` is a true 404 (the slug does not exist);
 * a private collection returns 403, which the page renders client-side for its owner.
 */
export async function getServerCollection(slug: string): Promise<{ collection: CollectionDetail | null; missing: boolean }> {
  try {
    const res = await backendFetch(`/collections/${encodeURIComponent(slug)}`, 600);
    if (res.ok) return { collection: await res.json(), missing: false };
    return { collection: null, missing: res.status === 404 };
  } catch {
    return { collection: null, missing: false };
  }
}

export interface PublicCollectionList {
  items: { id: string; slug: string; title: string; description: string | null; cover_image_url: string | null;
    item_count: number; owner: { username: string; name: string }; updated_at: string | null }[];
  total: number; page: number; page_size: number; total_pages: number;
}

export async function getServerPublicCollections(page = 1): Promise<PublicCollectionList | null> {
  try {
    const res = await backendFetch(`/discover/collections?page=${page}&page_size=24`, 600);
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}
