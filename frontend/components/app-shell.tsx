"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getToken, logout } from "@/lib/auth";
import { cn } from "@/lib/format";

const NAV = [
  { href: "/chat", label: "Chat", mobile: true },
  { href: "/dashboard", label: "Today", mobile: true },
  { href: "/progress", label: "Progress", mobile: true },
  { href: "/workouts", label: "Workouts", mobile: true },
  { href: "/foods", label: "Foods", mobile: false },
  { href: "/profile", label: "Profile", mobile: true },
  { href: "/settings", label: "Settings", mobile: false },
];

type Me = { id: string; email: string | null; has_profile: boolean };

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!(await getToken())) {
        router.replace("/login");
        return;
      }
      try {
        const user = await api<Me>("/auth/me");
        if (cancelled) return;
        setMe(user);
        if (!user.has_profile && pathname !== "/onboarding") router.replace("/onboarding");
      } catch {
        if (!cancelled) router.replace("/login");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  async function signOut() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    await logout();
    router.replace("/login");
  }

  if (!me) {
    return <div className="grid min-h-dvh place-items-center text-sm text-ink-soft">Loading your log…</div>;
  }

  const onboarding = pathname === "/onboarding";

  return (
    <div className="min-h-dvh md:grid md:grid-cols-[208px_1fr]">
      <aside className="hidden border-r border-line bg-surface md:flex md:min-h-dvh md:flex-col md:px-4 md:py-5">
        <Link href="/chat" className="px-2 font-display text-xl font-bold tracking-tight">
          fitpro
        </Link>
        {!onboarding && (
          <nav className="mt-8 flex flex-col gap-0.5" aria-label="Main">
            {NAV.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                aria-current={pathname.startsWith(n.href) ? "page" : undefined}
                className={cn(
                  "rounded-lg px-3 py-2 text-[15px]",
                  pathname.startsWith(n.href) ? "bg-ink text-white" : "text-ink-soft hover:bg-paper hover:text-ink",
                )}
              >
                {n.label}
              </Link>
            ))}
          </nav>
        )}
        <div className="mt-auto space-y-2 px-2 text-sm">
          <p className="truncate text-ink-faint" title={me.email ?? ""}>{me.email}</p>
          <button onClick={signOut} className="text-ink-soft underline-offset-2 hover:underline">
            Log out
          </button>
        </div>
      </aside>

      <div className="flex min-h-dvh flex-col">
        <header className="flex items-center justify-between border-b border-line bg-surface px-4 py-3 md:hidden">
          <Link href="/chat" className="font-display text-lg font-bold">fitpro</Link>
          <button onClick={signOut} className="text-sm text-ink-soft">Log out</button>
        </header>
        <main className="flex-1 pb-20 md:pb-0">{children}</main>
        {!onboarding && (
          <nav className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-line bg-surface md:hidden" aria-label="Main">
            {NAV.filter((n) => n.mobile).map((n) => (
              <Link
                key={n.href}
                href={n.href}
                aria-current={pathname.startsWith(n.href) ? "page" : undefined}
                className={cn("py-3 text-center text-[13px]", pathname.startsWith(n.href) ? "font-semibold text-ink" : "text-ink-faint")}
              >
                {n.label}
              </Link>
            ))}
          </nav>
        )}
      </div>
    </div>
  );
}
