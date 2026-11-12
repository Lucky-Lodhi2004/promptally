import { getDeviceFingerprint } from "./fingerprint";
import {
  AssetDetail,
  AssetListResponse,
  BillingQuote,
  CollectionDetail,
  CollectionSummary,
  CreateCollectionResponse,
  SubscriptionState,
  DirectBuyResponse,
  TaxonomyResponse,
  SellerGatewayStatus,
  SubscribeResponse,
  UserProfile,
} from "./types";

// Browser requests stay on this origin; Next proxies them to the private API.
const API_BASE_URL = "/api/v1";

type RequestOptions = RequestInit;

export class ApiError extends Error {
  status: number;
  data: any;
  retryAfter: number;

  constructor(status: number, message: string, data?: any, retryAfter = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.retryAfter = retryAfter;
  }
}

async function fetchResponse(endpoint: string, options: RequestOptions = {}): Promise<Response> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (typeof window !== "undefined") {
    headers["X-Device-Fingerprint"] = await getDeviceFingerprint();
  }

  // Auto-detect JSON payload unless FormData is passed
  const isFormData = options.body instanceof FormData;
  if (!isFormData && options.body && typeof options.body === "object") {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(options.body);
  }

  const res = await fetch(url, {
    cache: "no-store",
    ...options,
    headers,
    credentials: "include", // send cookies
  });

  if (!res.ok) {
    let errorDetail = `Request failed with status ${res.status}`;
    let data: any = null;
    try {
      data = await res.json();
      if (data && typeof data === "object") {
        const detail = data.detail || data.message;
        if (Array.isArray(detail)) {
          errorDetail = detail.map((item: { msg?: string }) => item.msg || "Invalid input").join("; ");
        } else if (typeof detail === "string") errorDetail = detail;
      }
    } catch {
      // ignore JSON parse failure on non-JSON error pages
    }
    const retryAfter = Math.max(0, Number(res.headers.get("Retry-After")) || 0);
    if (res.status === 429 && retryAfter) errorDetail += ` Try again in ${retryAfter} seconds.`;
    throw new ApiError(res.status, errorDetail, data, retryAfter);
  }

  return res;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const res = await fetchResponse(endpoint, options);
  return res.status === 204 ? ({} as T) : res.json();
}

// Persist one key per authenticated buyer/action across retries and reloads.
// PostgreSQL also prevents duplicate attempts when separate tabs generate keys.
let checkoutOwner = "anonymous";
export function setCheckoutOwner(userId: string | null) {
  checkoutOwner = userId || "anonymous";
}
function checkoutStorageKey(action: string): string {
  return `promptally_checkout_key:${checkoutOwner}:${action}`;
}

const checkoutKeys = new Map<string, string>();
function clearCheckoutKey(action: string) {
  const name = checkoutStorageKey(action);
  checkoutKeys.delete(name);
  try { localStorage.removeItem(name); } catch { /* storage may be unavailable */ }
}

async function checkoutRequest<T>(endpoint: string, action: string): Promise<T> {
  const name = checkoutStorageKey(action);
  let key = checkoutKeys.get(name);
  try { key = localStorage.getItem(name) || key; } catch { /* use memory fallback */ }
  if (!key) {
    key = crypto.randomUUID();
    checkoutKeys.set(name, key);
    try { localStorage.setItem(name, key); } catch { /* use memory fallback */ }
  }
  try {
    return await request<T>(endpoint, {method: "POST", headers: {"Idempotency-Key": key}});
  } catch (error) {
    // Keep the key on timeouts, conflicts and server errors: outcome may be unknown.
    if (error instanceof ApiError && [400, 401, 403, 404, 422].includes(error.status)) clearCheckoutKey(action);
    throw error;
  }
}

async function assetText(slug: string, action: "copy" | "markdown" = "copy") {
  const path = action === "markdown" ? `/assets/${encodeURIComponent(slug)}.md` : `/assets/${encodeURIComponent(slug)}/download?action=copy`;
  const res = await fetchResponse(path, { headers: { Accept: action === "markdown" ? "text/markdown" : "text/plain" } });
  return res.text();
}

async function downloadAsset(slug: string) {
  const res = await fetchResponse(`/assets/${encodeURIComponent(slug)}/download`);
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const encoded = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
  const plain = disposition.match(/filename="([^"]+)"/i)?.[1];
  let filename = plain || slug;
  if (encoded) { try { filename = decodeURIComponent(encoded); } catch { /* use fallback */ } }
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const api = {
  // 1. Taxonomy & Catalog
  getTaxonomy: () => request<TaxonomyResponse>("/taxonomy"),

  getAssets: (params: {
    section?: string;
    subcategory?: string;
    q?: string;
    pricing?: "all" | "free" | "paid";
    sort?: "popular" | "downloads" | "newest";
    page?: number;
    page_size?: number;
  }) => {
    const searchParams = new URLSearchParams();
    if (params.section) searchParams.set("section", params.section);
    if (params.subcategory) searchParams.set("subcategory", params.subcategory);
    if (params.q) searchParams.set("q", params.q);
    if (params.pricing) searchParams.set("pricing", params.pricing);
    if (params.sort) searchParams.set("sort", params.sort);
    if (params.page) searchParams.set("page", params.page.toString());
    if (params.page_size) searchParams.set("page_size", params.page_size.toString());
    return request<AssetListResponse>(`/assets?${searchParams.toString()}`);
  },

  // `countView` is true only for the first load of a page in the browser, so polling,
  // refreshes and server renders never inflate the view counter.
  getAssetDetail: (slug: string, countView = false) =>
    request<AssetDetail>(`/assets/${slug}${countView ? "?view=1" : ""}`),

  getAssetMarkdown: (slug: string) => assetText(slug, "markdown"),
  copyAsset: (slug: string) => assetText(slug),
  downloadAsset,

  downloadAssetUrl: (slug: string, action: "download" | "copy" = "download") =>
    `${API_BASE_URL}/assets/${slug}/download?action=${action}`,

  uploadAsset: (formData: FormData) =>
    request<{
      status: string;
      asset_id: string;
      slug: string;
      url: string;
      is_paid: boolean;
      price_usd: number;
      author_username: string;
    }>("/assets", {
      method: "POST",
      body: formData,
    }),

  deleteAsset: (assetId: string) =>
    request<{ status: string; message: string }>(`/assets/${assetId}`, {
      method: "DELETE",
    }),

  // 2. Collections
  getCollections: () => request<CollectionSummary[]>("/collections"),

  createCollection: (formData: FormData) =>
    request<CreateCollectionResponse>("/collections", {
      method: "POST",
      body: formData,
    }),

  getCollectionDetail: (slug: string) =>
    request<CollectionDetail>(`/collections/${slug}`),

  addItemToCollection: (collectionId: string, assetId: string) => {
    const form = new FormData();
    form.append("asset_id", assetId);
    return request<{ status: string; message: string }>(`/collections/${collectionId}/items`, {
      method: "POST", body: form,
    });
  },

  removeItemFromCollection: (collectionId: string, assetId: string) =>
    request<{ status: string; message: string }>(
      `/collections/${collectionId}/items/${assetId}`,
      {
        method: "DELETE",
      }
    ),

  // 3. User & Authentication
  signup: (payload: {
    email: string;
    password: string;
    name?: string;
    device_fingerprint?: string;
  }) =>
    request<{ access_token: string; token_type: string; user: any }>(
      "/auth/signup",
      {
        method: "POST",
        body: payload as any,
      }
    ),

  login: (payload: { email: string; password: string }) =>
    request<{ access_token: string; token_type: string; user: any }>(
      "/auth/login",
      {
        method: "POST",
        body: payload as any,
      }
    ),

  verifyEmail: (token: string) => request<{status: string; message: string}>("/auth/verify-email", {
    method: "POST", body: {token} as any,
  }),

  resendVerification: () => request<{status: string; message: string}>("/auth/resend-verification", {method: "POST"}),

  startGoogleLogin: async () => request<{client_id: string; nonce: string; csrf_token: string; expires_in: number}>(
    "/auth/google/start", {method: "POST", body: {device_fingerprint: await getDeviceFingerprint()} as any}),

  googleAuth: (payload: { credential: string; csrf_token: string; device_fingerprint?: string }) =>
    request<{ access_token: string; token_type: string; user: any }>(
      "/auth/google",
      {
        method: "POST",
        body: payload as any,
      }
    ),

  logout: () =>
    request<{ status: string; message: string }>("/auth/logout", {
      method: "POST",
    }),

  getMe: () => request<UserProfile>("/users/me"),

  updateProfile: (formData: FormData) =>
    request<UserProfile>("/users/me", {
      method: "PATCH",
      body: formData,
    }),

  changePassword: (payload: { current_password: string; new_password: string }) =>
    request<{ status: string; message: string }>("/users/me/password", {
      method: "POST",
      body: payload as any,
    }),

  // 4. Platform Subscription ($1/month)
  getBillingQuote: () => request<BillingQuote>("/billing/quote"),

  createSubscription: () =>
    checkoutRequest<SubscribeResponse>("/billing/subscribe", "subscription"),

  getSubscription: async () => {
    const state = await request<SubscriptionState>("/billing/subscription");
    if (state.subscription && state.subscription.status !== "PENDING") clearCheckoutKey("subscription");
    return state;
  },

  verifySubscription: () =>
    request<SubscriptionState>("/billing/verify", {method: "POST"}),

  cancelSubscription: () =>
    request<{ status: string; message: string }>("/billing/cancel", {
      method: "POST",
    }),

  // 5. Direct-to-Seller Marketplace (BYOG 0% cut)
  getSellerGateways: () => request<SellerGatewayStatus>("/sellers/gateways"),

  connectSellerGateway: (payload: {
    gateway_type: "razorpay" | "dodo";
    key_id?: string;
    key_secret?: string;
    api_key?: string;
    webhook_secret?: string;
    environment?: "test" | "live";
  }) =>
    request<SellerGatewayStatus & {status: string; webhook_url: string}>("/sellers/connect", {
      method: "POST",
      body: payload as any,
    }),

  startRazorpayConnect: () => request<{authorization_url: string}>("/sellers/razorpay/oauth/start", {method: "POST"}),

  verifyPurchase: (slug: string, payload: {payment_reference: string; payment_id?: string; signature?: string}) =>
    request<{status: string; unlocked: boolean}>(`/assets/${encodeURIComponent(slug)}/verify-payment`, {
      method: "POST", body: payload as any,
    }),

  buyAssetDirect: (slug: string) =>
    checkoutRequest<DirectBuyResponse>(`/assets/${encodeURIComponent(slug)}/buy`, `purchase:${slug}`),

  // 6. Admin Panel
  getAdminUsers: (params: { status?: "all" | "subscribed"; page?: number; page_size?: number }) => {
    const searchParams = new URLSearchParams();
    if (params.status) searchParams.set("status", params.status);
    if (params.page) searchParams.set("page", params.page.toString());
    if (params.page_size) searchParams.set("page_size", params.page_size.toString());
    return request<any>(`/admin/users?${searchParams.toString()}`);
  },
};

