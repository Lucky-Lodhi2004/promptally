/** Canonical public origin. Set NEXT_PUBLIC_SITE_URL in production; never rely on the localhost fallback. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");
export const SITE_NAME = "Promptally";

/** Only list brand profiles that really exist: NEXT_PUBLIC_SAME_AS="https://github.com/promptally,https://x.com/promptally" */
export const SAME_AS: string[] = (process.env.NEXT_PUBLIC_SAME_AS || "")
  .split(",").map((u) => u.trim()).filter((u) => /^https:\/\//.test(u));

/** Escape `<` so JSON-LD can never close its own <script> element. */
export function jsonLd(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}

export function absoluteUrl(path: string): string {
  return /^https?:\/\//.test(path) ? path : `${SITE_URL}${path.startsWith("/") ? "" : "/"}${path}`;
}

/** Clean hub URLs. `all` is the section hub itself, so there is exactly one URL per hub. */
export function hubPath(section: string, category?: string | null): string {
  return !category || category === "all" ? `/directory/${section}` : `/directory/${section}/${category}`;
}
