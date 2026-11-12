import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

// Search and AI-answer crawlers are explicitly welcome on the public catalog. Private areas,
// the JSON API and filter/sort permutations are not (they canonicalize to the clean hubs).
const AI_AND_SEARCH_BOTS = [
  "Googlebot", "Bingbot", "OAI-SearchBot", "ChatGPT-User", "PerplexityBot", "Perplexity-User",
  "Claude-SearchBot", "Claude-User", "Google-Extended", "Applebot-Extended", "DuckDuckBot",
];
const PUBLIC = ["/", "/p/", "/directory", "/curated", "/collections/", "/llms.txt", "/llms-full.txt", "/api/v1/seo/", "/.well-known/mcp.json"];
const PRIVATE = ["/api/", "/p-viewer/", "/dashboard", "/admin", "/publish", "/verify-email", "/collections$"];
const FACETS = ["/*?*sort=", "/*?*pricing=", "/*?*q="];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: AI_AND_SEARCH_BOTS, allow: PUBLIC, disallow: [...PRIVATE, ...FACETS] },
      { userAgent: "*", allow: PUBLIC, disallow: [...PRIVATE, ...FACETS] },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
