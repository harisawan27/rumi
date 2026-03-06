"use client";

import { useState } from "react";
import { signInWithPopup, GoogleAuthProvider } from "firebase/auth";
import { useRouter } from "next/navigation";
import { auth } from "@/services/firebase";

export default function SignInPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSignIn() {
    setLoading(true);
    setError(null);
    try {
      const provider = new GoogleAuthProvider();
      const result = await signInWithPopup(auth, provider);
      const idToken = await result.user.getIdToken();
      // Store token in memory (sessionStorage avoids localStorage persistence)
      sessionStorage.setItem("id_token", idToken);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Sign-in failed");
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gray-950 text-white">
      <div className="text-center space-y-6 max-w-sm w-full px-6">
        <h1 className="text-4xl font-bold tracking-tight">Mirr&apos;at</h1>
        <p className="text-gray-400 text-sm">
          Not a chatbot — a Karachi-based Wise Engineer companion.
        </p>
        <button
          onClick={handleSignIn}
          disabled={loading}
          className="w-full py-3 px-6 bg-white text-gray-900 rounded-lg font-medium hover:bg-gray-100 disabled:opacity-50 transition"
        >
          {loading ? "Signing in…" : "Sign in with Google"}
        </button>
        {error && (
          <p className="text-red-400 text-sm">{error}</p>
        )}
      </div>
    </main>
  );
}
