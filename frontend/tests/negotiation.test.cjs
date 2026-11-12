const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/negotiation.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const exportsObject = {};
new Function('exports', compiled)(exportsObject);
const { wantsMarkdown } = exportsObject;

test('browsers keep receiving HTML', () => {
  assert.equal(wantsMarkdown('text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'), false);
  assert.equal(wantsMarkdown('*/*'), false);
  assert.equal(wantsMarkdown(''), false);
});

test('agents asking for markdown get markdown', () => {
  assert.equal(wantsMarkdown('text/markdown'), true);
  assert.equal(wantsMarkdown('text/markdown, text/html;q=0.9'), true);
  assert.equal(wantsMarkdown('TEXT/Markdown;q=1.0, */*;q=0.1'), true);
});

test('HTML wins when it is preferred or markdown is refused', () => {
  assert.equal(wantsMarkdown('text/html, text/markdown;q=0.5'), false);
  assert.equal(wantsMarkdown('text/markdown;q=0'), false);
  assert.equal(wantsMarkdown('text/markdown;q=abc, text/html'), true);
});
