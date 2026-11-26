"use client";

import { Suspense, useEffect, useRef } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import { captureEvent, identifyUser, initPostHog } from "@/lib/posthog";

function PostHogPageviewAndIdentity() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { user, loading } = useAuth();
  const lastIdentifiedRef = useRef<string | null>(null);

  useEffect(() => {
    initPostHog();
  }, []);

  useEffect(() => {
    if (!pathname) return;
    const qs = searchParams.toString();
    const currentUrl = `${window.location.origin}${pathname}${qs ? `?${qs}` : ""}`;
    captureEvent("$pageview", { $current_url: currentUrl });
  }, [pathname, searchParams]);

  useEffect(() => {
    if (loading) return;
    if (user) {
      const fingerprint = `${user.id}:${user.tier}:${user.email_verified}:${user.payouts_enabled}`;
      if (lastIdentifiedRef.current !== fingerprint) {
        identifyUser(user);
        lastIdentifiedRef.current = fingerprint;
      }
    } else {
      lastIdentifiedRef.current = null;
    }
  }, [user, loading]);

  return null;
}

export function PostHogProvider({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Suspense fallback={null}>
        <PostHogPageviewAndIdentity />
      </Suspense>
      {children}
    </>
  );
}

