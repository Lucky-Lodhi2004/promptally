"use client";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { loadGoogleIdentity, GoogleIdentity } from "@/lib/google-identity";

export function GoogleSignInButton({disabled, onBusy, onSuccess}: {disabled: boolean; onBusy: (busy: boolean) => void; onSuccess?: () => void}) {
  const { googleLogin } = useAuth();
  const container = useRef<HTMLDivElement>(null);
  const callbacks = useRef({googleLogin, onBusy, disabled, onSuccess});
  callbacks.current = {googleLogin, onBusy, disabled, onSuccess};
  const pending = useRef<Promise<[Awaited<ReturnType<typeof api.startGoogleLogin>>, GoogleIdentity]> | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const signingIn = useRef(false);

  useEffect(() => {
    let active = true;
    let expires: ReturnType<typeof setTimeout> | undefined;
    setReady(false); setError("");
    // Keep a single challenge across React Strict Mode's effect replay.
    pending.current ??= Promise.all([api.startGoogleLogin(), loadGoogleIdentity()]);
    pending.current.then(([challenge, identity]) => {
      if (!active || !container.current) return;
      identity.initialize({client_id: challenge.client_id, nonce: challenge.nonce, auto_select: false,
        ux_mode: "popup", cancel_on_tap_outside: true, callback: async (result) => {
          if (!active || signingIn.current || callbacks.current.disabled) return;
          signingIn.current = true; callbacks.current.onBusy(true); setError("");
          try {
            if (!result.credential) throw new Error("Google did not return a sign-in credential.");
            await callbacks.current.googleLogin(result.credential, challenge.csrf_token);
            callbacks.current.onSuccess?.();
          } catch (failure) {
            if (active) { setReady(false); setError(failure instanceof Error ? failure.message : "Google sign-in failed."); }
          } finally {
            signingIn.current = false; callbacks.current.onBusy(false);
          }
        }});
      container.current.replaceChildren();
      identity.renderButton(container.current, {type: "standard", theme: "outline", size: "large",
        text: "continue_with", shape: "rectangular", width: Math.min(container.current.offsetWidth || 320, 400), logo_alignment: "left"});
      setReady(true);
      expires = setTimeout(() => {
        if (active && !signingIn.current) { setReady(false); setError("Google sign-in session expired. Please retry."); }
      }, challenge.expires_in * 1000);
    }).catch(failure => { if (active) setError(failure instanceof Error ? failure.message : "Google sign-in is unavailable."); });
    return () => { active = false; if (expires) clearTimeout(expires); };
  }, [attempt]);

  return <div className="mb-5">
    <div ref={container} inert={!ready || disabled} aria-label="Continue with Google" className={!ready || disabled ? "pointer-events-none opacity-50" : ""} />
    {!ready && !error && <p role="status" className="py-3 text-center text-xs text-gray-500">Loading Google sign-in…</p>}
    {error && <div className="mt-2 text-xs text-red-700" role="alert">
      <p>{error}</p>
      <button type="button" disabled={disabled} onClick={() => { pending.current = null; setAttempt(value => value + 1); }}
        className="mt-2 underline disabled:opacity-50">Try Google again</button>
    </div>}
  </div>;
}
