/**
 * Lightweight, zero-dependency browser fingerprinting.
 * Combines canvas drawing hash, screen resolution, timezone, color depth,
 * and navigator metadata to produce a stable device fingerprint.
 * An abuse signal, not proof of a physical device identity.
 */
async function computeFingerprint(): Promise<string> {
  if (typeof window === "undefined") {
    return "server-render-fingerprint";
  }

  try {
    const components: string[] = [
      navigator.userAgent || "",
      navigator.language || "",
      new Intl.DateTimeFormat().resolvedOptions().timeZone || "",
      screen.width + "x" + screen.height + "x" + screen.colorDepth,
      navigator.hardwareConcurrency?.toString() || "",
      (navigator as any).deviceMemory?.toString() || "",
    ];

    // Canvas fingerprinting
    const canvas = document.createElement("canvas");
    canvas.width = 200;
    canvas.height = 50;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.textBaseline = "top";
      ctx.font = "14px 'Arial', sans-serif";
      ctx.textBaseline = "alphabetic";
      ctx.fillStyle = "#f60";
      ctx.fillRect(125, 1, 62, 20);
      ctx.fillStyle = "#069";
      ctx.fillText("Promptally-Secure-Device-Gate", 2, 15);
      ctx.fillStyle = "rgba(102, 204, 0, 0.7)";
      ctx.fillText("Promptally-Secure-Device-Gate", 4, 17);
      components.push(canvas.toDataURL());
    }

    const rawString = components.join("###");
    // Subtle crypto SHA-256
    const msgBuffer = new TextEncoder().encode(rawString);
    const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  } catch {
    // Fallback if canvas/subtle crypto is blocked
    const fallback = [
      navigator.userAgent,
      screen.width,
      screen.height,
      new Date().getTimezoneOffset(),
    ].join("_");
    let hash = 0;
    for (let i = 0; i < fallback.length; i++) {
      hash = (hash << 5) - hash + fallback.charCodeAt(i);
      hash |= 0;
    }
    return "fallback_" + Math.abs(hash).toString(16);
  }
}


let fingerprintPromise: Promise<string> | null = null;
export function getDeviceFingerprint(): Promise<string> {
  if (typeof window === "undefined") return Promise.resolve("server-render-fingerprint");
  return fingerprintPromise ??= computeFingerprint();
}
