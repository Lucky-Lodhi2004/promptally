const {test, beforeEach} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/google-identity.ts'), 'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
}).outputText;
let api, scripts;
beforeEach(() => {
  scripts = [];
  global.window = {setTimeout, clearTimeout};
  global.document = {createElement: () => ({remove() {this.removed = true;}}), head:{appendChild: script => scripts.push(script)}};
  api = {};
  new Function('exports', compiled)(api);
});
test('Google SDK loads once for concurrent callers and uses the official URL', async () => {
  const first = api.loadGoogleIdentity(), second = api.loadGoogleIdentity();
  assert.equal(first, second); assert.equal(scripts.length, 1);
  assert.equal(scripts[0].src, 'https://accounts.google.com/gsi/client');
  const identity = {renderButton(){}};
  window.google = {accounts:{id:identity}}; scripts[0].onload();
  assert.equal(await first, identity);
});
test('blocked SDK load rejects clearly and can be retried', async () => {
  const first = api.loadGoogleIdentity(); scripts[0].onerror();
  await assert.rejects(first, /could not load/); assert.ok(scripts[0].removed);
  const second = api.loadGoogleIdentity(); assert.equal(scripts.length, 2);
  window.google = {accounts:{id:{}}}; scripts[1].onload(); await second;
});
test('an existing Google SDK is reused without adding scripts', async () => {
  const identity = {}; window.google = {accounts:{id:identity}};
  assert.equal(await api.loadGoogleIdentity(), identity); assert.equal(scripts.length, 0);
});
