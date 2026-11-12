import type { AssetDetail } from "@/lib/types";

function textList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).map((item) => item.trim()).filter(Boolean);
  if (typeof value === "string") return value.split(/[,|]/).map((item) => item.trim()).filter(Boolean);
  return [];
}

function compatibleModels(asset: AssetDetail) {
  const metadata = asset.technical_metadata || {};
  const values = textList(
    metadata.target_vendors || metadata.compatible_models || metadata.vendors || metadata.models,
  );
  return values.length ? values.join(", ") : "Universal / Model Agnostic";
}

type WorkflowStep = { name: string; type: string; detail: string };

function workflowSteps(asset: AssetDetail): WorkflowStep[] {
  if (asset.section?.slug !== "workflows" || !asset.raw_content) return [];
  try {
    const parsed = JSON.parse(asset.raw_content) as Record<string, unknown> | unknown[];
    const root = Array.isArray(parsed) ? parsed : parsed;
    const nested = !Array.isArray(root) && root.workflow && typeof root.workflow === "object"
      ? root.workflow as Record<string, unknown>
      : null;
    const candidate = Array.isArray(root)
      ? root
      : root.nodes || root.steps || nested?.nodes || nested?.steps;
    const nodes = Array.isArray(candidate)
      ? candidate
      : candidate && typeof candidate === "object"
        ? Object.values(candidate)
        : [];

    return nodes.slice(0, 50).map((node, index) => {
      const value = node && typeof node === "object" ? node as Record<string, unknown> : {};
      const name = String(value.name || value.label || value.title || value.id || `Step ${index + 1}`);
      const type = String(value.type || value.kind || value.operation || value.action || "Node");
      const description = value.description || value.summary || value.prompt || value.command;
      const detail = typeof description === "string"
        ? description
        : Object.keys(value).filter((key) => !["name", "label", "title", "id", "type", "kind"].includes(key)).slice(0, 5).join(", ") || "Configured workflow step";
      return { name, type, detail: detail.slice(0, 240) };
    });
  } catch {
    return [];
  }
}

export function ArtifactSemanticOverview({ asset }: { asset: AssetDetail }) {
  return (
    <>
      <header>
        <div className="mb-3 flex items-center gap-2">
          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-bold text-amber-800">
            {asset.asset_type.replace(/_/g, " ")}
          </span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${asset.is_paid ? "border border-amber-300 bg-amber-100 text-amber-800" : "bg-gray-100 text-gray-800"}`}>
            {asset.is_paid ? `$${asset.price_usd.toFixed(2)} USD` : "Free Blueprint"}
          </span>
          <span className="ml-auto text-xs font-medium text-gray-500">License: {asset.source_license}</span>
        </div>
        <h1 className="text-2xl font-extrabold leading-tight tracking-tight text-gray-900 sm:text-3xl">
          {asset.seo_title}
        </h1>
        <p data-aeo="citation-summary" className="mt-3 text-sm leading-relaxed text-gray-600">
          {asset.tldr_summary || asset.short_description}
        </p>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-4 border-t border-gray-100 pt-4 text-xs text-gray-500">
          <div className="flex items-center gap-2.5">
            <img
              src={asset.author?.avatar_url || "/avatars/default-avatar.svg"}
              alt=""
              className="h-7 w-7 rounded-full border border-gray-300 object-cover"
            />
            <span><span className="text-gray-400">Created by </span><strong className="text-gray-900">@{asset.author?.username || "promptally"}</strong></span>
          </div>
          <span>{asset.view_count.toLocaleString()} views · {asset.copy_count.toLocaleString()} copies · {asset.download_count.toLocaleString()} downloads</span>
        </div>
      </header>

      <section aria-labelledby="specs-heading">
        <h2 id="specs-heading" className="mb-3 text-base font-bold text-gray-900">Technical Specifications</h2>
        <div className="overflow-x-auto rounded-xl border border-gray-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-50 text-gray-500">
              <tr><th scope="col" className="px-4 py-2.5 font-bold">Specification</th><th scope="col" className="px-4 py-2.5 font-bold">Value</th></tr>
            </thead>
            <tbody className="divide-y divide-gray-100 text-gray-700">
              <tr><th scope="row" className="px-4 py-2.5 font-semibold">Artifact type</th><td className="px-4 py-2.5">{asset.asset_type.replace(/_/g, " ")}{asset.category ? ` (${asset.category.name})` : ""}</td></tr>
              <tr><th scope="row" className="px-4 py-2.5 font-semibold">Compatible engines</th><td className="px-4 py-2.5">{compatibleModels(asset)}</td></tr>
              <tr><th scope="row" className="px-4 py-2.5 font-semibold">Input variables</th><td className="px-4 py-2.5">{asset.variables_schema?.length ? asset.variables_schema.map((item) => item.name).join(", ") : "None (pre-filled)"}</td></tr>
              <tr><th scope="row" className="px-4 py-2.5 font-semibold">Approximate tokens</th><td className="px-4 py-2.5">{asset.token_count.toLocaleString()}</td></tr>
              <tr><th scope="row" className="px-4 py-2.5 font-semibold">Source file</th><td className="px-4 py-2.5 font-mono">{asset.file_name}</td></tr>
              <tr><th scope="row" className="px-4 py-2.5 font-semibold">Access tier</th><td className="px-4 py-2.5">{asset.is_paid ? `Marketplace paid ($${asset.price_usd.toFixed(2)} USD)` : `Free public (${asset.source_license})`}</td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

export function ArtifactSemanticSupplement({ asset }: { asset: AssetDetail }) {
  const steps = workflowSteps(asset);
  return (
    <>
      {asset.file_previews?.length > 0 && (
        <section aria-labelledby="bundle-files-heading">
          <h2 id="bundle-files-heading" className="mb-3 text-base font-bold text-gray-900">Included Source Files</h2>
          <div className="space-y-3">
            {asset.file_previews.map((file) => (
              <details key={file.name} open className="rounded-xl border border-gray-200 bg-white p-4">
                <summary className="cursor-pointer font-mono text-sm font-bold text-gray-900">{file.name}</summary>
                <pre className="mt-3 max-h-[500px] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-gray-50 p-4 font-mono text-xs text-gray-700"><code>{file.content}</code></pre>
              </details>
            ))}
          </div>
        </section>
      )}

      {steps.length > 0 && (
        <section aria-labelledby="workflow-steps-heading">
          <h2 id="workflow-steps-heading" className="mb-3 text-base font-bold text-gray-900">Workflow Node &amp; Step Summary</h2>
          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-50 text-gray-500"><tr><th className="px-4 py-2.5">Step</th><th className="px-4 py-2.5">Type</th><th className="px-4 py-2.5">Configuration</th></tr></thead>
              <tbody className="divide-y divide-gray-100 text-gray-700">
                {steps.map((step, index) => <tr key={`${step.name}-${index}`}><th scope="row" className="px-4 py-2.5 font-semibold">{step.name}</th><td className="px-4 py-2.5">{step.type}</td><td className="px-4 py-2.5">{step.detail}</td></tr>)}
              </tbody>
            </table>
          </div>
          <details open className="mt-3 rounded-xl border border-gray-200 bg-white p-4">
            <summary className="cursor-pointer text-sm font-bold text-gray-900">Raw workflow JSON</summary>
            <pre className="mt-3 max-h-[500px] overflow-auto whitespace-pre-wrap break-words rounded-lg bg-gray-50 p-4 font-mono text-xs text-gray-700"><code>{asset.raw_content}</code></pre>
          </details>
        </section>
      )}

      {asset.sample_output_markdown && (
        <section aria-labelledby="benchmark-heading" className="rounded-2xl border border-gray-200 bg-white p-6">
          <h2 id="benchmark-heading" className="mb-3 text-base font-bold text-gray-900">Verified Execution Output &amp; Benchmark</h2>
          <pre className="whitespace-pre-wrap break-words rounded-xl border border-gray-200 bg-gray-50 p-4 font-mono text-xs text-gray-700"><code>{asset.sample_output_markdown}</code></pre>
        </section>
      )}

      <section aria-labelledby="how-to-heading">
        <h2 id="how-to-heading" className="mb-3 text-base font-bold text-gray-900">How to use this {asset.asset_type.replace(/_/g, " ").toLowerCase()}</h2>
        <ol className="list-decimal space-y-1.5 pl-5 text-sm leading-relaxed text-gray-700">
          <li>{asset.is_paid && !asset.has_access ? "Review the public specifications and preview, then unlock the blueprint from its creator." : "Review the pre-filled example and source files above."}</li>
          {asset.variables_schema?.length > 0 && <li>Replace each variable ({asset.variables_schema.map((item) => `{{${item.name}}}`).join(", ")}) with your own value.</li>}
          <li>Copy the template or download <code>{asset.file_name}</code>, then use it in your model, IDE, or workflow tool.</li>
          <li>Compare your result with the sample output when one is provided.</li>
        </ol>
      </section>

      {asset.faq?.length > 0 && (
        <section aria-labelledby="faq-heading">
          <h2 id="faq-heading" className="mb-3 text-base font-bold text-gray-900">Frequently Asked Questions</h2>
          <div className="space-y-3">
            {asset.faq.map((item) => (
              <details key={item.question} open className="rounded-xl border border-gray-200 bg-white p-4">
                <summary className="cursor-pointer text-sm font-semibold text-gray-900">{item.question}</summary>
                <p className="mt-2 text-sm leading-relaxed text-gray-600">{item.answer}</p>
              </details>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
