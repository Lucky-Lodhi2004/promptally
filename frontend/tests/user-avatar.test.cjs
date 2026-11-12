const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/components/ui/UserAvatar.tsx'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.React, target: ts.ScriptTarget.ES2022 },
}).outputText;

test('avatar falls back on missing or broken URLs and accepts a new custom URL', () => {
  let state = null;
  const react = {
    createElement: (type, props, ...children) => ({ type, props, children }),
    useState: () => [state, (value) => { state = value; }],
  };
  react.default = react;
  const exports = {};
  new Function('exports', 'require', compiled)(exports, () => react);
  const render = (src) => exports.UserAvatar({ src, alt: 'Profile' }).children[0];
  const fallback = '/avatars/default-avatar.svg';
  assert.equal(render(null).props.src, fallback);
  assert.equal(render('  ').props.src, fallback);
  const broken = render('/missing-avatar.jpg');
  assert.equal(broken.props.src, '/missing-avatar.jpg');
  broken.props.onError();
  assert.equal(render('/missing-avatar.jpg').props.src, fallback);
  assert.equal(render('/uploads/avatars/new.webp').props.src, '/uploads/avatars/new.webp');
});
