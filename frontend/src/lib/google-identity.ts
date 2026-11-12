export interface GoogleCredentialResponse { credential: string }
export interface GoogleIdentity {
  initialize(options: {client_id: string; nonce: string; callback: (response: GoogleCredentialResponse) => void;
    auto_select: boolean; ux_mode: "popup"; cancel_on_tap_outside: boolean}): void;
  renderButton(element: HTMLElement, options: {type: "standard"; theme: "outline"; size: "large";
    text: "continue_with"; shape: "rectangular"; width: number; logo_alignment: "left"}): void;
  cancel(): void;
  disableAutoSelect(): void;
}

declare global { interface Window { google?: { accounts: { id: GoogleIdentity } } } }
let loading: Promise<GoogleIdentity> | null = null;

export function loadGoogleIdentity(): Promise<GoogleIdentity> {
  if (window.google?.accounts.id) return Promise.resolve(window.google.accounts.id);
  if (loading) return loading;
  loading = new Promise<GoogleIdentity>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    const timer = window.setTimeout(() => fail(), 15000);
    const fail = () => {
      window.clearTimeout(timer); script.remove(); loading = null;
      reject(new Error("Google sign-in could not load. Check your connection or content blocker and retry."));
    };
    script.onload = () => {
      window.clearTimeout(timer);
      const identity = window.google?.accounts.id;
      if (identity) resolve(identity); else fail();
    };
    script.onerror = fail;
    document.head.appendChild(script);
  });
  return loading;
}
