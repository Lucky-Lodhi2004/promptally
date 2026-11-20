"use client";

import { useEffect, useState } from "react";
import { GoogleSignInButton } from "@/components/auth/GoogleSignInButton";
import { useAuth } from "@/context/AuthContext";

type Details = { client_name: string; redirect_uri: string; scope: string; resource: string };

export default function MCPConsent() {
  const { user } = useAuth();
  const [handle, setHandle] = useState("");
  const [details, setDetails] = useState<Details | null>(null);
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const request = new URLSearchParams(window.location.search).get("request") || "";
    if (!request) { setError("Start this connection from your MCP client."); return; }
    setHandle(request);
    fetch(`/api/v1/oauth/requests/${encodeURIComponent(request)}`, { credentials: "include", cache: "no-store" })
      .then(async response => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "This connection request is unavailable.");
        if (active) setDetails(data);
      }).catch(failure => { if (active) setError(failure.message); });
    return () => { active = false; };
  }, []);

  async function decide(approved: boolean) {
    setBusy(true); setError("");
    try {
      const response = await fetch(`/api/v1/oauth/requests/${encodeURIComponent(handle)}`, {
        method: "POST", credentials: "include", cache: "no-store",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ approved }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not authorize this connection.");
      window.location.assign(data.redirect_url);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not connect.");
      setBusy(false);
    }
  }

  return <section className="mx-auto my-12 max-w-lg rounded-xl border border-gray-200 bg-white p-8">
    <h1 className="mb-4 text-2xl font-bold">Connect to Promptally</h1>
    {!details && !error && <p role="status">Loading connection request…</p>}
    {details && <>
      <p className="mb-4"><strong className="break-words">{details.client_name}</strong> wants to use Promptally on your behalf.</p>
      <p className="mb-4 text-sm text-gray-600">This connection can search the directory, read free resources, and preview paid listings. It cannot publish, change your account, or unlock paid content.</p>
      <p className="mb-5 break-all text-sm text-gray-600">You will return to: <strong>{details.redirect_uri}</strong></p>
      {new URL(details.redirect_uri).protocol === "http:" && <p className="mb-5 text-sm text-amber-800">This callback goes to an application running on your computer. Continue only if you started this connection there.</p>}
      {!signedIn && <GoogleSignInButton disabled={busy} onBusy={setBusy} onSuccess={() => setSignedIn(true)} />}
      {signedIn && user && <p className="mb-4 text-sm">Signed in as {user.email}.</p>}
      <div className="flex gap-3">
        <button disabled={busy || !signedIn || !user} onClick={() => decide(true)}
          className="rounded bg-orange-500 px-5 py-3 text-white disabled:opacity-50">{busy ? "Please wait…" : "Allow connection"}</button>
        <button disabled={busy} onClick={() => decide(false)} className="rounded border px-5 py-3 disabled:opacity-50">Cancel</button>
      </div>
    </>}
    {error && <p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}
  </section>;
}
