"use client";

/**
 * Auth client supporting both backend modes:
 *  - local:    email/password against the FastAPI backend (Argon2 + JWT)
 *  - supabase: Supabase Auth issues the session; the backend validates its JWT
 * The access token is kept in localStorage (MVP). Moving to httpOnly cookies is a later hardening step.
 */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const MODE = process.env.NEXT_PUBLIC_AUTH_MODE === "supabase" ? "supabase" : "local";
const TOKEN_KEY = "fitpro.token";

let supabase: SupabaseClient | null = null;
function sb(): SupabaseClient {
  if (!supabase) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    if (!url || !key) throw new Error("Supabase is not configured (NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY).");
    supabase = createClient(url, key);
  }
  return supabase;
}

export const authMode = MODE;

export async function getToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  if (MODE === "supabase") {
    const { data } = await sb().auth.getSession();
    return data.session?.access_token ?? null;
  }
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function setToken(token: string | null) {
  try {
    if (token) window.localStorage.setItem(TOKEN_KEY, token);
    else window.localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
}

async function post(path: string, body: unknown) {
  const res = await fetch(`${API_URL}/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.error?.details?.[0]?.msg;
    throw new Error(detail ? `${data.error.message}: ${detail}` : data?.error?.message || "Request failed.");
  }
  return data;
}

export async function login(email: string, password: string) {
  if (MODE === "supabase") {
    const { error } = await sb().auth.signInWithPassword({ email, password });
    if (error) throw new Error(error.message);
    return;
  }
  const data = await post("/auth/login", { email, password });
  setToken(data.access_token);
}

export async function register(email: string, password: string) {
  if (MODE === "supabase") {
    const { data, error } = await sb().auth.signUp({ email, password });
    if (error) throw new Error(error.message);
    if (!data.session) throw new Error("Check your email to confirm your account, then log in.");
    return;
  }
  const data = await post("/auth/register", { email, password });
  setToken(data.access_token);
}

export async function logout() {
  if (MODE === "supabase") {
    await sb().auth.signOut();
    return;
  }
  setToken(null);
}

/** Returns a dev-only token when the backend is not in production (no mail service in development). */
export async function requestPasswordReset(email: string): Promise<string | null> {
  if (MODE === "supabase") {
    const { error } = await sb().auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/reset-password` });
    if (error) throw new Error(error.message);
    return null;
  }
  const data = await post("/auth/password-reset/request", { email });
  return data.dev_reset_token ?? null;
}

export async function confirmPasswordReset(token: string, newPassword: string) {
  if (MODE === "supabase") {
    const { error } = await sb().auth.updateUser({ password: newPassword });
    if (error) throw new Error(error.message);
    return;
  }
  await post("/auth/password-reset/confirm", { token, new_password: newPassword });
}

export function clearLocalSession() {
  if (MODE === "local") setToken(null);
}
