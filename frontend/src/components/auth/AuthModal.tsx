"use client";

import React, { useState } from "react";
import { X, Lock, Mail, User, AlertCircle, ArrowRight } from "lucide-react";
import { GoogleSignInButton } from "./GoogleSignInButton";
import { useAuth } from "@/context/AuthContext";

export function AuthModal() {
  const {
    isAuthModalOpen,
    closeAuthModal,
    authModalMode,
    openAuthModal,
    login,
    signup,
  } = useAuth();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isAuthModalOpen) return null;

  const isSignup = authModalMode === "signup";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (googleBusy || loading) return;
    setError(null);
    setLoading(true);

    try {
      if (isSignup) {
        await signup(email, password, name);
      } else {
        await login(email, password);
      }
      setEmail("");
      setPassword("");
      setName("");
    } catch (err: any) {
      setError(err.message || "Authentication failed. Please check your details.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[#303133]/55 animate-in fade-in duration-200">
      <div className="relative w-full max-w-[500px] bg-white rounded-lg shadow-[0_18px_55px_rgba(0,0,0,0.24)] border border-[#dededf] overflow-hidden">
        <div className="h-1 bg-[#f4b56a]" />

        <div className="p-6 sm:p-8">
          <button
            onClick={closeAuthModal}
            className="absolute top-5 right-5 p-1 text-[#999] hover:text-[#f28c28] hover:bg-[#f7f7f7] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>

          <div className="mb-7 pr-10">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded bg-[#fff1df] text-[#f28c28] flex items-center justify-center">
                <Lock className="w-5 h-5" />
              </div>
              <span className="text-[11px] font-extrabold uppercase tracking-[0.16em] text-[#f4b56a]">Promptally account</span>
            </div>
            <h3 className="text-[26px] font-light tracking-[-0.02em] text-[#56565a]">
              {isSignup ? "Create your account" : "Welcome back to Promptally"}
            </h3>
            <p className="text-[13px] text-[#77777a] mt-1.5">
              {isSignup
                ? "Join 35,000+ AI engineers, creators, and researchers."
                : "Sign in to access your collections, purchases, and blueprints."}
            </p>
          </div>

          {error && (
            <div className="mb-4 p-3 rounded bg-red-50 border border-red-200 text-red-700 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <GoogleSignInButton disabled={loading || googleBusy} onBusy={setGoogleBusy} />
          <div className="mb-5 flex items-center gap-3 text-xs text-gray-400"><span className="h-px flex-1 bg-gray-200" />or continue with email<span className="h-px flex-1 bg-gray-200" /></div>
          <form onSubmit={handleSubmit} className="space-y-4">
            {isSignup && (
              <div>
                <label className="block text-xs font-bold text-[#5f6063] mb-1.5">
                  Full Name (optional)
                </label>
                <div className="relative">
                  <User className="w-4 h-4 text-[#999] absolute left-3.5 top-3.5" />
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Alex Morgan"
                    className="w-full pl-10 pr-3 py-3 text-sm border border-[#d3d4d6] rounded focus:ring-2 focus:ring-[#f4b56a]/30 focus:border-[#f4b56a] outline-none transition-all"
                  />
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-bold text-[#5f6063] mb-1.5">
                Email address
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-[#999] absolute left-3.5 top-3.5" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  className="w-full pl-10 pr-3 py-3 text-sm border border-[#d3d4d6] rounded focus:ring-2 focus:ring-[#f4b56a]/30 focus:border-[#f4b56a] outline-none transition-all"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-[#5f6063] mb-1.5">
                Password
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-[#999] absolute left-3.5 top-3.5" />
                <input
                  type="password"
                  required
                  minLength={8}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-3 py-3 text-sm border border-[#d3d4d6] rounded focus:ring-2 focus:ring-[#f4b56a]/30 focus:border-[#f4b56a] outline-none transition-all"
                />
              </div>
            </div>

            {isSignup && (
              <p className="text-[11px] text-gray-500">
                Maximum 2 accounts per IP address and device. Email signups require verification.
              </p>
            )}

            <button
              type="submit"
              disabled={loading || googleBusy}
              className="w-full mt-2 bg-[#f28c28] hover:bg-[#d66f0f] disabled:opacity-50 text-white font-bold py-3 rounded text-sm flex items-center justify-center gap-2 transition-colors"
            >
              <span>{loading ? "Processing..." : isSignup ? "Create Account" : "Sign In"}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>

          {/* Toggle mode */}
          <div className="mt-6 pt-5 border-t border-[#dededf] text-center text-xs text-[#66676a]">
            {isSignup ? (
              <p>
                Already have an account?{" "}
                <button
                  type="button"
                  onClick={() => openAuthModal("login")}
                  className="font-bold text-[#f28c28] hover:text-[#d66f0f]"
                >
                  Sign in
                </button>
              </p>
            ) : (
              <p>
                Don't have an account yet?{" "}
                <button
                  type="button"
                  onClick={() => openAuthModal("signup")}
                  className="font-bold text-[#f28c28] hover:text-[#d66f0f]"
                >
                  Create one now
                </button>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

