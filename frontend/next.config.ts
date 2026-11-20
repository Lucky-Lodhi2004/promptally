import type { NextConfig } from "next";

// Internal URL is used only by the Next server, never sent to browsers.
const backend = (process.env.API_INTERNAL_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1")
  .replace(/\/$/, "").replace(/\/api\/v1$/, "");

// One canonical host: www -> apex is a permanent redirect (only when a public site URL is configured).
const site = process.env.NEXT_PUBLIC_SITE_URL || "";
const apex = /^https:\/\/(?!www\.)([a-z0-9.-]+\.[a-z]{2,})\/?$/i.exec(site)?.[1];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async headers() {
    return [{source: "/:path*", headers: [
      {key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups"},
      {key: "X-Frame-Options", value: "DENY"},
      {key: "X-Content-Type-Options", value: "nosniff"},
      {key: "Referrer-Policy", value: "strict-origin-when-cross-origin"},
      ...(site.startsWith('https://') ? [{key: "Strict-Transport-Security", value: "max-age=31536000"}] : []),
    ]}];
  },
  async redirects() {
    return apex ? [{
      source: "/:path*",
      has: [{ type: "host", value: `www.${apex}` }],
      destination: `https://${apex}/:path*`,
      permanent: true,
    }] : [];
  },
  async rewrites() {
    return { beforeFiles: [
      { source: "/api/v1/:path*", destination: `${backend}/api/v1/:path*` },
      { source: "/uploads/:path*", destination: `${backend}/uploads/:path*` },
      { source: "/llms.txt", destination: `${backend}/llms.txt` },
      { source: "/llms-full.txt", destination: `${backend}/llms-full.txt` },
      { source: "/sitemap.xml", destination: `${backend}/sitemap.xml` },
      { source: "/.well-known/mcp.json", destination: `${backend}/.well-known/mcp.json` },
      { source: "/.well-known/oauth-protected-resource", destination: `${backend}/.well-known/oauth-protected-resource` },
      { source: "/.well-known/oauth-protected-resource/api/v1/mcp", destination: `${backend}/.well-known/oauth-protected-resource/api/v1/mcp` },
      { source: "/.well-known/oauth-authorization-server", destination: `${backend}/.well-known/oauth-authorization-server` },
      { source: "/p/:slug.md", destination: `${backend}/api/v1/assets/:slug.md` },
      // IndexNow key file: the API only serves the configured key and 404s every other name.
      { source: "/:key([A-Za-z0-9-]{8,64}).txt", destination: `${backend}/:key.txt` },
    ] };
  },
  images: { remotePatterns: [{ protocol: "https", hostname: "raw.githubusercontent.com" }] },
};
export default nextConfig;
