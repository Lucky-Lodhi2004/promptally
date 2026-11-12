import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { wantsMarkdown } from "@/lib/negotiation";

const SITE = (process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000").replace(/\/$/, "");
const ARTIFACT = /^\/p\/([^/]+?)(\.md)?$/;

export function middleware(request: NextRequest) {
  const headers = new Headers(request.headers);
  for (const name of ['cf-connecting-ip', 'cf-ipcountry', 'x-real-ip', 'x-forwarded-for',
    'x-country-code', 'x-dev-country', 'x-proxy-token', 'x-internal-render']) headers.delete(name);
  const nonce = btoa(crypto.randomUUID());
  const csp = [
    "default-src 'self'", "base-uri 'self'", "object-src 'none'", "frame-ancestors 'none'",
    `script-src 'self' 'nonce-${nonce}' https://accounts.google.com https://*.razorpay.com${process.env.NODE_ENV === 'development' ? " 'unsafe-eval'" : ''}`,
    "style-src 'self' 'unsafe-inline' https://accounts.google.com https://fonts.googleapis.com",
    "img-src 'self' data: blob: https:", "font-src 'self' data: https://fonts.gstatic.com",
    "connect-src 'self' https://accounts.google.com https://*.googleapis.com https://*.razorpay.com https://*.dodopayments.com",
    "frame-src https://accounts.google.com https://*.razorpay.com https://*.dodopayments.com",
    "form-action 'self' https://*.razorpay.com https://*.dodopayments.com",
  ].join('; ');
  headers.set('x-nonce', nonce);
  headers.set('Content-Security-Policy', csp);
  const secure = (response: NextResponse) => {
    response.headers.set('Content-Security-Policy', csp);
    return response;
  };
  const match = ARTIFACT.exec(request.nextUrl.pathname);
  if (!match) return secure(NextResponse.next({ request: { headers } }));
  const slug = match[1];

  // Content negotiation: same URL, Markdown representation. The rewrite is proxied to the
  // API with the visitor's own credentials, so paid sources stay locked for non-buyers.
  if (!match[2] && wantsMarkdown(request.headers.get("accept") || "")) {
    const url = request.nextUrl.clone();
    url.pathname = `/api/v1/assets/${slug}.md`;
    const response = NextResponse.rewrite(url, { request: { headers } });
    response.headers.set("Vary", "Accept");
    return secure(response);
  }

  // A session cookie means the viewer may own or have bought this artifact: render their
  // access dynamically instead of serving the shared anonymous page.
  const signedIn = !match[2] && Boolean(request.cookies.get("access_token")?.value);
  let response = NextResponse.next({ request: { headers } });
  if (signedIn) {
    const url = request.nextUrl.clone();
    url.pathname = `/p-viewer/${slug}`;
    response = NextResponse.rewrite(url, { request: { headers } });
  }
  if (!match[2]) {
    // RFC 8288 discovery: agents learn about the Markdown twin before parsing the body.
    response.headers.append(
      "Link",
      `<${SITE}/p/${slug}.md>; rel="alternate"; type="text/markdown", <${SITE}/llms.txt>; rel="describedby"; type="text/markdown"`,
    );
    response.headers.set("Vary", "Accept");
  }
  return secure(response);
}

export const config = { matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"] };
