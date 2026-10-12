"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Button, ErrorNote, Field, Input } from "@/components/ui";
import { confirmPasswordReset } from "@/lib/auth";

function ResetForm() {
  const token = useSearchParams().get("token") ?? "";
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await confirmPasswordReset(token, password);
      setDone(true);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (done) {
    return (
      <div className="space-y-4">
        <h1 className="text-[1.75rem] font-semibold">Password updated</h1>
        <Link className="font-medium underline" href="/login">Log in</Link>
      </div>
    );
  }
  return (
    <form onSubmit={submit} className="space-y-5">
      <h1 className="text-[1.75rem] font-semibold">Choose a new password</h1>
      <Field label="New password" htmlFor="password" hint="At least 8 characters.">
        <Input id="password" type="password" autoComplete="new-password" minLength={8} required value={password}
          onChange={(e) => setPassword(e.target.value)} />
      </Field>
      <ErrorNote message={error} />
      <Button type="submit" className="w-full">Update password</Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetForm />
    </Suspense>
  );
}
