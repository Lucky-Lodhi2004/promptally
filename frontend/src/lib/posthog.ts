"use client";

import posthog from "posthog-js";
import type { UserProfile } from "@/lib/types";

let initialized = false;

export function initPostHog(): boolean {
  if (typeof window === "undefined") return false;
  const apiKey = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  if (!apiKey) return false;
  if (!initialized) {
    const uiHost = (process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com")
      .replace(".i.posthog.com", ".posthog.com");
    posthog.init(apiKey, {
      api_host: "/ingest",
      ui_host: uiHost,
      persistence: "localStorage+cookie",
      cross_subdomain_cookie: true,
      capture_pageview: false,
      capture_pageleave: true,
      disable_session_recording: true,
      person_profiles: "identified_only",
    });
    initialized = true;
  }
  return true;
}

export function captureEvent(event: string, properties?: Record<string, unknown>): void {
  if (!initPostHog()) return;
  posthog.capture(event, properties);
}

export function identifyUser(user: UserProfile): void {
  if (!initPostHog()) return;
  posthog.identify(user.id, {
    username: user.username,
    tier: user.tier,
    country_code: user.country_code,
    email_verified: user.email_verified,
    payouts_enabled: user.payouts_enabled,
  });
}

export function resetPostHog(): void {
  if (typeof window === "undefined" || !initialized) return;
  posthog.reset();
}

