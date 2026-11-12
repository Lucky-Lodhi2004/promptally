"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { User as UserIcon, ShoppingCart, Search, ChevronDown, LogOut, Settings, FolderHeart, Shield, Sparkles } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { UserAvatar } from "@/components/ui/UserAvatar";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

export function TopUtilityBar() {
  const { user, logout, openAuthModal, isPro, isAdmin } = useAuth();
  const [currency, setCurrency] = useState<string>("$ USD");
  const [dropdownOpen, setDropdownOpen] = useState(false);

  useEffect(() => {
    // Probe billing quote to detect viewer's country currency
    api
      .getBillingQuote()
      .then((quote) => {
        if (quote.currency === "INR") {
          setCurrency("₹ INR");
        } else {
          setCurrency("$ USD");
        }
      })
      .catch(() => {
        setCurrency("$ USD");
      });
  }, []);

  return (
    <div className="relative z-[70] h-11 bg-[#fff8ef] text-[14px] text-[#444447] px-4 sm:px-9 flex items-center justify-between border-t-[3px] border-[#f28c28]">
      {/* Left side */}
      <div className="flex h-full items-center gap-4">
        <Link
          href="/contact"
          className="hover:text-[#f28c28] transition-colors font-bold"
        >
          Contact us
        </Link>
        {!user && <span className="hidden sm:block h-5 w-px bg-[#dfe1ec]" />}
      </div>

      {/* Right side */}
      <div className="flex h-full items-center gap-5 sm:gap-7">
        {user ? (
          <div className="relative sm:absolute sm:left-[175px] sm:top-1/2 sm:-translate-y-1/2">
            <button
              onClick={() => setDropdownOpen(!dropdownOpen)}
              className="flex h-9 items-center gap-2 rounded-md bg-[#e9ebf6] px-3.5 font-bold text-[#444447] transition-colors hover:bg-[#e1e4f1]"
            >
              <UserAvatar
                src={user.avatar_url}
                alt={user.username}
                className="h-5 w-5"
              />
              <span className="max-w-[170px] truncate">{user.name || user.username}</span>
              {isPro && (
                <span className="bg-amber-100 text-amber-800 text-[9px] font-bold px-1.5 py-0.5 rounded border border-amber-300">
                  PRO
                </span>
              )}
              <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
            </button>

            {dropdownOpen && (
              <div
                className="absolute right-0 z-[80] mt-1 w-52 bg-white rounded-lg shadow-xl border border-gray-100 py-1.5 animate-in fade-in slide-in-from-top-1"
                onMouseLeave={() => setDropdownOpen(false)}
              >
                <div className="px-3 py-2 border-b border-gray-100">
                  <p className="font-semibold text-gray-800 truncate text-xs">{user.name || user.username}</p>
                  <p className="text-[11px] text-gray-500 truncate">{user.email}</p>
                </div>

                <Link
                  href="/dashboard"
                  onClick={() => setDropdownOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 text-gray-700 hover:bg-amber-50 hover:text-amber-600 transition-colors"
                >
                  <Settings className="w-4 h-4" />
                  <span>Dashboard & Settings</span>
                </Link>

                <Link
                  href="/collections"
                  onClick={() => setDropdownOpen(false)}
                  className="flex items-center gap-2 px-3 py-2 text-gray-700 hover:bg-amber-50 hover:text-amber-600 transition-colors"
                >
                  <FolderHeart className="w-4 h-4" />
                  <span>My Collections</span>
                </Link>

                {isAdmin && (
                  <Link
                    href="/admin"
                    onClick={() => setDropdownOpen(false)}
                    className="flex items-center gap-2 px-3 py-2 text-purple-700 hover:bg-purple-50 transition-colors"
                  >
                    <Shield className="w-4 h-4" />
                    <span>Admin Panel</span>
                  </Link>
                )}

                {!isPro && (
                  <Link
                    href="/dashboard?tab=membership"
                    onClick={() => setDropdownOpen(false)}
                    className="flex items-center gap-2 px-3 py-2 text-amber-700 font-medium hover:bg-amber-50 transition-colors"
                  >
                    <Sparkles className="w-4 h-4" />
                    <span>Upgrade to Pro ($1/mo)</span>
                  </Link>
                )}

                <div className="border-t border-gray-100 my-1"></div>

                <button
                  onClick={() => {
                    setDropdownOpen(false);
                    logout();
                  }}
                  className="w-full flex items-center gap-2 px-3 py-2 text-red-600 hover:bg-red-50 transition-colors text-left"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign out</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-4 font-bold">
            <button
              onClick={() => openAuthModal("signup")}
              className="hover:text-gray-900 transition-colors font-medium"
            >
              Sign up
            </button>
            <button
              onClick={() => openAuthModal("login")}
              className="flex items-center space-x-1 hover:text-gray-900 transition-colors font-medium"
            >
              <UserIcon className="w-3.5 h-3.5" />
              <span>Sign in</span>
            </button>
          </div>
        )}

        {/* Currency badge */}
        <span className="hidden sm:inline font-bold cursor-default">
          {currency}
        </span>

        <ThemeToggle />

        {/* Saved / Collections shortcut */}
        <Link
          href="/collections"
          title="Collections"
          className="text-[#444447] hover:text-[#f28c28] transition-colors"
        >
          <ShoppingCart className="w-5 h-5" />
        </Link>
        <Link href="/directory" aria-label="Search registry" className="text-[#444447] hover:text-[#f28c28] transition-colors">
          <Search className="w-5 h-5" />
        </Link>
      </div>
    </div>
  );
}

