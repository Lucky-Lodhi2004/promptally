"use client";
import { useState } from "react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

export function EmailVerificationBanner() {
  const { user, refreshUser } = useAuth();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  if (!user || user.email_verified) return null;
  const resend = async () => {
    setBusy(true);
    try { setMessage((await api.resendVerification()).message); }
    catch (error) { setMessage(error instanceof Error ? error.message : "Could not resend email."); }
    finally { setBusy(false); }
  };
  return <div role="status" className="border-b border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
    <p>{user.email_verification_required ? <>Check your inbox at <strong>{user.email}</strong> and verify your email to use your account.</> : <>Verify <strong>{user.email}</strong> to enable Google sign-in for your existing account.</>}</p>
    <div className="mt-2 flex flex-wrap gap-4">
      <button disabled={busy} onClick={resend} className="underline disabled:opacity-50">{busy ? "Queuing…" : "Resend verification email"}</button>
      <button onClick={() => { void refreshUser(); }} className="underline">I have verified my email</button>
    </div>
    {message && <p className="mt-2">{message}</p>}
  </div>;
}
