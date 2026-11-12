const { test, beforeEach } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const path = require('node:path');

const compiled = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../src/lib/api.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
function requireForApi(name) {
  if (name === './fingerprint') return {getDeviceFingerprint: async () => 'browser-device-fingerprint'};
  return require(name);
}
const moduleExports = {};
new Function('exports', 'require', compiled)(moduleExports, requireForApi);
const { api, ApiError, setCheckoutOwner } = moduleExports;
let calls;
beforeEach(() => {
  calls = [];
  setCheckoutOwner(null);
  global.window = {};
  global.localStorage = { getItem: () => 'test-token' };
  global.fetch = async (url, options) => {
    calls.push({ url, options });
    return Response.json({ status: 'success', collection_id: 'server-id', slug: 'my-collection', title: 'My collection', visibility: 'PUBLIC' });
  };
});

test('create-and-add uses returned collection_id and FormData over the same origin', async () => {
  const form = new FormData(); form.set('title', 'My collection');
  const created = await api.createCollection(form);
  await api.addItemToCollection(created.collection_id, 'asset-id');
  assert.equal(calls[1].url, '/api/v1/collections/server-id/items');
  assert.ok(calls[1].options.body instanceof FormData);
  assert.equal(calls[1].options.body.get('asset_id'), 'asset-id');
  assert.equal(calls[1].options.headers['Content-Type'], undefined);
});

test('remove uses the actual asset ID', async () => {
  await api.removeItemFromCollection('collection-id', 'actual-asset-id');
  assert.equal(calls[0].url, '/api/v1/collections/collection-id/items/actual-asset-id');
  assert.equal(calls[0].options.method, 'DELETE');
});

test('copy uses HttpOnly session cookies without reading a token from localStorage', async () => {
  global.fetch = async (url, options) => { calls.push({url,options}); return new Response('paid payload'); };
  assert.equal(await api.copyAsset('paid-prompt'), 'paid payload');
  assert.equal(calls[0].options.credentials, 'include');
  assert.equal(calls[0].options.headers.Authorization, undefined);
  assert.equal(calls[0].url, '/api/v1/assets/paid-prompt/download?action=copy');
});

test('copy rejects a paywall response rather than treating it as copied content', async () => {
  global.fetch = async () => Response.json({detail:'Purchase required'}, {status:403});
  await assert.rejects(api.copyAsset('locked'), error => error instanceof ApiError && error.status === 403 && error.message === 'Purchase required');
});

test('download keeps authentication and uses provider filename only after success', async () => {
  let clicked = false, revoked = false;
  const originalCreate = URL.createObjectURL, originalRevoke = URL.revokeObjectURL;
  const link = { remove() {}, click() { clicked = true; } };
  global.document = { createElement: () => link, body: { appendChild() {} } };
  URL.createObjectURL = () => 'blob:download'; URL.revokeObjectURL = () => { revoked = true; };
  global.fetch = async (url, options) => {
    calls.push({url,options});
    return new Response('source', {headers:{'Content-Disposition':'attachment; filename="workflow.json"'}});
  };
  try {
    await api.downloadAsset('paid');
    assert.equal(calls[0].options.headers.Authorization, undefined);
    assert.equal(calls[0].options.credentials, 'include');
    assert.equal(link.download, 'workflow.json'); assert.ok(clicked);
    await new Promise(resolve => setTimeout(resolve, 1100));
    assert.ok(revoked);
  } finally {
    URL.createObjectURL = originalCreate; URL.revokeObjectURL = originalRevoke;
    delete global.document;
  }
});

test('validation errors become readable messages', async () => {
  global.fetch = async () => Response.json({detail:[{msg:'Asset is required'}]}, {status:422});
  await assert.rejects(api.addItemToCollection('c','a'), /Asset is required/);
});

test('Dodo automatic connection sends only credentials and explicit mode', async () => {
  await api.connectSellerGateway({gateway_type: 'dodo', api_key: 'test-seller-key', environment: 'test'});
  assert.equal(calls[0].url, '/api/v1/sellers/connect');
  const payload = JSON.parse(calls[0].options.body);
  assert.equal(payload.environment, 'test');
  assert.equal(payload.webhook_secret, undefined);
  assert.equal(calls[0].options.headers.Authorization, undefined);
});

test('OAuth initiation and payment verification use authenticated same-origin requests', async () => {
  await api.startRazorpayConnect();
  await api.verifyPurchase('paid prompt', {payment_reference: 'saved-checkout', payment_id: 'pay_1', signature: 'test-signature'});
  assert.equal(calls[0].url, '/api/v1/sellers/razorpay/oauth/start');
  assert.equal(calls[0].options.method, 'POST');
  assert.equal(calls[0].options.credentials, 'include');
  assert.equal(calls[1].url, '/api/v1/assets/paid%20prompt/verify-payment');
  assert.equal(JSON.parse(calls[1].options.body).payment_reference, 'saved-checkout');
  assert.equal(calls[1].options.headers.Authorization, undefined);
});

test('subscription reconciliation checks current account without accepting a client subscription ID', async () => {
  await api.verifySubscription();
  assert.equal(calls[0].url, '/api/v1/billing/verify');
  assert.equal(calls[0].options.method, 'POST');
  assert.equal(calls[0].options.body, undefined);
  assert.equal(calls[0].options.headers.Authorization, undefined);
  assert.equal(calls[0].options.credentials, 'include');
});

test('checkout retains its key across network retries and reloads', async () => {
  const storage = new Map([['promptally_token', 'test-token']]);
  global.localStorage = {
    getItem: key => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key),
  };
  let fail = true;
  global.fetch = async (url, options) => {
    calls.push({url, options});
    if (fail) { fail = false; throw new TypeError('connection lost'); }
    return Response.json({status:'pending', order_id:'order_1'});
  };
  await assert.rejects(api.buyAssetDirect('retry-prompt'));
  await api.buyAssetDirect('retry-prompt');
  assert.ok(calls[0].options.headers['Idempotency-Key']);
  assert.equal(calls[0].options.headers['Idempotency-Key'], calls[1].options.headers['Idempotency-Key']);
  // Re-evaluate the module to simulate a page reload (the memory map is gone).
  const fresh = {};
  new Function('exports', 'require', compiled)(fresh, requireForApi);
  await fresh.api.buyAssetDirect('retry-prompt');
  assert.equal(calls[0].options.headers['Idempotency-Key'], calls[2].options.headers['Idempotency-Key']);
});

test('checkout keys are scoped to the signed-in buyer', async () => {
  const token = user => 'header.' + Buffer.from(JSON.stringify({sub:user})).toString('base64url') + '.signature';
  const storage = new Map([['promptally_token', token('buyer-a')]]);
  global.localStorage = {
    getItem: key => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, value),
    removeItem: key => storage.delete(key),
  };
  await api.createSubscription();
  setCheckoutOwner('buyer-b');
  await api.createSubscription();
  assert.notEqual(calls[0].options.headers['Idempotency-Key'], calls[1].options.headers['Idempotency-Key']);
});

test('every browser API request sends the device signal', async () => {
  await api.getMe();
  assert.equal(calls[0].options.headers['X-Device-Fingerprint'], 'browser-device-fingerprint');
});

test('verification posts the secret in the body and resend uses the authenticated client', async () => {
  await api.verifyEmail('a-secret-verification-token');
  assert.equal(calls[0].url, '/api/v1/auth/verify-email');
  assert.equal(JSON.parse(calls[0].options.body).token, 'a-secret-verification-token');
  await api.resendVerification();
  assert.equal(calls[1].url, '/api/v1/auth/resend-verification');
  assert.equal(calls[1].options.headers.Authorization, undefined);
});

test('429 exposes Retry-After for payment polling and a readable message', async () => {
  global.fetch = async () => Response.json({detail:'Rate limit exceeded.'}, {status:429, headers:{'Retry-After':'42'}});
  await assert.rejects(api.getMe(), error => error instanceof ApiError && error.status === 429
    && error.retryAfter === 42 && error.message.includes('42 seconds'));
});

test('Google sign-in starts with a browser challenge and returns only the credential plus CSRF binding', async () => {
  await api.startGoogleLogin();
  assert.equal(calls[0].url, '/api/v1/auth/google/start');
  assert.equal(calls[0].options.method, 'POST');
  assert.equal(JSON.parse(calls[0].options.body).device_fingerprint, 'browser-device-fingerprint');
  await api.googleAuth({credential:'google-id-token', csrf_token:'browser-csrf', device_fingerprint:'browser-device-fingerprint'});
  assert.equal(calls[1].url, '/api/v1/auth/google');
  assert.deepEqual(JSON.parse(calls[1].options.body), {
    credential:'google-id-token', csrf_token:'browser-csrf', device_fingerprint:'browser-device-fingerprint',
  });
  assert.equal(calls[1].options.credentials, 'include');
});
