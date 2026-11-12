import type { Metadata } from "next";
import Link from "next/link";
import { CircleHelp, CreditCard, Mail, ShieldAlert, Store, Wrench } from "lucide-react";
import { ContactEmailForm } from "@/components/contact/ContactEmailForm";

const CONTACT_EMAIL = "contact@promptally.dev";

export const metadata: Metadata = {
  title: "Contact Us — Promptally",
  description: "Contact the Promptally team for account, payment, seller, publishing, or technical support.",
};

const supportAreas = [
  {
    icon: CircleHelp,
    title: "Account & access",
    description: "Sign-in, verification, profile, collections, and account settings.",
  },
  {
    icon: CreditCard,
    title: "Payments & Pro",
    description: "Subscriptions, purchase confirmations, billing, and payment questions.",
  },
  {
    icon: Store,
    title: "Selling & publishing",
    description: "Seller Studio, payment gateways, payouts, and blueprint publishing.",
  },
  {
    icon: Wrench,
    title: "Technical support",
    description: "Broken pages, downloads, unexpected errors, and product feedback.",
  },
];

export default function ContactPage() {
  return (
    <div className="min-h-[calc(100vh-130px)] bg-gray-50">
      <section className="border-b border-gray-200 bg-[#fff8ef] px-5 py-14 sm:px-8 sm:py-18">
        <div className="mx-auto max-w-4xl text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-[#f28c28] text-white shadow-sm">
            <Mail className="h-7 w-7" />
          </div>
          <p className="mt-5 text-sm font-bold uppercase tracking-[0.16em] text-[#d66f0f]">Promptally support</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">How can we help?</h1>
          <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-gray-600 sm:text-lg">
            Send us your questions, report a problem, or ask for help with your Promptally account and marketplace activity.
          </p>
          <a
            href={`mailto:${CONTACT_EMAIL}`}
            className="mt-6 inline-flex items-center gap-2 rounded-full border border-amber-300 bg-white px-5 py-2.5 text-base font-bold text-[#d66f0f] shadow-sm transition hover:border-[#f28c28] hover:text-[#b85b08]"
          >
            <Mail className="h-4 w-4" />
            {CONTACT_EMAIL}
          </a>
        </div>
      </section>

      <main className="mx-auto max-w-6xl px-5 py-10 sm:px-8 sm:py-14">
        <div className="grid gap-8 lg:grid-cols-[0.82fr_1.18fr] lg:items-start">
          <div className="space-y-6">
            <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-bold text-gray-900">Support for every part of Promptally</h2>
              <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
                {supportAreas.map(({ icon: Icon, title, description }) => (
                  <div key={title} className="flex gap-3 rounded-xl border border-gray-100 bg-gray-50 p-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-100 text-[#d66f0f]">
                      <Icon className="h-5 w-5" />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-gray-900">{title}</h3>
                      <p className="mt-1 text-sm leading-relaxed text-gray-600">{description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="rounded-2xl border border-amber-200 bg-amber-50 p-6">
              <div className="flex gap-3">
                <ShieldAlert className="mt-0.5 h-5 w-5 shrink-0 text-[#d66f0f]" />
                <div>
                  <h2 className="text-base font-bold text-gray-900">Help us resolve it faster</h2>
                  <p className="mt-2 text-sm leading-relaxed text-gray-700">
                    Include your Promptally username, the affected page or blueprint, and any payment reference relevant to the issue.
                  </p>
                  <p className="mt-3 text-sm font-semibold text-gray-900">
                    Never email passwords, API keys, card details, or recovery codes.
                  </p>
                </div>
              </div>
            </section>
          </div>

          <ContactEmailForm />
        </div>

        <div className="mt-10 text-center text-sm text-gray-600">
          Prefer writing directly? Email{" "}
          <a className="font-bold text-[#d66f0f] hover:underline" href={`mailto:${CONTACT_EMAIL}`}>
            {CONTACT_EMAIL}
          </a>
          . You can also return to the{" "}
          <Link href="/" className="font-bold text-[#d66f0f] hover:underline">Promptally homepage</Link>.
        </div>
      </main>
    </div>
  );
}
