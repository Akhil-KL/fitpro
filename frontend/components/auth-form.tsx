"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { login, register } from "@/lib/auth";
import { Button, ErrorNote, Field, Input } from "./ui";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      if (isLogin) await login(email.trim(), password);
      else await register(email.trim(), password);
      router.replace(isLogin ? "/chat" : "/onboarding");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h1 className="text-[1.75rem] font-semibold">{isLogin ? "Log in" : "Create your account"}</h1>
        <p className="mt-1 text-sm text-ink-soft">
          {isLogin ? "Pick up your log where you left it." : "Then set up your profile to get calorie and protein targets."}
        </p>
      </div>
      <Field label="Email" htmlFor="email">
        <Input id="email" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <Field label="Password" htmlFor="password" hint={isLogin ? undefined : "At least 8 characters."}>
        <Input
          id="password"
          type="password"
          autoComplete={isLogin ? "current-password" : "new-password"}
          required
          minLength={isLogin ? 1 : 8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </Field>
      <ErrorNote message={error} />
      <Button type="submit" className="w-full" disabled={busy}>
        {busy ? "Please wait…" : isLogin ? "Log in" : "Create account"}
      </Button>
      <div className="flex justify-between text-sm text-ink-soft">
        {isLogin ? (
          <>
            <Link className="underline-offset-2 hover:underline" href="/register">Create an account</Link>
            <Link className="underline-offset-2 hover:underline" href="/forgot-password">Forgot password?</Link>
          </>
        ) : (
          <Link className="underline-offset-2 hover:underline" href="/login">I already have an account</Link>
        )}
      </div>
    </form>
  );
}
