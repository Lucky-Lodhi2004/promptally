const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/middleware.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const exportsObject = {};
const response = (options) => ({ forwarded: options?.request?.headers, headers: new Headers() });
new Function('exports', 'require', compiled)(exportsObject, (name) => {
  if (name === 'next/server') return { NextResponse: {
    next: response, rewrite: (url, options) => ({ ...response(options), url }),
  }};
  if (name === '@/lib/negotiation') return { wantsMarkdown: (accept) => accept === 'text/markdown' };
  throw new Error(name);
});

test('Next strips forwarded identity and ingress credentials before proxying API traffic', () => {
  const incoming = new Headers({ 'X-Real-IP': '8.8.8.8', 'CF-Connecting-IP': '1.1.1.1', 'CF-IPCountry': 'IN',
    'X-Proxy-Token': 'forged-secret', 'X-Internal-Render': 'forged-render',
    'X-Forwarded-For': '8.8.4.4', Cookie: 'access_token=private-cookie' });
  const result = exportsObject.middleware({ headers: incoming, nextUrl: { pathname: '/api/v1/auth/signup' } });
  for (const name of ['X-Real-IP', 'CF-Connecting-IP', 'CF-IPCountry', 'X-Proxy-Token', 'X-Internal-Render', 'X-Forwarded-For']) {
    assert.equal(result.forwarded.get(name), null);
  }
  assert.equal(result.forwarded.get('Cookie'), 'access_token=private-cookie');
});

test('HTML responses get a unique nonce and a CSP compatible with Google and Razorpay', () => {
  const request = { headers: new Headers(), nextUrl: { pathname: '/dashboard' } };
  const first = exportsObject.middleware(request), second = exportsObject.middleware(request);
  const nonce = first.forwarded.get('x-nonce');
  assert.ok(nonce);
  assert.notEqual(nonce, second.forwarded.get('x-nonce'));
  const csp = first.headers.get('Content-Security-Policy');
  assert.ok(csp.includes(`'nonce-${nonce}'`));
  assert.ok(csp.includes("frame-ancestors 'none'"));
  assert.ok(csp.includes('https://accounts.google.com'));
  assert.ok(csp.includes('https://*.razorpay.com'));
  assert.ok(!csp.split('script-src')[1].split(';')[0].includes('unsafe-inline'));
});
