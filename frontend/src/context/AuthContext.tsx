"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { UserProfile } from "@/lib/types";
import { api, ApiError, setCheckoutOwner } from "@/lib/api";
import { getDeviceFingerprint } from "@/lib/fingerprint";

interface AuthContextType {
  user: UserProfile | null;
  loading: boolean;
  isPro: boolean;
  isAdmin: boolean;
  login: (email: string, pass: string) => Promise<void>;
  signup: (email: string, pass: string, name?: string) => Promise<void>;
  googleLogin: (credential: string, csrfToken: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  isAuthModalOpen: boolean;
  authModalMode: "login" | "signup";
  openAuthModal: (mode?: "login" | "signup") => void;
  closeAuthModal: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<"login" | "signup">("login");

  const refreshUser = async () => {
    try {
      const profile = await api.getMe();
      setCheckoutOwner(profile.id);
      setUser(profile);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        setUser(null);
        setCheckoutOwner(null);
        if (typeof window !== "undefined") {
          localStorage.removeItem("promptally_token");
        }
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Remove tokens persisted by previous builds; sessions use HttpOnly cookies.
    localStorage.removeItem("promptally_token");
    refreshUser();
  }, []);

  const login = async (email: string, pass: string) => {
    await api.login({ email, password: pass });
    await refreshUser();
    closeAuthModal();
  };

  const signup = async (email: string, pass: string, name?: string) => {
    const fingerprint = await getDeviceFingerprint();
    await api.signup({
      email,
      password: pass,
      name,
      device_fingerprint: fingerprint,
    });
    await refreshUser();
    closeAuthModal();
  };

  const googleLogin = async (credential: string, csrfToken: string) => {
    const fingerprint = await getDeviceFingerprint();
    await api.googleAuth({
      credential,
      csrf_token: csrfToken,
      device_fingerprint: fingerprint,
    });
    await refreshUser();
    closeAuthModal();
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
    }
    if (typeof window !== "undefined") {
      localStorage.removeItem("promptally_token");
    }
    window.google?.accounts.id.disableAutoSelect();
    setCheckoutOwner(null);
    setUser(null);
  };

  const openAuthModal = (mode: "login" | "signup" = "login") => {
    setAuthModalMode(mode);
    setIsAuthModalOpen(true);
  };

  const closeAuthModal = () => {
    setIsAuthModalOpen(false);
  };

  const isPro = user?.tier === "PRO" || user?.tier === "ADMIN";
  const isAdmin = user?.tier === "ADMIN";

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        isPro,
        isAdmin,
        login,
        signup,
        googleLogin,
        logout,
        refreshUser,
        isAuthModalOpen,
        authModalMode,
        openAuthModal,
        closeAuthModal,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

