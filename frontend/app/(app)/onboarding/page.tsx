"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { ProfileForm } from "@/components/profile-form";
import { Button, Panel } from "@/components/ui";
import { api } from "@/lib/api";
import { num } from "@/lib/format";
import type { Profile, Targets } from "@/lib/types";

export default function OnboardingPage() {
  const router = useRouter();
  const [result, setResult] = useState<{ profile: Profile; targets: Targets } | null>(null);

  async function saved(profile: Profile) {
    const targets = await api<Targets>("/targets");
    setResult({ profile, targets });
  }

  return (
    <div className="mx-auto max-w-2xl px-4 py-8 md:py-12">
      {!result ? (
        <>
          <h1 className="text-[1.75rem] font-semibold">Set up your profile</h1>
          <p className="mb-8 mt-1 text-ink-soft">This gives you daily calorie, protein and water targets. You can change it any time.</p>
          <ProfileForm submitLabel="Calculate my targets" onSaved={saved} />
        </>
      ) : (
        <div className="space-y-6">
          <h1 className="text-[1.75rem] font-semibold">Your daily targets</h1>
          <Panel className="grid grid-cols-2 gap-px overflow-hidden bg-line sm:grid-cols-3">
            {[
              ["Calories", `${num(result.targets.calorie_target)} kcal`],
              ["Protein", `${result.targets.protein_target_g} g`],
              ["Carbs", `${result.targets.carbs_target_g} g`],
              ["Fat", `${result.targets.fat_target_g} g`],
              ["Water", `${num(result.targets.water_target_ml)} ml`],
              ["BMI", `${result.profile.bmi ?? "–"} (${result.profile.bmi_category ?? ""})`],
            ].map(([k, v]) => (
              <div key={k} className="bg-surface p-4">
                <p className="text-sm text-ink-soft">{k}</p>
                <p className="tabular font-display text-xl font-semibold">{v}</p>
              </div>
            ))}
          </Panel>
          <p className="text-sm text-ink-soft">
            Based on a BMR of {num(result.profile.bmr)} kcal and a maintenance (TDEE) of {num(result.profile.tdee)} kcal.
          </p>
          <Button onClick={() => router.replace("/chat")}>Start logging</Button>
        </div>
      )}
    </div>
  );
}
