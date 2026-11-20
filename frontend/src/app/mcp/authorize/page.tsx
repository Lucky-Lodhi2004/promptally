import type { Metadata } from "next";
import MCPConsent from "./MCPConsent";

export const metadata: Metadata = {
  title: "Connect to Promptally",
  robots: { index: false, follow: false },
  referrer: "no-referrer",
};

export default function MCPAuthorizePage() {
  return <MCPConsent />;
}
