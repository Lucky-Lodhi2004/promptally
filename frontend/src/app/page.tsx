import Link from "next/link";
import type { Metadata } from "next";
import { Search, ArrowRight } from "lucide-react";
import { AssetCard } from "@/components/assets/AssetCard";
import { CategoryDropdowns } from "@/components/directory/CategoryDropdowns";
import { getServerAssets } from "@/lib/server-api";
import { SAME_AS, SITE_URL, jsonLd } from "@/lib/site";

export const metadata: Metadata = {
  title: "Promptally — Free AI Prompt, Agent Skill & Workflow Registry",
  description:
    "Promptally is the open directory and marketplace for ChatGPT, Claude and Gemini prompts, ComfyUI & n8n node graphs, looping workflows, MCP configs and SKILL.md agent skills.",
  alternates: { canonical: "/", types: { "text/markdown": "/llms.txt" } },
  robots: { index: true, follow: true, "max-snippet": -1, "max-image-preview": "large", "max-video-preview": -1 },
  openGraph: {
    type: "website", url: "/", siteName: "Promptally",
    title: "Promptally — The AI Prompt, Skill & Workflow Registry",
    description: "Copy and download pre-filled prompts, looping workflows, MCP configs and agentic skills for free, or sell your own blueprints.",
    images: [{ url: "/og-home.png", width: 1200, height: 630, alt: "Promptally — AI Blueprint Registry" }],
  },
  twitter: { card: "summary_large_image", title: "Promptally — AI Prompt, Agent Skill & Workflow Registry", images: ["/og-home.png"] },
};

// Rendered per request (never prerendered at build time, so an API outage during a deploy can't
// freeze an empty page); the API call underneath is cached for 10 minutes by Next's data cache.
// The crawler-visible HTML never waits on client JS.
export const dynamic = "force-dynamic";

export default async function HomePage() {
  const featured = await getServerAssets({ pricing: "all", sort: "popular", page: 1, page_size: 16 }, 600);
  const items = featured?.items ?? [];

  const structured = {
    "@context": "https://schema.org",
    "@graph": [
      {
        "@type": "WebSite", "@id": `${SITE_URL}/#website`, url: `${SITE_URL}/`, name: "Promptally",
        alternateName: ["Promptally AI", "Promptally Registry"],
        description: "Open registry and marketplace for AI prompts, looping workflows, node graphs and agentic skills.",
        inLanguage: "en", publisher: { "@id": `${SITE_URL}/#organization` },
        potentialAction: {
          "@type": "SearchAction",
          target: { "@type": "EntryPoint", urlTemplate: `${SITE_URL}/directory?q={search_term_string}` },
          "query-input": "required name=search_term_string",
        },
      },
      {
        "@type": "Organization", "@id": `${SITE_URL}/#organization`, name: "Promptally", url: `${SITE_URL}/`,
        logo: { "@type": "ImageObject", url: `${SITE_URL}/logo-512x512.png`, width: 512, height: 512 },
        ...(SAME_AS.length ? { sameAs: SAME_AS } : {}),
      },
    ],
  };

  return (
    <div className="min-h-[calc(100vh-130px)] bg-white">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: jsonLd(structured) }} />
      <div className="px-5 py-10 sm:px-10 xl:px-[7%] xl:py-16">
        <section aria-labelledby="hero-heading" className="mb-12">
          <h1 id="hero-heading" className="text-[28px] font-light leading-tight tracking-tight text-[#4b4b4d] sm:text-[34px]">
            Promptally: The Open Registry for AI Prompts, Agentic Skills &amp; Workflows
          </h1>
          <p className="mt-3 max-w-3xl text-[15px] leading-relaxed text-gray-500">
            Explore, customize and copy pre-filled system prompts, ComfyUI and n8n node graphs, deterministic coding loops,
            MCP server configs and <code>SKILL.md</code> packages for free, or publish your own and sell them directly to buyers.
          </p>
          <div className="mt-6 rounded-lg border border-[#e6e6e7] bg-white p-0 shadow-[0_2px_12px_rgba(0,0,0,0.07)]">
            <form action="/directory" method="GET" role="search" className="relative flex items-center">
              <label htmlFor="global-search" className="sr-only">Search prompts, skills and workflows on Promptally</label>
              <input id="global-search" type="search" name="q" required placeholder="Search for your next AI blueprint"
                className="w-full rounded-lg bg-white px-5 py-3.5 pr-36 text-[15px] font-light text-[#666] outline-none placeholder:text-[#b8b9bc] focus:ring-2 focus:ring-[#f4b56a]" />
              <button type="submit" className="absolute bottom-1 right-3 top-1 flex items-center gap-3 px-3 text-[13px] font-medium text-[#f28c28] transition-colors">
                <span>Explore</span><Search aria-hidden="true" className="h-5 w-5 text-[#999]" />
              </button>
            </form>
          </div>
        </section>

        <section aria-labelledby="directory-hubs-heading" className="mb-14">
          <h2 id="directory-hubs-heading" className="mb-4 text-[22px] font-light text-[#69696c]">Browse by modality &amp; category</h2>
          <CategoryDropdowns />
        </section>

        <section aria-labelledby="trending-heading">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 id="trending-heading" className="text-[22px] font-light text-[#69696c]">Popular prompts, skills &amp; configs on Promptally</h2>
              <p className="mt-1 text-[15px] leading-relaxed text-gray-500">The most copied and downloaded blueprints in the registry.</p>
            </div>
            <Link href="/directory" className="flex items-center gap-1 text-[13px] font-bold text-[#f28c28] hover:text-[#d66f0f]">
              <span>Browse the directory</span><ArrowRight aria-hidden="true" className="h-3.5 w-3.5" />
            </Link>
          </div>
          <div className="mb-6 mt-4 h-[2px] bg-[#f4b56a]" />
          {items.length > 0 ? (
            <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {items.map((asset) => <AssetCard key={asset.id} asset={asset} />)}
            </div>
          ) : (
            <p className="py-12 text-center text-sm text-gray-500">No blueprints are published yet. <Link href="/publish" className="font-semibold text-[#f28c28] hover:underline">Publish the first one</Link>.</p>
          )}
        </section>
      </div>
    </div>
  );
}
