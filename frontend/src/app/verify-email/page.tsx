"use client";
import { useEffect, useState, useRef } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import Link from "next/link";

export default function VerifyEmailPage() {
  const { refreshUser, openAuthModal } = useAuth();
  const initialized = useRef(false);
  const [token, setToken] = useState("");
  const [busy, setBusy] = useState(false);
  const [verified, setVerified] = useState(false);
  const [message, setMessage] = useState("");
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    const value = new URLSearchParams(window.location.hash.slice(1)).get("token") || "";
    setToken(value);
    // Keep the token in component memory, out of history and referrers.
    window.history.replaceState(null, "", window.location.pathname);
    if (!value) setMessage("Open the verification link from your email. You can request another email while signed in.");
  }, []);
  const verify = async () => {
    setBusy(true);
    try {
      const result = await api.verifyEmail(token);
      setMessage(result.message); setVerified(true); setToken("");
      await refreshUser();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not verify your email."); }
    finally { setBusy(false); }
  };
  return <section className="mx-auto my-16 max-w-lg rounded-xl border p-8">
    <h1 className="mb-4 text-2xl font-bold">Verify your email</h1>
    {!verified && token && <>
      <p className="mb-4">Confirm your email address to finish setting up your Promptally account.</p>
      <button disabled={busy} onClick={verify} className="rounded bg-orange-500 px-5 py-3 text-white disabled:opacity-50">{busy ? "Verifying…" : "Verify email address"}</button>
    </>}
    {message && <p role="status" className="my-4">{message}</p>}
    {verified && <div className="flex gap-4"><Link href="/dashboard" className="underline">Continue to dashboard</Link><button onClick={() => openAuthModal("login")} className="underline">Sign in</button></div>}
  </section>;
}
