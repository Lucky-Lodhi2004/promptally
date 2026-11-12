/** True when the client prefers Markdown over HTML (agents, curl -H, IDE @web fetchers). */
export function wantsMarkdown(accept: string): boolean {
  const ranges = accept.split(",").map((part) => {
    const [type, ...params] = part.trim().toLowerCase().split(";");
    const q = params.map((p) => p.trim()).find((p) => p.startsWith("q="));
    const parsed = q ? parseFloat(q.slice(2)) : 1;
    return { type: type.trim(), q: Number.isNaN(parsed) ? 1 : parsed };
  });
  const md = ranges.find((r) => r.type === "text/markdown");
  if (!md || !(md.q > 0)) return false;
  const html = ranges.find((r) => r.type === "text/html");
  return !html || md.q >= html.q;
}
