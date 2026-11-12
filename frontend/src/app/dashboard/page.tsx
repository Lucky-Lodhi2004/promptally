"use client";

import React, { useState, useEffect, useRef, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Script from "next/script";
import {
  User,
  Lock,
  Sparkles,
  Briefcase,
  Check,
  AlertCircle,
  Copy,
  Upload,
  Calendar,
  ShieldCheck,
  CreditCard,
  Loader2,
  Trash2,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, ApiError } from "@/lib/api";
import { SellerGatewayStatus, SubscriptionInfo, BillingQuote } from "@/lib/types";
import { UserAvatar } from "@/components/ui/UserAvatar";

function DashboardContent() {
  const searchParams = useSearchParams();
  const initialTab = searchParams.get("tab") || "profile";

  const { user, refreshUser, isPro, openAuthModal } = useAuth();

  const [activeTab, setActiveTab] = useState<string>(initialTab);

  // Tab 1: Profile State
  const [username, setUsername] = useState("");
  const [name, setName] = useState("");
  const [avatarFile, setAvatarFile] = useState<File | null>(null);
  const [profileMsg, setProfileMsg] = useState<string | null>(null);
  const [profileErr, setProfileErr] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);

  // Tab 2: Password State
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passMsg, setPassMsg] = useState<string | null>(null);
  const [passErr, setPassErr] = useState<string | null>(null);
  const [savingPass, setSavingPass] = useState(false);

  // Tab 3: Membership ($1/mo) State
  const [subInfo, setSubInfo] = useState<SubscriptionInfo | null>(null);
  const [loadingSub, setLoadingSub] = useState(false);
  const [subMsg, setSubMsg] = useState<string | null>(null);
  const [subErr, setSubErr] = useState<string | null>(null);
  const [subscribing, setSubscribing] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [quote, setQuote] = useState<BillingQuote | null>(null);
  const [checkingPayment, setCheckingPayment] = useState(false);
  const paymentRun = useRef(0);

  // Tab 4: Seller Studio (BYOG) State
  const [gatewayStatus, setGatewayStatus] = useState<SellerGatewayStatus | null>(null);
  const [rzpKeyId, setRzpKeyId] = useState("");
  const [rzpKeySecret, setRzpKeySecret] = useState("");
  const [rzpWebhookSecret, setRzpWebhookSecret] = useState("");
  const [dodoApiKey, setDodoApiKey] = useState("");
  const [dodoEnv, setDodoEnv] = useState<"test" | "live">("test");
  const [sellerMsg, setSellerMsg] = useState<string | null>(null);
  const [sellerErr, setSellerErr] = useState<string | null>(null);
  const [savingSeller, setSavingSeller] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);

  useEffect(() => {
    if (searchParams.get("razorpay") === "connected") setSellerMsg("Razorpay connected. Indian buyers can now pay you directly.");
    if (searchParams.get("razorpay") === "denied") setSellerErr("Razorpay connection was not authorized. You can try again.");
  }, [searchParams]);

  const handleRazorpayOAuth = async () => {
    setSavingSeller(true);
    setSellerErr(null);
    try {
      const result = await api.startRazorpayConnect();
      window.location.assign(result.authorization_url);
    } catch (error) {
      setSellerErr(error instanceof Error ? error.message : "Could not connect Razorpay");
    } finally { setSavingSeller(false); }
  };

  useEffect(() => {
    if (user) {
      setUsername(user.username);
      setName(user.name);
    }
  }, [user]);

  useEffect(() => {
    if (activeTab === "membership" && user) {
      setLoadingSub(true);
      api
        .getSubscription()
        .then((res) => {
          setSubInfo(res.subscription);
        })
        .catch((error) => setSubErr(error.message))
        .finally(() => setLoadingSub(false));
      api.getBillingQuote().then(setQuote).catch(error => setSubErr(error.message));
    } else if (activeTab === "seller-studio" && user) {
      api
        .getSellerGateways()
        .then((res) => {
          setGatewayStatus(res);
        })
        .catch(() => {});
    }
  }, [activeTab, user]);

  // Handle Profile Update
  const handleProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setProfileMsg(null);
    setProfileErr(null);
    setSavingProfile(true);

    try {
      const formData = new FormData();
      formData.append("username", username.trim());
      formData.append("name", name.trim());
      if (avatarFile) {
        formData.append("avatar", avatarFile);
      }
      await api.updateProfile(formData);
      await refreshUser();
      setProfileMsg("Profile updated successfully!");
    } catch (err: any) {
      setProfileErr(err.message || "Failed to update profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  // Handle Password Change
  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPassMsg(null);
    setPassErr(null);
    setSavingPass(true);

    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setPassMsg("Password updated successfully!");
      setCurrentPassword("");
      setNewPassword("");
    } catch (err: any) {
      setPassErr(err.message || "Failed to change password.");
    } finally {
      setSavingPass(false);
    }
  };

  const checkSubscriptionPayment = async () => {
    const run = ++paymentRun.current;
    setCheckingPayment(true);
    setSubMsg("Waiting for payment confirmation…");
    try {
      for (let attempt = 0; attempt < 12 && run === paymentRun.current; attempt++) {
        let state;
        if (attempt % 3 === 0) {
          try { state = await api.verifySubscription(); }
          catch (error) {
            if (error instanceof ApiError && error.status === 429) {
              await new Promise(resolve => setTimeout(resolve, Math.max(20, error.retryAfter) * 1000));
              continue;
            }
            throw error;
          }
        } else {
          state = await api.getSubscription();
        }
        if (run !== paymentRun.current) return;
        setSubInfo(state.subscription);
        if (state.is_pro) {
          await refreshUser();
          setSubMsg("Payment confirmed. Your Pro membership is active.");
          return;
        }
        if (state.subscription?.status === "CANCELED") {
          setSubMsg("The subscription was cancelled. No Pro access was granted.");
          return;
        }
        if (state.subscription?.status === "PAST_DUE") {
          setSubErr("Payment failed or requires attention. For a failed initial Dodo payment, click Upgrade to Pro to start a fresh checkout. Existing subscriptions may require billing support.");
          setSubMsg(null);
          return;
        }
        await new Promise(resolve => setTimeout(resolve, 20000));
      }
      if (run === paymentRun.current) setSubMsg("Payment confirmation is still pending. Check again shortly; do not pay again.");
    } catch (error) {
      if (run === paymentRun.current) setSubErr(error instanceof Error ? error.message : "Could not check membership");
    } finally {
      if (run === paymentRun.current) setCheckingPayment(false);
    }
  };

  useEffect(() => {
    if (user && searchParams.get("subscription") === "pending") {
      setActiveTab("membership");
      checkSubscriptionPayment();
    }
    return () => { paymentRun.current++; };
  }, [user?.id, searchParams]);

  const handleSubscribe = async () => {
    setSubscribing(true);
    setSubErr(null);
    try {
      // Inspect existing state before creating anything: closing a modal or an SDK
      // load failure must resume the existing checkout instead of billing twice.
      const state = await api.getSubscription();
      setSubInfo(state.subscription);
      if (state.is_pro) { await refreshUser(); return; }
      const pending = state.subscription?.status === "PENDING" ? state.subscription : null;
      const res = pending || await api.createSubscription();
      if (!pending) {
        const saved = await api.getSubscription();
        setSubInfo(saved.subscription);
      }
      if (res.gateway === "razorpay" && res.key_id && res.subscription_id && (window as any).Razorpay) {
        const rzp = new (window as any).Razorpay({
          key: res.key_id, subscription_id: res.subscription_id,
          name: "Promptally Pro Membership", description: "Monthly Pro membership",
          handler: checkSubscriptionPayment,
          prefill: { name: user?.name, email: user?.email }, theme: { color: "#ea580c" },
        });
        rzp.open();
      } else if (res.checkout_url) {
        window.location.assign(res.checkout_url);
      } else {
        setSubErr("Payment SDK is loading. Use Resume checkout to try again.");
      }
    } catch (error) {
      setSubErr(error instanceof Error ? error.message : "Could not start checkout");
    } finally { setSubscribing(false); }
  };

  const handleCancelSubscription = async () => {
    if (cancelling || (isPro && subInfo?.cancel_at_period_end)) return;
    const message = isPro
      ? "Cancel your Pro subscription? You will retain access until the end of your paid billing cycle."
      : "Cancel this subscription and stop further renewal attempts?";
    if (!confirm(message)) {
      return;
    }
    setCancelling(true);
    setSubErr(null);
    setSubMsg(null);
    try {
      const cancellation = await api.cancelSubscription();
      setSubMsg(cancellation.message);
      const res = await api.getSubscription();
      setSubInfo(res.subscription);
      await refreshUser();
    } catch (err: any) {
      setSubErr(err.message || "Failed to cancel subscription.");
    } finally {
      setCancelling(false);
    }
  };

  // Connect Razorpay Gateway (Seller Studio)
  const handleConnectRazorpay = async (e: React.FormEvent) => {
    e.preventDefault();
    setSellerMsg(null);
    setSellerErr(null);
    setSavingSeller(true);

    try {
      const res = await api.connectSellerGateway({
        gateway_type: "razorpay",
        key_id: rzpKeyId.trim(),
        key_secret: rzpKeySecret.trim(),
        webhook_secret: rzpWebhookSecret.trim(),
      });
      setGatewayStatus((prev) => ({
        ...prev,
        razorpay_connected: true,
        dodo_connected: prev?.dodo_connected || false,
      }));
      setSellerMsg(`Razorpay connected! Webhook URL: ${res.webhook_url}`);
      setRzpKeySecret("");
      setRzpWebhookSecret("");
    } catch (err: any) {
      setSellerErr(err.message || "Failed to connect Razorpay account.");
    } finally {
      setSavingSeller(false);
    }
  };

  // Connect Dodo Gateway (Seller Studio)
  const handleConnectDodo = async (e: React.FormEvent) => {
    e.preventDefault();
    setSellerMsg(null);
    setSellerErr(null);
    setSavingSeller(true);

    try {
      const res = await api.connectSellerGateway({
        gateway_type: "dodo",
        api_key: dodoApiKey.trim(),
        environment: dodoEnv,
      });
      setGatewayStatus(res);
      setSellerMsg("Dodo connected. Payment notifications are configured automatically, and products will be created when you publish.");
      setDodoApiKey("");
    } catch (err: any) {
      setSellerErr(err.message || "Failed to connect Dodo Payments account.");
    } finally {
      setSavingSeller(false);
    }
  };

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedUrl(id);
    setTimeout(() => setCopiedUrl(null), 2000);
  };

  if (!user) {
    return (
      <div className="readable-interface max-w-md mx-auto py-20 px-4 text-center">
        <h2 className="text-xl font-bold text-gray-900 mb-2">Account Required</h2>
        <p className="text-xs text-gray-500 mb-6">Please sign in to access your dashboard and settings.</p>
        <button
          onClick={() => openAuthModal("login")}
          className="bg-amber-600 hover:bg-amber-500 text-white font-bold text-xs px-6 py-2.5 rounded-xl shadow-sm transition-all"
        >
          Sign In
        </button>
      </div>
    );
  }

  const razorpayWebhookUrl = `${typeof window !== "undefined" ? window.location.origin : (process.env.NEXT_PUBLIC_SITE_URL || "")}/api/v1/webhooks/razorpay/${user.id}`;

  return (
    <>
      <Script src="https://checkout.razorpay.com/v1/checkout.js" strategy="lazyOnload" />

      <div className="readable-interface max-w-[1500px] mx-auto px-5 sm:px-10 py-10 xl:py-14">
        <div className="mb-8">
          <h1 className="text-2xl sm:text-[30px] font-light text-[#5f6063] tracking-tight">
            Account & Developer Settings
          </h1>
          <p className="text-xs text-gray-500 mt-1">
            Manage your profile, security, Pro membership, and connected payment gateways.
          </p>
        </div>

        {/* Tab Navigation */}
        <div className="flex items-center gap-2 border-b-2 border-[#f4b56a] pb-px mb-8 overflow-x-auto">
          {[
            { id: "profile", label: "Profile", icon: User },
            { id: "security", label: "Security", icon: Lock },
            { id: "membership", label: "Pro Membership", icon: Sparkles },
            { id: "seller-studio", label: "Seller Studio (BYOG)", icon: Briefcase },
          ].map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 py-3 px-4 text-xs font-bold whitespace-nowrap border-b-2 transition-all ${
                  isActive
                    ? "border-[#f28c28] text-[#f28c28]"
                    : "border-transparent text-gray-500 hover:text-gray-900"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>

        {/* Tab 1: Profile */}
        {activeTab === "profile" && (
          <form onSubmit={handleProfileSubmit} className="max-w-xl bg-white p-6 sm:p-8 rounded-2xl border border-gray-200 shadow-xs space-y-5">
            <h2 className="text-xl font-bold text-gray-900">Personal Information</h2>

            {profileMsg && (
              <div className="p-3 bg-amber-50 border border-amber-200 text-amber-700 text-xs rounded-xl flex items-center gap-2">
                <Check className="w-4 h-4" />
                <span>{profileMsg}</span>
              </div>
            )}

            {profileErr && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                <span>{profileErr}</span>
              </div>
            )}

            {/* Avatar Preview & Upload */}
            <div className="flex items-center gap-4">
              <UserAvatar
                src={user.avatar_url}
                alt={user.username}
                className="h-16 w-16 border border-gray-200"
              />
              <div>
                <label className="block text-xs font-bold text-gray-700 mb-1">
                  Profile Picture
                </label>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => setAvatarFile(e.target.files?.[0] || null)}
                  className="text-xs text-gray-500 file:mr-3 file:py-1 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-gray-100 hover:file:bg-gray-200"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">Username</label>
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full p-2.5 text-xs font-medium border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
              />
              <p className="text-[11px] text-gray-400 mt-1">Unique public identifier displayed on your blueprints.</p>
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">Display Name</label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full p-2.5 text-xs font-medium border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">Email Address</label>
              <input
                type="email"
                disabled
                value={user.email}
                className="w-full p-2.5 text-xs font-medium bg-gray-50 border border-gray-200 rounded-xl text-gray-500 cursor-not-allowed"
              />
            </div>

            <button
              type="submit"
              disabled={savingProfile}
              className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-bold text-xs px-6 py-2.5 rounded-xl shadow-sm transition-all"
            >
              {savingProfile ? "Saving..." : "Save Profile"}
            </button>
          </form>
        )}

        {/* Tab 2: Security */}
        {activeTab === "security" && (
          <form onSubmit={handlePasswordSubmit} className="max-w-xl bg-white p-6 sm:p-8 rounded-2xl border border-gray-200 shadow-xs space-y-5">
            <h2 className="text-xl font-bold text-gray-900">Change Password</h2>

            {passMsg && (
              <div className="p-3 bg-amber-50 border border-amber-200 text-amber-700 text-xs rounded-xl flex items-center gap-2">
                <Check className="w-4 h-4" />
                <span>{passMsg}</span>
              </div>
            )}

            {passErr && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                <span>{passErr}</span>
              </div>
            )}

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">Current Password</label>
              <input
                type="password"
                required
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                className="w-full p-2.5 text-xs font-medium border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-gray-700 mb-1">New Password</label>
              <input
                type="password"
                required
                minLength={6}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                className="w-full p-2.5 text-xs font-medium border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
              />
            </div>

            <button
              type="submit"
              disabled={savingPass}
              className="bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-bold text-xs px-6 py-2.5 rounded-xl shadow-sm transition-all"
            >
              {savingPass ? "Updating..." : "Update Password"}
            </button>
          </form>
        )}

        {/* Tab 3: Membership ($1/mo) */}
        {activeTab === "membership" && (
          <div className="max-w-xl bg-white p-6 sm:p-8 rounded-2xl border border-gray-200 shadow-xs space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-gray-900">Platform Pro Subscription</h2>
                <p className="text-xs font-semibold text-green-700 mt-0.5">$1.00 USD / month (₹85 INR in India)</p>
              </div>
              <span
                className={`text-xs font-bold px-3 py-1 rounded-full uppercase ${
                  isPro ? "bg-green-100 text-green-800 border border-green-200" : "bg-gray-100 text-gray-700"
                }`}
              >
                {user.tier}
              </span>
            </div>

            {subMsg && (
              <div className="p-3 bg-green-50 border border-green-200 text-green-700 text-xs rounded-xl flex items-center gap-2">
                <Check className="w-4 h-4" />
                <span>{subMsg}</span>
              </div>
            )}

            {subErr && (
              <div className="p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
                <AlertCircle className="w-4 h-4" />
                <span>{subErr}</span>
              </div>
            )}

            {!isPro && subInfo?.status === "PENDING" && <div className="rounded-xl border border-amber-200 p-4 text-xs">
              <p>A checkout is pending. Resume it or check for confirmation before paying again.</p>
              <button disabled={checkingPayment} onClick={checkSubscriptionPayment} className="mt-2 underline disabled:opacity-50">{checkingPayment ? "Checking payment…" : "Check payment status"}</button>
            </div>}
            {isPro ? (
              <div className="space-y-4 pt-2">
                <div className="p-4 rounded-xl bg-amber-50/70 border border-amber-200 space-y-2">
                  <div className="flex items-center gap-2 text-amber-800 font-bold text-xs">
                    <Sparkles className="w-4 h-4" />
                    <span>Active Pro Member Privileges</span>
                  </div>
                  <ul className="text-xs text-amber-900 space-y-1 list-disc list-inside">
                    <li>Create unlimited personal & public collections</li>
                    <li>Access to Seller Studio (Bring-Your-Own-Gateway)</li>
                    <li>Publish and sell prompts with 0% platform fee</li>
                  </ul>
                  {subInfo && (
                    <div className="pt-2 text-[11px] text-amber-800 border-t border-amber-200 flex items-center justify-between">
                      <span>Gateway: {subInfo.gateway}</span>
                      <span>{subInfo.cancel_at_period_end ? "Access ends" : "Next cycle"}: {new Date(subInfo.current_period_end).toLocaleDateString()}</span>
                    </div>
                  )}
                </div>

                {subInfo?.cancel_at_period_end && (
                  <p className="text-xs text-amber-900">Cancellation is scheduled. Your Pro access continues until the date above, and your subscription will not renew.</p>
                )}

                <button
                  onClick={handleCancelSubscription}
                  disabled={cancelling || loadingSub || !subInfo || subInfo.cancel_at_period_end}
                  className="text-xs text-red-600 hover:text-red-700 font-bold hover:underline disabled:opacity-50 disabled:no-underline flex items-center gap-1.5"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  <span>{cancelling ? "Cancelling…" : subInfo?.cancel_at_period_end ? "Cancellation scheduled" : "Cancel Pro Subscription"}</span>
                </button>
              </div>
            ) : (
              <div className="space-y-4 pt-2">
                {subInfo?.subscription_id && subInfo.status !== "CANCELED" && (
                  <button
                    onClick={handleCancelSubscription}
                    disabled={cancelling || loadingSub}
                    className="text-xs text-red-600 font-bold hover:underline disabled:opacity-50"
                  >
                    {cancelling ? "Cancelling…" : "Cancel existing subscription"}
                  </button>
                )}
                <p className="text-xs text-gray-600 leading-relaxed">
                  Pro costs $1/month. {quote ? `Your verified regional price is ${new Intl.NumberFormat(undefined, { style: "currency", currency: quote.currency }).format(quote.amount / 100)} per month via ${quote.gateway}.` : "The regional price will be confirmed before checkout."}
                </p>

                <button
                  onClick={handleSubscribe}
                  disabled={subscribing || checkingPayment}
                  className="w-full bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-bold text-sm py-3 rounded-xl shadow-md transition-all flex items-center justify-center gap-2"
                >
                  {subscribing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  <span>{subInfo?.status === "PENDING" ? "Resume checkout" : "Upgrade to Pro ($1 / mo)"}</span>
                </button>
              </div>
            )}
          </div>
        )}

        {/* Tab 4: Seller Studio (BYOG) */}
        {activeTab === "seller-studio" && (
          <div className="space-y-8">
            <div className="bg-gradient-to-r from-amber-50 via-amber-50 to-amber-50 p-6 rounded-2xl border border-amber-200/80">
              <div className="flex items-center gap-2 text-amber-800 font-bold text-sm mb-1">
                <Briefcase className="w-4 h-4" />
                <span>Bring-Your-Own-Gateway (BYOG) Setup</span>
              </div>
              <p className="text-xs text-gray-600 max-w-2xl leading-relaxed">
                Promptally takes <strong>0% platform commission</strong>. Buyers pay directly into your merchant accounts.
                Connect Razorpay for Indian buyers, Dodo for foreign buyers, or both to serve both groups. Provider fees still apply.
              </p>
            </div>

            {sellerMsg && (
              <div className="p-3.5 bg-green-50 border border-green-200 text-green-700 text-xs rounded-xl flex items-center gap-2">
                <Check className="w-4 h-4 flex-shrink-0" />
                <span>{sellerMsg}</span>
              </div>
            )}

            {sellerErr && (
              <div className="p-3.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{sellerErr}</span>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Razorpay connection; manual credentials remain available during migration. */}
              <div id="razorpay" className="bg-white p-6 rounded-2xl border border-gray-200 shadow-xs space-y-4">
                <h3 className="font-bold text-gray-900 text-sm">Razorpay — Indian buyers (INR)</h3>
                <p className={`text-xs ${gatewayStatus?.razorpay_connected ? "font-semibold text-green-700" : "text-gray-600"}`}>
                  {gatewayStatus?.razorpay_connected ? "Connected. Indian buyers can pay you directly." : "Connect your existing merchant account to accept payments from Indian buyers."}
                </p>
                <button type="button" disabled={savingSeller || !gatewayStatus?.razorpay_oauth_available}
                  onClick={handleRazorpayOAuth}
                  className="w-full bg-amber-600 hover:bg-amber-500 disabled:opacity-50 text-white font-bold text-xs py-2.5 rounded-xl">
                  {savingSeller ? "Connecting…" : gatewayStatus?.razorpay_connected ? "Reconnect Razorpay" : "Connect with Razorpay"}
                </button>
                {!gatewayStatus?.razorpay_oauth_available && <p className="text-xs text-gray-600">Razorpay Connect is awaiting platform activation. Existing connections continue to work.</p>}
                {gatewayStatus?.razorpay_connection_type === "manual" && <p className="text-xs text-gray-600">Your existing connection is active. Contact support before migrating an account with paid listings.</p>}
                {!gatewayStatus?.razorpay_oauth_available && gatewayStatus?.razorpay_connection_type !== "oauth" && <details>
                  <summary className="cursor-pointer text-xs font-semibold">Advanced: manual connection</summary>
                  <form onSubmit={handleConnectRazorpay} className="space-y-4 pt-4">
                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">Key ID</label>
                  <input
                    type="text"
                    required
                    value={rzpKeyId}
                    onChange={(e) => setRzpKeyId(e.target.value)}
                    placeholder="rzp_live_..."
                    className="w-full p-2 text-xs font-mono border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">Key Secret</label>
                  <input
                    type="password"
                    required
                    value={rzpKeySecret}
                    onChange={(e) => setRzpKeySecret(e.target.value)}
                    placeholder="••••••••"
                    className="w-full p-2 text-xs font-mono border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">Webhook Secret</label>
                  <input
                    type="password"
                    required
                    value={rzpWebhookSecret}
                    onChange={(e) => setRzpWebhookSecret(e.target.value)}
                    placeholder="••••••••"
                    className="w-full p-2 text-xs font-mono border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20"
                  />
                </div>

                <div className="p-3 bg-gray-50 rounded-xl border border-gray-200">
                  <p className="text-[10px] font-bold uppercase text-gray-400 mb-1">Your Razorpay Webhook URL</p>
                  <div className="flex items-center justify-between text-xs font-mono text-gray-700">
                    <span className="truncate mr-2">{razorpayWebhookUrl}</span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(razorpayWebhookUrl, "rzp")}
                      className="p-1 hover:text-amber-600"
                    >
                      {copiedUrl === "rzp" ? <Check className="w-3.5 h-3.5 text-amber-600" /> : <Copy className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  disabled={savingSeller}
                  className="w-full bg-gray-900 hover:bg-gray-800 disabled:opacity-50 text-white font-bold text-xs py-2.5 rounded-xl transition-all"
                >
                  {savingSeller ? "Connecting..." : "Save Razorpay Credentials"}
                </button>
                  </form>
                </details>}
              </div>

              {/* Dodo Payments Card */}
              <form id="dodo" onSubmit={handleConnectDodo} className="bg-white p-6 rounded-2xl border border-gray-200 shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-gray-900 text-sm">2. Dodo Payments (Global USD)</h3>
                  {gatewayStatus?.dodo_connected ? (
                    <span className="text-[10px] font-bold bg-amber-100 text-amber-800 px-2 py-0.5 rounded-full">Connected ({gatewayStatus.dodo_environment})</span>
                  ) : (
                    <span className="text-[10px] font-bold bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full">Not Connected</span>
                  )}
                </div>

                {gatewayStatus?.dodo_connected && !gatewayStatus.dodo_webhook_managed && <p className="text-xs text-gray-600">Your existing connection still works. Paste the same API key once to enable automatic setup.</p>}

                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">API Key</label>
                  <input
                    type="password"
                    required
                    value={dodoApiKey}
                    onChange={(e) => setDodoApiKey(e.target.value)}
                    placeholder="Paste your Dodo API key"
                    className="w-full p-2 text-xs font-mono border border-gray-300 rounded-lg outline-none focus:ring-2 focus:ring-amber-500/20"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold text-gray-700 mb-1">Environment</label>
                  <select
                    value={dodoEnv}
                    onChange={(e) => setDodoEnv(e.target.value as any)}
                    className="w-full p-2 text-xs font-semibold bg-white border border-gray-300 rounded-lg outline-none"
                  >
                    <option value="live">Live Production</option>
                    <option value="test">Test Sandbox</option>
                  </select>
                </div>

                <p className="text-xs text-gray-600">Create an API key with write access in Dodo → Developer → API Keys, then paste it here. We configure payment notifications and products for you. This enables foreign buyers to pay in USD.</p>
                <button
                  type="submit"
                  disabled={savingSeller}
                  className="w-full bg-gray-900 hover:bg-gray-800 disabled:opacity-50 text-white font-bold text-xs py-2.5 rounded-xl transition-all"
                >
                  {savingSeller ? "Connecting..." : "Connect Dodo"}
                </button>
              </form>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="py-24 text-center flex flex-col items-center justify-center">
          <Loader2 className="w-8 h-8 text-amber-600 animate-spin mb-3" />
          <p className="text-xs font-medium text-gray-500">Loading dashboard...</p>
        </div>
      }
    >
      <DashboardContent />
    </Suspense>
  );
}

