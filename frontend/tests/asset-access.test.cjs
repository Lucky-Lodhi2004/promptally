const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

test('private asset pages and metadata fetch buyer access without requiring a public listing', async () => {
  const calls = [];
  const asset = { slug: 'delisted-purchase', seo_title: 'Purchased item', short_description: 'Preview',
    is_indexable: false, raw_content: 'private purchased text', json_ld: { private: 'must not render' } };
  const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname,
    '../src/components/assets/asset-page.tsx'), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
  }).outputText;
  const exportsObject = {};
  new Function('exports', 'require', compiled)(exportsObject, (name) => {
    if (name === 'react/jsx-runtime') return { jsx: (type, props) => ({ type, props }),
      jsxs: (type, props) => ({ type, props }), Fragment: 'fragment' };
    if (name === 'react') return { Suspense: 'suspense' };
    if (name === '@/components/assets/AssetDetailView') return { default: 'detail' };
    if (name === '@/components/assets/ArtifactSemanticContent') return {
      ArtifactSemanticOverview: 'semantic-overview', ArtifactSemanticSupplement: 'semantic-supplement',
    };
    if (name === '@/lib/server-api') return { getServerAsset: async (slug, authenticated) => {
      calls.push({ slug, authenticated });
      if (!authenticated) throw new Error('Public listing is not available');
      return asset;
    }};
    if (name === '@/lib/site') return { SITE_URL: 'https://app.promptally.dev',
      absoluteUrl: value => value, jsonLd: JSON.stringify };
    throw new Error(name);
  });
  const result = await exportsObject.AssetPageContent({ slug: asset.slug, authenticated: true });
  assert.equal(result.props.children[0], false, 'private structured data is omitted');
  assert.deepEqual(calls, [{ slug: asset.slug, authenticated: true }]);
  const metadata = await exportsObject.assetMetadata(asset.slug, false, true);
  assert.equal(metadata.robots.index, false);
  assert.equal(calls.length, 2);
  assert.ok(calls.every(call => call.authenticated));
});
