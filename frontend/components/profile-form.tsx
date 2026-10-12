"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ACTIVITY, GOALS } from "@/lib/format";
import type { Profile } from "@/lib/types";
import { Button, ErrorNote, Field, Input, Select } from "./ui";

type FormState = {
  name: string;
  age: string;
  gender: string;
  ethnicity: string;
  height_cm: string;
  current_weight_kg: string;
  activity_level: string;
  fitness_goal: string;
  target_weight_kg: string;
  timezone: string;
};

function toForm(p: Profile | null): FormState {
  const tz = typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";
  return {
    name: p?.name ?? "",
    age: p?.age?.toString() ?? "",
    gender: p?.gender ?? "",
    ethnicity: p?.ethnicity ?? "",
    height_cm: p?.height_cm?.toString() ?? "",
    current_weight_kg: p?.current_weight_kg?.toString() ?? "",
    activity_level: p?.activity_level ?? "",
    fitness_goal: p?.fitness_goal ?? "",
    target_weight_kg: p?.target_weight_kg?.toString() ?? "",
    timezone: p?.timezone && p.timezone !== "UTC" ? p.timezone : tz,
  };
}

const n = (s: string) => (s.trim() === "" ? null : Number(s));

export function ProfileForm({ submitLabel, onSaved }: { submitLabel: string; onSaved: (p: Profile) => void }) {
  const [form, setForm] = useState<FormState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Profile>("/profile").then((p) => setForm(toForm(p))).catch((e) => setError((e as Error).message));
  }, []);

  if (!form) return error ? <ErrorNote message={error} /> : null;

  const set = (k: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      const saved = await api<Profile>("/profile", {
        method: "PUT",
        body: {
          name: form.name.trim() || null,
          age: n(form.age),
          gender: form.gender || null,
          ethnicity: form.ethnicity.trim() || null,
          height_cm: n(form.height_cm),
          current_weight_kg: n(form.current_weight_kg),
          activity_level: form.activity_level || null,
          fitness_goal: form.fitness_goal || null,
          target_weight_kg: n(form.target_weight_kg),
          timezone: form.timezone,
        },
      });
      onSaved(saved);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-3 font-display text-base font-semibold">About you</legend>
        <Field label="Name" htmlFor="name"><Input id="name" value={form.name} onChange={set("name")} autoComplete="given-name" /></Field>
        <Field label="Age" htmlFor="age"><Input id="age" type="number" inputMode="numeric" min={13} max={110} required value={form.age} onChange={set("age")} /></Field>
        <Field label="Sex" htmlFor="gender" hint="Used in the BMR formula.">
          <Select id="gender" required value={form.gender} onChange={set("gender")}>
            <option value="">Select</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other / prefer not to say</option>
          </Select>
        </Field>
        <Field label="Ethnicity (optional)" htmlFor="ethnicity" hint="Not used in any calculation.">
          <Input id="ethnicity" value={form.ethnicity} onChange={set("ethnicity")} />
        </Field>
      </fieldset>

      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-3 font-display text-base font-semibold">Body</legend>
        <Field label="Height (cm)" htmlFor="height"><Input id="height" type="number" step="0.1" min={100} max={250} required value={form.height_cm} onChange={set("height_cm")} /></Field>
        <Field label="Current weight (kg)" htmlFor="weight"><Input id="weight" type="number" step="0.1" min={25} max={350} required value={form.current_weight_kg} onChange={set("current_weight_kg")} /></Field>
      </fieldset>

      <fieldset className="grid gap-4 sm:grid-cols-2">
        <legend className="mb-3 font-display text-base font-semibold">Training and goal</legend>
        <Field label="Activity level" htmlFor="activity">
          <Select id="activity" required value={form.activity_level} onChange={set("activity_level")}>
            <option value="">Select</option>
            {Object.entries(ACTIVITY).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
        </Field>
        <Field label="Goal" htmlFor="goal">
          <Select id="goal" required value={form.fitness_goal} onChange={set("fitness_goal")}>
            <option value="">Select</option>
            {Object.entries(GOALS).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </Select>
        </Field>
        <Field label="Target weight (kg, optional)" htmlFor="target"><Input id="target" type="number" step="0.1" min={25} max={350} value={form.target_weight_kg} onChange={set("target_weight_kg")} /></Field>
        <Field label="Time zone" htmlFor="tz" hint="Decides where your day starts and ends."><Input id="tz" required value={form.timezone} onChange={set("timezone")} /></Field>
      </fieldset>

      <ErrorNote message={error} />
      <Button type="submit" disabled={busy}>{busy ? "Saving…" : submitLabel}</Button>
    </form>
  );
}
