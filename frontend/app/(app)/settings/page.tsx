"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button, Panel, PanelTitle } from "@/components/ui";
import { API_URL, authMode, logout } from "@/lib/auth";
import { useApi } from "@/lib/use-api";

export default function SettingsPage() {
  const router = useRouter();
  const { data: me } = useApi<{ email: string | null }>("/auth/me");

  return (
    <div className="mx-auto max-w-2xl space-y-6 px-4 py-6 md:py-8">
      <h1 className="text-[1.75rem] font-semibold">Settings</h1>

      <Panel>
        <PanelTitle title="Account" />
        <div className="space-y-3 px-5 pb-5 pt-2 text-sm">
          <p>Signed in as <span className="font-medium">{me?.email ?? "…"}</span></p>
          <div className="flex flex-wrap gap-2">
            {authMode === "local" && (
              <Link href="/forgot-password" className="inline-flex h-8 items-center rounded-lg border border-line bg-surface px-3 hover:bg-paper">
                Change password
              </Link>
            )}
            <Button variant="secondary" size="sm" onClick={async () => { await logout(); router.replace("/login"); }}>Log out</Button>
          </div>
        </div>
      </Panel>

      <Panel>
        <PanelTitle title="Your data" />
        <ul className="space-y-2 px-5 pb-5 pt-2 text-sm">
          <li><Link className="text-protein underline-offset-2 hover:underline" href="/profile">Profile and targets</Link></li>
          <li><Link className="text-protein underline-offset-2 hover:underline" href="/foods">Custom foods and food history</Link></li>
          <li><Link className="text-protein underline-offset-2 hover:underline" href="/workouts">Workout plans and history</Link></li>
        </ul>
      </Panel>

      <Panel>
        <PanelTitle title="Connection" />
        <p className="px-5 pb-5 pt-2 text-sm text-ink-soft">
          Backend: <code className="text-ink">{API_URL}</code>. Sign-in: {authMode === "supabase" ? "Supabase Auth" : "email and password"}.
        </p>
      </Panel>
    </div>
  );
}
