"use client";

import React from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { CATEGORIES } from "@/lib/constants";

export function Navbar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();

  // Determine currently active section
  let activeSection = "prompts";
  if (pathname.startsWith("/directory/")) {
    const parts = pathname.split("/");
    activeSection = parts[2] || "prompts";
  } else if (searchParams.get("section")) {
    activeSection = searchParams.get("section")!;
  }


  return (
    <header className="bg-white border-b border-[#e5e5e5] sticky top-0 z-40">
      <div className="h-[86px] px-5 sm:px-9 flex items-center justify-between gap-8">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-3 flex-shrink-0 group" aria-label="Promptally home">
          <div className="w-12 h-11 flex items-center justify-center transition-transform group-hover:scale-105">
            <svg
              aria-hidden="true"
              className="w-12 h-12"
              viewBox="0 0 72 68"
              fill="none"
            >
              <path
                d="M29 6h-6c-7 0-9 4-9 10v5c0 4-2 7-7 7 5 0 7 3 7 7v5c0 6 2 10 9 10h6"
                stroke="#ffaa3d"
                strokeWidth="7"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <path
                d="M43 18h6c7 0 9 4 9 10v5c0 4 2 7 7 7-5 0-7 3-7 7v5c0 6-2 10-9 10h-6"
                stroke="#e47a14"
                strokeWidth="7"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          <span className="text-[27px] font-light tracking-[-0.035em] text-[#4b4b4d] group-hover:text-[#f28c28] transition-colors">promptally</span>
        </Link>

        {/* 8 Categories Navigation Bar */}
        <nav aria-label="Main Navigation" className="hidden xl:flex h-full flex-1 items-center justify-end gap-2 overflow-x-auto scrollbar-none">
          {CATEGORIES.map((cat) => {
            const isActive = activeSection === cat.slug;
            return (
              <Link
                key={cat.slug}
                href={`/directory/${cat.slug}`}
                aria-current={isActive ? "page" : undefined}
                className={`relative flex h-10 items-center rounded px-3 text-[14px] font-bold text-white whitespace-nowrap shadow-sm transition-colors ${
                  isActive
                    ? "bg-[#e47a14]"
                    : "bg-[#f28c28] hover:bg-[#d66f0f]"
                }`}
              >
                <span>{cat.name}</span>
              </Link>
            );
          })}
        </nav>

        {/* Mobile Category Trigger / Search */}
        <div className="flex items-center space-x-2 xl:hidden">
          <Link
            href="/directory"
            className="text-sm font-bold text-white bg-[#f28c28] hover:bg-[#d66f0f] px-4 py-2 rounded transition-colors"
          >
            Browse Categories
          </Link>
        </div>
      </div>
    </header>
  );
}

