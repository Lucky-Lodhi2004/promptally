"use client";

import { useEffect, useRef } from "react";
import Link from "next/link";
import { ChevronDown } from "lucide-react";
import { CATEGORIES } from "@/lib/constants";

const DROPDOWN_SELECTOR = "details[data-category-dropdown]";

export function CategoryDropdowns() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const closeDropdownsExcept = (except: HTMLDetailsElement | null = null) => {
      rootRef.current?.querySelectorAll<HTMLDetailsElement>(DROPDOWN_SELECTOR).forEach((dropdown) => {
        if (dropdown !== except) dropdown.open = false;
      });
    };

    const handlePointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const clickedDropdown = target.closest<HTMLDetailsElement>(DROPDOWN_SELECTOR);
      closeDropdownsExcept(clickedDropdown);
    };

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const openDropdown = rootRef.current?.querySelector<HTMLDetailsElement>(`${DROPDOWN_SELECTOR}[open]`);
      if (!openDropdown) return;
      closeDropdownsExcept();
      openDropdown.querySelector<HTMLElement>("summary")?.focus();
    };

    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, []);

  return (
    <div ref={rootRef} className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {CATEGORIES.map((section) => (
        <details key={section.slug} name="directory-category" data-category-dropdown className="group relative">
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 rounded-lg border border-[#dedee0] bg-white px-4 py-3 text-[15px] font-bold text-[#55565a] shadow-sm transition-colors hover:border-[#f4b56a] hover:text-[#d66f0f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f4b56a] [&::-webkit-details-marker]:hidden">
            <span>{section.name}</span>
            <ChevronDown aria-hidden="true" className="h-4 w-4 shrink-0 text-[#8a8a8d] transition-transform duration-200 group-open:rotate-180" />
          </summary>

          <div className="absolute left-0 right-0 top-[calc(100%+0.4rem)] z-20 rounded-lg border border-[#dedee0] bg-white p-2 shadow-[0_12px_32px_rgba(0,0,0,0.14)]">
            <ul className="max-h-80 space-y-0.5 overflow-y-auto" aria-label={`${section.name} categories`}>
              {section.subcategories.map((sub) => (
                <li key={sub.slug}>
                  <Link
                    href={sub.slug === "all" ? `/directory/${section.slug}` : `/directory/${section.slug}/${sub.slug}`}
                    className="block rounded-md px-3 py-2.5 text-[14px] font-medium leading-snug text-[#66676a] transition-colors hover:bg-[#fff3e2] hover:text-[#d66f0f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f4b56a]"
                  >
                    {sub.name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        </details>
      ))}
    </div>
  );
}
