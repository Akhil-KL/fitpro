"use client";

import Link from "next/link";
import { useState } from "react";
import { Button, ErrorNote, Field, Input } from "@/components/ui";
import { requestPasswordReset } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [devToken, setDevToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      setDevToken(await requestPasswordReset(email.trim()));
      setSent(true);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (sent) {
    return (
      <div className="space-y-4">
        <h1 className="text-[1.75rem] font-semibold">Check your email</h1>
        <p className="text-sm text-ink-soft">If {email} has an account, we sent a link to reset the password.</p>
        {devToken && (
          <p className="rounded-lg border border-line bg-surface p-3 text-sm">
            Development mode: no email service is configured.{" "}
            <Link className="font-medium underline" href={`/reset-password?token=${encodeURIComponent(devToken)}`}>
              Open the reset link
            </Link>
          </p>
        )}
        <Link className="text-sm underline-offset-2 hover:underline" href="/login">Back to log in</Link>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <h1 className="text-[1.75rem] font-semibold">Reset your password</h1>
        <p className="mt-1 text-sm text-ink-soft">Enter your email and we&apos;ll send you a reset link.</p>
      </div>
      <Field label="Email" htmlFor="email">
        <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </Field>
      <ErrorNote message={error} />
      <Button type="submit" className="w-full" disabled={busy}>Send reset link</Button>
      <Link className="block text-sm text-ink-soft underline-offset-2 hover:underline" href="/login">Back to log in</Link>
    </form>
  );
}
