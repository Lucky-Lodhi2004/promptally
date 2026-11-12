"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Compass,
  FolderHeart,
  BadgeDollarSign,
  Briefcase,
  User,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";

export function Sidebar() {
  const pathname = usePathname();
  const { isPro } = useAuth();
  const [isOpen, setIsOpen] = useState(true);

  const primaryNav = [
    { label: "Dashboard", href: "/", icon: Compass },
    {
      label: "My Collections",
      href: "/collections",
      icon: FolderHeart,
      badge: isPro ? undefined : "PRO",
    },
    { label: "Sell Your Artifact", href: "/publish", icon: BadgeDollarSign },
    { label: "Seller Studio", href: "/dashboard?tab=seller-studio", icon: Briefcase },
    { label: "Account Settings", href: "/dashboard", icon: User },
  ];

  return (
    <aside
      className={`relative z-20 hidden min-h-[calc(100vh-130px)] flex-shrink-0 transition-[width] duration-300 ease-in-out lg:block ${
        isOpen ? "w-[258px]" : "w-0"
      }`}
    >
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-label={isOpen ? "Collapse side menu" : "Open side menu"}
        aria-expanded={isOpen}
        className="absolute left-full top-4 z-30 flex h-9 w-7 items-center justify-center rounded-r-md border border-l-0 border-[#dededf] bg-white text-[#67676a] shadow-sm transition-colors hover:bg-[#fff8ef] hover:text-[#f28c28] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#f28c28]"
      >
        {isOpen ? (
          <ChevronLeft className="h-4 w-4" strokeWidth={2.5} />
        ) : (
          <ChevronRight className="h-4 w-4" strokeWidth={2.5} />
        )}
      </button>

      <div className="absolute inset-y-0 left-0 w-[258px] overflow-hidden">
        <div
          className={`min-h-full w-[258px] border-r border-[#dededf] bg-white text-[#626266] transition-transform duration-300 ease-in-out ${
            isOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
            {primaryNav.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`relative flex min-h-[64px] items-center justify-between px-5 text-[15px] font-bold transition-colors border-b border-[#dededf] ${
                    isActive
                      ? "bg-[#f4b56a] text-white"
                      : "text-[#67676a] hover:bg-[#fff8ef] hover:text-[#f28c28]"
                  }`}
                >
                  <div className="flex items-center gap-3.5">
                    <Icon className="w-6 h-6" strokeWidth={2.4} />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[9px] font-extrabold bg-[#f28c28] text-white px-1.5 py-0.5 rounded">
                      {item.badge}
                    </span>
                  )}
                  {isActive && <span aria-hidden="true" className="absolute right-0 top-1/2 h-0 w-0 -translate-y-1/2 border-y-[11px] border-r-[12px] border-y-transparent border-r-white" />}
                </Link>
              );
            })}
        </div>
      </div>
    </aside>
  );
}

