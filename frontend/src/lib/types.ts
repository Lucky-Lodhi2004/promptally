export type UserTier = "FREE" | "PRO" | "ADMIN";

export interface UserSummary {
  id: string | null;
  username: string;
  name: string;
  avatar_url: string;
}

export interface UserProfile {
  id: string;
  email: string;
  username: string;
  name: string;
  avatar_url: string | null;
  tier: UserTier;
  country_code: string;
  email_verified: boolean;
  email_verification_required: boolean;
  payouts_enabled: boolean;
  seller_payment_config: Record<string, any>;
  subscription: SubscriptionInfo | null;
}

export interface SubscriptionInfo {
  status: string;
  gateway: "razorpay" | "dodo" | "legacy";
  current_period_end: string;
  cancel_at_period_end: boolean;
  checkout_url?: string | null;
  currency: string;
  amount: number;
  subscription_id?: string | null;
  key_id?: string | null;
}

export interface TaxonomyCategory {
  id: string;
  slug: string;
  name: string;
  seo_title: string | null;
  seo_description: string | null;
  sort_order: number;
  item_count: number;
}

export interface TaxonomySection {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  icon_name: string | null;
  sort_order: number;
  item_count: number;
  /** First entry is the virtual "all" category. */
  categories: TaxonomyCategory[];
}

/** Shape returned by GET /taxonomy. */
export interface TaxonomyResponse {
  sections: TaxonomySection[];
  total_assets: number;
}

export interface AssetCard {
  id: string;
  slug: string;
  seo_title: string;
  short_description: string;
  asset_type: string;
  media_preview_url: string | null;
  gif_preview_url: string | null;
  reference_media: string[];
  author: UserSummary;
  is_paid: boolean;
  price_cents: number;
  price_usd: number;
  copy_count: number;
  download_count: number;
  is_indexable: boolean;
  canonical_path: string;
  section_slug: string | null;
  category_slug: string | null;
}

export interface AssetListResponse {
  items: AssetCard[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  section_slug?: string | null;
  subcategory_slug?: string | null;
}

export interface AssetDetail {
  id: string;
  slug: string;
  seo_title: string;
  short_description: string;
  tldr_summary: string | null;
  token_count: number;
  faq: Array<{ question: string; answer: string }>;
  section: { id: string; slug: string; name: string } | null;
  category: { id: string; slug: string; name: string } | null;
  asset_type: string;
  file_name: string;
  file_extension: string;
  source_license: string;
  source_type: string;
  source_repo_url?: string | null;
  media_preview_url: string | null;
  gif_preview_url: string | null;
  reference_media: string[];
  preview_media: Array<{
    url: string;
    kind: "image" | "gif" | "video";
  }>;
  file_previews: Array<{
    name: string;
    content: string;
  }>;
  preview_snippet: string | null;
  sample_output_markdown: string | null;
  usage_instructions: string | null;
  technical_metadata: Record<string, any>;
  variables_schema: Array<{
    name: string;
    description?: string;
    default_value?: string;
    default?: string;
    example?: string;
    required?: boolean;
  }>;
  related_artifacts: Array<{
    slug: string;
    title: string;
    section_slug: string;
  }>;
  is_paid: boolean;
  price_cents: number;
  price_usd: number;
  is_published: boolean;
  is_indexable: boolean;
  copy_count: number;
  download_count: number;
  view_count: number;
  created_at: string | null;
  updated_at: string | null;
  author: UserSummary;
  has_access: boolean;
  can_copy_download: boolean;
  raw_content?: string | null;
  prefilled_preview_text?: string | null;
  json_ld?: Record<string, any>;
}

export interface CollectionSummary {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  cover_image_url: string | null;
  visibility: "PUBLIC" | "PRIVATE";
  item_count: number;
  is_indexable: boolean;
  created_at: string | null;
}

export interface CollectionItem extends Omit<AssetCard, "id"> {
  id: string; // Collection-item ID; mutations use asset_id.
  asset_id: string;
  slug: string;
  seo_title: string;
  short_description: string;
  asset_type: string;
  media_preview_url: string | null;
  gif_preview_url: string | null;
  is_paid: boolean;
  price_usd: number;
  custom_note: string | null;
  sort_order: number;
  has_access: boolean;
  can_copy_download: boolean;
}

export interface CreateCollectionResponse {
  status: string;
  collection_id: string;
  slug: string;
  title: string;
  visibility: "PUBLIC" | "PRIVATE";
}

export interface ComparisonRow {
  name: string;
  modality: string;
  category?: string | null;
  use_case?: string;
  variables?: string[];
  approx_tokens?: number;
  access: string;
  url: string;
}

export interface CollectionDetail extends CollectionSummary {
  owner: UserSummary;
  items: CollectionItem[];
  comparison_matrix?: ComparisonRow[];
}

export interface SubscriptionState {
  is_pro: boolean;
  subscription: SubscriptionInfo | null;
}

export interface SellerGatewayStatus {
  razorpay_connected: boolean;
  dodo_connected: boolean;
  dodo_environment?: "test" | "live" | null;
  razorpay_oauth_available?: boolean;
  razorpay_connection_type?: "manual" | "oauth" | null;
  razorpay_environment?: "test" | "live" | null;
  dodo_webhook_managed?: boolean;
}

export interface DirectBuyResponse {
  gateway?: "razorpay" | "dodo";
  payment_reference: string;
  checkout_url?: string | null;
  seller_username: string;
  amount_usd: number;
  amount: number;
  currency: string;
  key_id?: string | null;
  order_id?: string | null;
  status: string;
}

export interface BillingQuote {
  country_code: string;
  gateway: "razorpay" | "dodo";
  currency: "INR" | "USD";
  amount: number;
  interval: "month";
  amount_unit: "minor";
}

export interface SubscribeResponse {
  gateway: "razorpay" | "dodo";
  currency: string;
  amount: number;
  country_code: string;
  subscription_id?: string | null;
  checkout_url?: string | null;
  key_id?: string | null;
  checkout_session_id?: string | null;
  status: string;
}

