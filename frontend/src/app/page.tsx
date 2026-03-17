"use client";

import { useState, useEffect } from "react";
import {
  signInWithRedirect, onAuthStateChanged,
  GoogleAuthProvider, UserCredential,
} from "firebase/auth";
import { useRouter } from "next/navigation";
import { auth } from "@/services/firebase";
import { verifyAuth, getIdentity } from "@/services/session";

async function finishSignIn(result: UserCredential, router: ReturnType<typeof useRouter>) {
  const idToken = await result.user.getIdToken();
  sessionStorage.setItem("id_token", idToken);
  await verifyAuth();
  const identity = await getIdentity();
  router.push(identity ? "/dashboard" : "/onboarding");
}

export default function SignInPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Listen for auth state — fires after redirect completes or on existing session
  useEffect(() => {
    setLoading(true);
    const unsub = onAuthStateChanged(auth, async (user) => {
      if (!user) { setLoading(false); return; }
      try {
        await finishSignIn({ user } as UserCredential, router);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Sign-in failed");
        setLoading(false);
      }
      unsub();
    });
    return () => unsub();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleSignIn() {
    setLoading(true);
    setError(null);
    try {
      const provider = new GoogleAuthProvider();
      await signInWithRedirect(auth, provider);
      // Page navigates away — finishSignIn runs in the useEffect above on return
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      setLoading(false);
    }
  }

  return (
    <main className="dot-grid noise-overlay min-h-screen flex flex-col items-center justify-center px-4">
      {/* Ambient glow orbs */}
      <div
        className="pointer-events-none fixed"
        style={{
          top: "20%", left: "50%", transform: "translateX(-50%)",
          width: 480, height: 480,
          background: "radial-gradient(circle, rgba(201,168,76,0.06) 0%, transparent 70%)",
        }}
      />
      <div
        className="pointer-events-none fixed"
        style={{
          bottom: "10%", right: "15%",
          width: 320, height: 320,
          background: "radial-gradient(circle, rgba(34,211,238,0.04) 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10 w-full max-w-sm animate-fade-up">

        {/* Top mark */}
        <div className="flex justify-center mb-10">
          <div className="flex flex-col items-center gap-4">
            <img
              src="/rumi-logo.svg"
              alt="Rumi"
              style={{
                width: 64,
                height: 64,
                objectFit: "contain",
                filter: "brightness(0) saturate(100%) invert(75%) sepia(40%) saturate(500%) hue-rotate(5deg) brightness(95%)",
              }}
            />
            <span className="uppercase-label tracking-[0.35em]">Rumi</span>
          </div>
        </div>

        {/* Main card */}
        <div className="glass rounded-2xl p-8 text-center">
          {/* Title */}
          <h1
            className="font-display text-gold mb-1"
            style={{ fontSize: "3.5rem", fontWeight: 300, lineHeight: 1.1, letterSpacing: "0.04em" }}
          >
            Rumi
          </h1>
          <p className="uppercase-label mb-6">Present before you speak</p>

          {/* Divider with Arabic ornament */}
          <div className="flex items-center gap-3 mb-6">
            <div className="flex-1 h-px bg-gradient-to-r from-transparent to-[var(--border)]" />
            <span style={{ color: "var(--gold-dim)", fontSize: "1rem" }}>&#10022;</span>
            <div className="flex-1 h-px bg-gradient-to-l from-transparent to-[var(--border)]" />
          </div>

          <p className="text-sm mb-8 leading-relaxed" style={{ color: "var(--text-2)" }}>
            Not a chatbot. An identity-aware companion that<br />
            witnesses, understands, and speaks only when it matters.
          </p>

          {/* Sign-in button */}
          <button
            onClick={handleSignIn}
            disabled={loading}
            className="btn-primary w-full"
            style={{ justifyContent: "center" }}
          >
            {loading ? (
              <>
                <span
                  className="inline-block w-4 h-4 rounded-full border-2 border-current border-t-transparent"
                  style={{ animation: "spin 0.7s linear infinite" }}
                />
                Setting up…
              </>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 01-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="currentColor" fillOpacity="0.8" />
                  <path d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z" fill="currentColor" fillOpacity="0.6" />
                  <path d="M3.964 10.71A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="currentColor" fillOpacity="0.6" />
                  <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58z" fill="currentColor" fillOpacity="0.8" />
                </svg>
                Continue with Google
              </>
            )}
          </button>

          {error && (
            <p className="mt-4 text-sm" style={{ color: "var(--error)" }}>{error}</p>
          )}
        </div>

        {/* Footer */}
        <p className="text-center mt-6 text-xs" style={{ color: "var(--muted)" }}>
          Your identity is your own. Rumi only remembers what you share.
        </p>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </main>
  );
}
