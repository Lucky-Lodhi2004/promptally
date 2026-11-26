import type { Metadata } from "next";
import { headers } from "next/headers";
import "./globals.css";
import { AuthProvider } from "@/context/AuthContext";
import { PostHogProvider } from "@/components/analytics/PostHogProvider";
import { TopUtilityBar } from "@/components/layout/TopUtilityBar";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar } from "@/components/layout/Sidebar";
import { EmailVerificationBanner } from "@/components/auth/EmailVerificationBanner";
import { AuthModal } from "@/components/auth/AuthModal";
import Link from "next/link";
import { Suspense } from "react";
import { BadgeDollarSign } from "lucide-react";
import { SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: "Promptally — The AI Blueprint Registry & Marketplace",
  description:
    "Open Registry & Marketplace of 35,000+ AI Prompts, Agentic Skills, MCP Server Configurations, IDE Rules, and SWE Repair Loops.",
  applicationName: "Promptally",
  // Explicit brand signals for Google's site-name system and social cards.
  openGraph: { siteName: "Promptally", type: "website", locale: "en_US" },
  twitter: { card: "summary_large_image" },
  appleWebApp: { title: "Promptally" },
  robots: { index: true, follow: true, "max-snippet": -1, "max-image-preview": "large", "max-video-preview": -1 },
};

const themeInitializer = `
  try {
    const savedTheme = localStorage.getItem("promptally-theme");
    const useDark = savedTheme === "dark";
    document.documentElement.classList.toggle("dark", useDark);
    document.documentElement.style.colorScheme = useDark ? "dark" : "light";
  } catch (_) {}
`;

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const nonce = (await headers()).get('x-nonce') || undefined;
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script nonce={nonce} dangerouslySetInnerHTML={{ __html: themeInitializer }} />
      </head>
      <body className="min-h-screen flex flex-col bg-white text-gray-900">
        <AuthProvider>
          <PostHogProvider>
          <EmailVerificationBanner />
          <TopUtilityBar />
          <Suspense fallback={<div className="h-16 bg-white border-b border-gray-200" />}>
            <Navbar />
          </Suspense>
          <AuthModal />
          <Link
            href="/publish"
            aria-label="Sell your artifact"
            title="Sell your artifact"
            className="group fixed bottom-5 right-5 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-[#f28c28] text-white shadow-lg transition-all hover:-translate-y-0.5 hover:bg-[#d66f0f] hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f28c28] focus-visible:ring-offset-2"
          >
            <BadgeDollarSign className="h-6 w-6" strokeWidth={2.2} />
            <span className="pointer-events-none absolute right-full mr-3 whitespace-nowrap rounded-md bg-[#303133] px-3 py-1.5 text-xs font-bold text-white opacity-0 shadow-md transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
              Sell your artifact
            </span>
          </Link>
          <div className="flex flex-1 items-stretch">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <main className="flex-1">{children}</main>

          <footer className="bg-[#303133] text-[#aaa] text-xs py-10 border-t border-[#55575a] mt-16">
            <div className="max-w-[1600px] mx-auto px-4 sm:px-8 grid grid-cols-1 md:grid-cols-4 gap-8">
              <div>
                <div className="flex items-center space-x-2 mb-3">
                  <div className="w-6 h-6 rounded bg-[#f28c28] flex items-center justify-center font-bold text-white text-xs">
                    P
                  </div>
                  <span className="font-extrabold text-white text-sm tracking-tight">Promptally</span>
                </div>
                <p className="text-gray-400 text-xs leading-relaxed max-w-xs">
                  The open registry and marketplace for prompt templates, SKILL.md packages, MCP servers, and autonomous engineering loops.
                </p>
                <p className="text-gray-500 text-[11px] mt-4">
                  © {new Date().getFullYear()} Promptally, Inc. All rights reserved.
                </p>
              </div>

              <div>
                <h4 className="font-bold text-white uppercase tracking-wider text-[11px] mb-3">Registry Categories</h4>
                <ul className="space-y-2 text-xs">
                  <li><Link href="/directory/prompts" className="hover:text-white transition-colors">Prompts (20,490)</Link></li>
                  <li><Link href="/directory/skills" className="hover:text-white transition-colors">Agentic Skills (6,442)</Link></li>
                  <li><Link href="/directory/mcp-configs" className="hover:text-white transition-colors">MCP Configs (4,370)</Link></li>
                  <li><Link href="/directory/agents-commands" className="hover:text-white transition-colors">Subagents & Commands (838)</Link></li>
                </ul>
              </div>

              <div>
                <h4 className="font-bold text-white uppercase tracking-wider text-[11px] mb-3">Architecture & Rules</h4>
                <ul className="space-y-2 text-xs">
                  <li><Link href="/directory/ide-design-specs" className="hover:text-white transition-colors">IDE Rules & Specs (585)</Link></li>
                  <li><Link href="/directory/custom-gpts" className="hover:text-white transition-colors">Custom GPTs (1,255)</Link></li>
                  <li><Link href="/directory/workflows" className="hover:text-white transition-colors">Workflows (548)</Link></li>
                  <li><Link href="/directory/loops" className="hover:text-white transition-colors">Verification Loops (26)</Link></li>
                  <li><Link href="/curated" className="hover:text-white transition-colors">Curated Collections</Link></li>
                </ul>
              </div>

              <div>
                <h4 className="font-bold text-white uppercase tracking-wider text-[11px] mb-3">Platform & Developers</h4>
                <ul className="space-y-2 text-xs">
                  <li><Link href="/contact" className="hover:text-white transition-colors">Contact Us</Link></li>
                  <li><Link href="/publish" className="hover:text-white transition-colors">Publish / Sell Blueprints</Link></li>
                  <li><Link href="/dashboard?tab=seller-studio" className="hover:text-white transition-colors">Seller Studio (0% Cut)</Link></li>
                  <li><Link href="/dashboard?tab=membership" className="hover:text-white transition-colors">Pro Membership ($1/mo)</Link></li>
                  <li><a href="/llms.txt" target="_blank" rel="noreferrer" className="hover:text-white transition-colors font-mono">/llms.txt</a></li>
                  <li><a href="/sitemap.xml" target="_blank" rel="noreferrer" className="hover:text-white transition-colors font-mono">/sitemap.xml</a></li>
                  <li><a href="/.well-known/mcp.json" target="_blank" rel="noreferrer" className="hover:text-white transition-colors font-mono">/.well-known/mcp.json</a></li>
                </ul>
              </div>
            </div>
          </footer>
            </div>
          </div>
          </PostHogProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

