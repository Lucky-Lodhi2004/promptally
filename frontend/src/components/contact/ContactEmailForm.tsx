"use client";

import { FormEvent, useState } from "react";
import { Mail, Send } from "lucide-react";

const CONTACT_EMAIL = "contact@promptally.dev";

export function ContactEmailForm() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [topic, setTopic] = useState("General question");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const emailSubject = `[${topic}] ${subject.trim() || "Promptally support request"}`;
    const emailBody = [
      `Name: ${name.trim()}`,
      `Reply email: ${email.trim()}`,
      `Topic: ${topic}`,
      "",
      message.trim(),
    ].join("\n");

    window.location.href = `mailto:${CONTACT_EMAIL}?subject=${encodeURIComponent(emailSubject)}&body=${encodeURIComponent(emailBody)}`;
  };

  return (
    <form onSubmit={handleSubmit} className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm sm:p-8">
      <div className="mb-6 flex items-start gap-3">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-amber-100 text-[#d66f0f]">
          <Mail className="h-5 w-5" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-gray-900">Write to our team</h2>
          <p className="mt-1 text-sm leading-relaxed text-gray-600">
            Complete the details below and we’ll prepare an email in your default mail app.
          </p>
        </div>
      </div>

      <div className="grid gap-5 sm:grid-cols-2">
        <label className="block text-sm font-semibold text-gray-800">
          Your name
          <input
            required
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            autoComplete="name"
            className="mt-2 w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-base font-normal text-gray-900 outline-none transition focus:border-[#f28c28] focus:ring-2 focus:ring-[#f28c28]/20"
            placeholder="How should we address you?"
          />
        </label>

        <label className="block text-sm font-semibold text-gray-800">
          Reply email
          <input
            required
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
            className="mt-2 w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-base font-normal text-gray-900 outline-none transition focus:border-[#f28c28] focus:ring-2 focus:ring-[#f28c28]/20"
            placeholder="you@example.com"
          />
        </label>

        <label className="block text-sm font-semibold text-gray-800">
          What can we help with?
          <select
            value={topic}
            onChange={(event) => setTopic(event.target.value)}
            className="mt-2 w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-base font-normal text-gray-900 outline-none transition focus:border-[#f28c28] focus:ring-2 focus:ring-[#f28c28]/20"
          >
            <option>General question</option>
            <option>Account or sign-in</option>
            <option>Payment or subscription</option>
            <option>Seller Studio or payouts</option>
            <option>Publishing a blueprint</option>
            <option>Technical problem</option>
            <option>Report content</option>
          </select>
        </label>

        <label className="block text-sm font-semibold text-gray-800">
          Subject
          <input
            required
            type="text"
            value={subject}
            onChange={(event) => setSubject(event.target.value)}
            className="mt-2 w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-base font-normal text-gray-900 outline-none transition focus:border-[#f28c28] focus:ring-2 focus:ring-[#f28c28]/20"
            placeholder="A short summary"
          />
        </label>
      </div>

      <label className="mt-5 block text-sm font-semibold text-gray-800">
        How can we help?
        <textarea
          required
          value={message}
          onChange={(event) => setMessage(event.target.value)}
          rows={6}
          className="mt-2 w-full resize-y rounded-xl border border-gray-300 bg-white px-4 py-3 text-base font-normal leading-relaxed text-gray-900 outline-none transition focus:border-[#f28c28] focus:ring-2 focus:ring-[#f28c28]/20"
          placeholder="Describe the query or problem, what you expected, and what happened."
        />
      </label>

      <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-xs leading-relaxed text-gray-500">
          This button opens your email app. Your message is not stored on this page.
        </p>
        <button
          type="submit"
          className="inline-flex min-h-12 shrink-0 items-center justify-center gap-2 rounded-xl bg-[#f28c28] px-6 py-3 text-sm font-bold text-white shadow-sm transition hover:bg-[#d66f0f] focus:outline-none focus:ring-2 focus:ring-[#f28c28] focus:ring-offset-2"
        >
          <Send className="h-4 w-4" />
          Prepare email
        </button>
      </div>
    </form>
  );
}
