import React from "react";
import Link from "next/link";
import { CATEGORIES } from "@/lib/constants";
import { hubPath } from "@/lib/site";

interface SubcategoryStripProps {
  currentSectionSlug: string;
  currentSubcategorySlug: string;
}

/** Server-rendered: every subcategory is a real <a href> that crawlers can follow. */
export function SubcategoryStrip({
  currentSectionSlug,
  currentSubcategorySlug,
}: SubcategoryStripProps) {
  const currentCategory =
    CATEGORIES.find((c) => c.slug === currentSectionSlug) || CATEGORIES[0];

  return (
    <div className="bg-[#f7f8f8] border-b border-[#dededf] py-2.5 px-4 sm:px-8">
      <div className="max-w-[1600px] mx-auto flex min-w-0 items-center gap-4">
        {/* Category Description Banner Pill */}
        <div className="hidden xl:flex items-center gap-2 pr-4 border-r border-gray-200 flex-shrink-0">
          <span className="text-[15px] font-bold text-[#55565a]">
            {currentCategory.name}
          </span>
        </div>

        {/* Subcategories Horizontal Scroll */}
        <nav
          className="subcategory-scroll flex min-w-0 flex-1 items-center gap-1.5 overflow-x-auto scroll-smooth py-1.5"
          aria-label={`${currentCategory.name} subcategories`}
        >
          {currentCategory.subcategories.map((sub) => {
            const isSubActive =
              currentSubcategorySlug === sub.slug ||
              (!currentSubcategorySlug && sub.slug === "all");

            return (
              <Link
                key={sub.slug}
                href={hubPath(currentCategory.slug, sub.slug)}
                title={sub.description}
                aria-current={isSubActive ? "page" : undefined}
                className={`flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded px-3 py-1.5 text-sm font-bold transition-all ${
                  isSubActive
                    ? "bg-[#f4b56a] text-white"
                    : "bg-transparent text-[#68686c] border border-transparent hover:border-[#f4b56a] hover:text-[#444447] hover:bg-white"
                }`}
              >
                <span>{sub.name}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
