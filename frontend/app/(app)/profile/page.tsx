"use client";

import { useState } from "react";
import { ProfileForm } from "@/components/profile-form";
import { Panel } from "@/components/ui";
import { num } from "@/lib/format";
import type { Profile, Targets } from "@/lib/types";
import { useApi } from "@/lib/use-api";

export default function ProfilePage() {
  const [saved, setSaved] = useState(0);
  const { data: targets, reload } = useApi<Targets>("/targets");
  const { data: profile, reload: reloadProfile } = useApi<Profile>("/profile");

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-4 py-8">
      <div>
        <h1 className="text-[1.75rem] font-semibold">Profile</h1>
        <p className="mt-1 text-ink-soft">Changing your weight, activity or goal creates new targets from today; past days keep theirs.</p>
      </div>

      {targets && profile && (
        <Panel className="flex flex-wrap gap-x-8 gap-y-3 px-5 py-4 text-sm">
          <Stat label="Calories" value={`${num(targets.calorie_target)} kcal`} />
          <Stat label="Protein" value={`${targets.protein_target_g} g`} />
          <Stat label="Carbs" value={`${targets.carbs_target_g} g`} />
          <Stat label="Fat" value={`${targets.fat_target_g} g`} />
          <Stat label="Water" value={`${num(targets.water_target_ml)} ml`} />
          <Stat label="BMR / TDEE" value={`${num(profile.bmr)} / ${num(profile.tdee)}`} />
          <Stat label="BMI" value={`${profile.bmi ?? "–"}`} />
        </Panel>
      )}

      <ProfileForm
        key={saved}
        submitLabel="Save changes"
        onSaved={() => {
          setSaved((s) => s + 1);
          reload();
          reloadProfile();
        }}
      />
      {saved > 0 && <p role="status" className="text-sm text-fat">Profile saved.</p>}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-ink-soft">{label}</p>
      <p className="tabular font-display text-lg font-semibold">{value}</p>
    </div>
  );
}
