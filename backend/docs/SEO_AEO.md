# SEO and AEO

How Promptally exposes its catalog to search engines (SEO) and AI answer engines / coding
agents (AEO). Run commands from the repository root.

## URL model

| URL | Purpose | Indexed |
|---|---|---|
| `/` | Brand home: `<h1>`, hub links, featured items, WebSite + Organization JSON-LD | yes |
| `/directory` | Section index; `?q=` is global search | index only without `q` |
| `/directory/{section}` | Section hub | yes if it has items |
| `/directory/{section}/{category}` | Category hub (one clean URL per taxonomy node) | yes if it has items |
| `/p/{slug}` | Artifact page | per `is_indexable` |
| `/p/{slug}.md` or `Accept: text/markdown` | Markdown twin | n/a |
| `/collections/{slug}` | Public collection hub with comparison table | public, indexable, 3+ items |
| `/curated` | Index of public collections | yes |

`?q=`, `?sort=`, `?pricing=` render `noindex, follow` and canonicalize to the clean hub.
`?page=N` is self-canonical. Legacy `?subcategory=` URLs 308-redirect to the path form.
Unknown sections/categories/slugs return real 404s. Sections that exist in the UI but are
not seeded yet render an empty, `noindex` hub (HTTP 200).

## Quality gate and internal links

* `is_indexable` requires 450+ characters of prompt + description + sample output, and
  less than 0.90 lexical similarity to an earlier indexed page in the section.
* Each indexable page stores 12 `related_artifacts`: 8 nearest by IDF-weighted token
  overlap and 4 from a deterministic per-category ring, so no indexable page is orphaned.
  Publishing also adds the new page to its peers' links.
* This is a lexical stand-in for pgvector (no extension needed). To switch later, replace
  `RelatedIndex` in `backend/app/services/related.py`; keep the returned list-of-dict shape.
* Refresh everything for an existing database (safe to re-run; uses your configured DB):

```bash
backend/venv/bin/python backend/scripts/enrich_seo_aeo.py
```

## Caching and counters

* Anonymous `GET /assets/{slug}` is `public, s-maxage=3600` with a weak ETag and `304`
  support (a paid item's anonymous payload is the locked view, identical for everyone).
  Authenticated requests stay `private, no-store`.
* Views count only when the browser asks (`?view=1`, once per page load); server renders,
  crawlers and payment polling do not. Counters no longer change `updated_at`, so ETags
  and sitemap `<lastmod>` only move on real content edits.
* Next serves `/p/{slug}` from a shared ISR cache (5 min). Requests with an `access_token`
  cookie are rewritten by `middleware.ts` to the dynamic, `noindex` `/p-viewer/{slug}`
  so owners and buyers see their unlocked content.

## Optional: stop SSR renders sharing one rate-limit bucket

The Next server calls the API from a single IP. Without this, crawler-triggered renders
share one 60-reads/min budget (the Next data cache already absorbs most of it). Set the
**same random value** on both sides, then restart both:

```ini
# backend/.env
INTERNAL_RENDER_TOKEN=<long random string>
# frontend/.env.local
INTERNAL_RENDER_TOKEN=<same value>
```

Only GET/HEAD requests carrying that header are exempt; browsers never see the token.
Do not use a User-Agent allowlist for this.

## Other settings

* `NEXT_PUBLIC_SITE_URL` must be the public HTTPS origin (canonicals, sitemaps, JSON-LD).
  When it is an apex HTTPS URL, `www.` is permanently redirected to it.
* `NEXT_PUBLIC_SAME_AS` (optional): comma-separated HTTPS profile URLs (GitHub, npm, X...)
  emitted as Organization `sameAs`. List only profiles that exist.
* The IndexNow key file (`/<INDEXNOW_KEY>.txt`) is proxied to the API; other `.txt` names 404.
  Change `INDEXNOW_KEY` from its default before relying on it.

## Machine endpoints

* `/llms.txt` (top 20) and `/llms-full.txt` (all categories + top 200).
* `/sitemap.xml` indexes `pages.xml` (home, hubs), one chunked sitemap per section, and
  `collections-0.xml`.
* `POST /api/v1/mcp` requires a Google-authorized MCP bearer token; see [MCP OAuth](MCP_OAUTH.md).
  It speaks JSON-RPC 2.0 (`initialize`, `ping`, `tools/list`,
  `tools/call`); the original un-enveloped shape still works. Manifest: `/.well-known/mcp.json`.
* `PATCH /api/v1/assets/{id}` edits title/description/sample output; renaming records the
  old slug in `slug_redirects` (301). Deleting an artifact returns 404 afterwards (no 410).

## Brand assets

`frontend/scripts/generate-brand-assets.py` regenerates `favicon.ico`, `apple-icon.png`,
`public/logo-512x512.png` and `public/og-home.png` (needs Pillow).

## Verify

```bash
backend/venv/bin/python -m pytest backend/tests -q
npm --prefix frontend test && (cd frontend && npx tsc --noEmit)
backend/venv/bin/python frontend/scripts/verify-integration.py
```
