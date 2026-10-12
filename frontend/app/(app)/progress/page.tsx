"use client";

import { useState } from "react";
import { CaloriesBars, MacroDonut, TrendLine } from "@/components/charts";
import { Empty, ErrorNote, Field, Input, Panel, PanelTitle, Select, Spinner } from "@/components/ui";
import { qs } from "@/lib/api";
import { cn, daysAgo, isoDay, num } from "@/lib/format";
import type { NutritionSeries, WeightAnalytics, WorkoutAnalytics } from "@/lib/types";
import { useApi } from "@/lib/use-api";

const RANGES = [
  { label: "7 days", days: 7 },
  { label: "30 days", days: 30 },
  { label: "90 days", days: 90 },
  { label: "1 year", days: 365 },
];

export default function ProgressPage() {
  const [days, setDays] = useState<number | "custom">(30);
  const [custom, setCustom] = useState({ from: daysAgo(13), to: isoDay(new Date()) });
  const [exercise, setExercise] = useState<string>("");

  const range = days === "custom" ? custom : { from: daysAgo(days - 1), to: isoDay(new Date()) };
  const nutrition = useApi<NutritionSeries>(`/analytics/nutrition${qs({ ...range, granularity: "auto" })}`);
  const weight = useApi<WeightAnalytics>(`/analytics/weight${qs(range)}`);
  const workouts = useApi<WorkoutAnalytics>(`/analytics/workouts${qs({ ...range, exercise: exercise || null })}`);

  const n = nutrition.data;
  const w = weight.data;
  const wk = workouts.data;
  const basis = n?.value_basis === "daily_average" ? `Daily average per ${n.granularity === "weekly" ? "week" : "month"}` : "Per day";

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 md:py-8">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="text-[1.75rem] font-semibold">Progress</h1>
        <div className="flex flex-wrap items-end gap-2" role="group" aria-label="Date range">
          {RANGES.map((r) => (
            <button key={r.days} onClick={() => setDays(r.days)} aria-pressed={days === r.days}
              className={cn("rounded-full px-3 py-1.5 text-sm", days === r.days ? "bg-ink text-white" : "border border-line bg-surface text-ink-soft hover:text-ink")}>
              {r.label}
            </button>
          ))}
          <button onClick={() => setDays("custom")} aria-pressed={days === "custom"}
            className={cn("rounded-full px-3 py-1.5 text-sm", days === "custom" ? "bg-ink text-white" : "border border-line bg-surface text-ink-soft hover:text-ink")}>
            Custom
          </button>
        </div>
      </div>
      {days === "custom" && (
        <div className="flex flex-wrap gap-3">
          <Field label="From" htmlFor="from"><Input id="from" type="date" value={custom.from} max={custom.to} onChange={(e) => setCustom({ ...custom, from: e.target.value })} /></Field>
          <Field label="To" htmlFor="to"><Input id="to" type="date" value={custom.to} min={custom.from} onChange={(e) => setCustom({ ...custom, to: e.target.value })} /></Field>
        </div>
      )}

      <ErrorNote message={nutrition.error || weight.error || workouts.error} />

      <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Panel>
          <PanelTitle title="Calories" aside={basis} />
          {n ? <div className="px-2 pb-3"><CaloriesBars points={n.points} target={n.targets?.calories} /></div> : <Spinner />}
        </Panel>
        <Panel>
          <PanelTitle title="Macro split" aside="share of calories" />
          {n ? (
            <>
              <MacroDonut {...n.macro_distribution} />
              <dl className="grid grid-cols-2 gap-3 px-5 pb-5 text-sm">
                <div><dt className="text-ink-soft">Avg calories</dt><dd className="tabular font-display text-lg font-semibold">{num(n.averages.calories)}</dd></div>
                <div><dt className="text-ink-soft">Avg protein</dt><dd className="tabular font-display text-lg font-semibold">{num(n.averages.protein_g, 1)} g</dd></div>
                <div><dt className="text-ink-soft">Days logged</dt><dd className="tabular font-display text-lg font-semibold">{n.averages.logged_days}</dd></div>
                {n.calorie_adherence_pct !== null && (
                  <div><dt className="text-ink-soft">Within 10% of target</dt><dd className="tabular font-display text-lg font-semibold">{num(n.calorie_adherence_pct)}%</dd></div>
                )}
              </dl>
            </>
          ) : <Spinner />}
        </Panel>
      </section>

      <Panel>
        <PanelTitle title="Protein" aside={n?.targets ? `target ${n.targets.protein_g} g` : undefined} />
        {n ? <div className="px-2 pb-3"><TrendLine points={n.points} xKey="period_start" yKey="protein_g" unit="g" color="#2F5BEA" target={n.targets?.protein_g} /></div> : <Spinner />}
      </Panel>

      <section className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Panel>
          <PanelTitle title="Body weight" />
          {w && w.points.length ? (
            <div className="px-2 pb-3"><TrendLine points={w.points} xKey="date" yKey="weight_kg" unit="kg" target={w.target_weight_kg} /></div>
          ) : w ? <Empty>No weight entries in this range.</Empty> : <Spinner />}
        </Panel>
        <Panel>
          <PanelTitle title="Weight summary" />
          {w && (
            <dl className="grid grid-cols-2 gap-4 px-5 pb-5 pt-2 text-sm">
              <Stat label="Current" value={w.current_weight_kg !== null ? `${num(w.current_weight_kg, 1)} kg` : "–"} />
              <Stat label="Starting" value={w.starting_weight_kg !== null ? `${num(w.starting_weight_kg, 1)} kg` : "–"} />
              <Stat label="Total change" value={w.change_kg !== null ? `${w.change_kg > 0 ? "+" : ""}${num(w.change_kg, 2)} kg` : "–"} />
              <Stat label="Per week" value={w.avg_weekly_change_kg !== null ? `${num(w.avg_weekly_change_kg, 2)} kg` : "needs 7+ days"} />
              <Stat label="Target" value={w.target_weight_kg ? `${num(w.target_weight_kg, 1)} kg` : "not set"} />
              <Stat label="Toward target" value={w.progress_pct !== null ? `${num(w.progress_pct)}%` : "–"} />
            </dl>
          )}
        </Panel>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <Panel>
          <PanelTitle title="Workout frequency" aside={wk ? `${num(wk.weekly_frequency, 1)} sessions a week` : undefined} />
          {wk ? (
            <>
              <div className="px-2"><CaloriesBars points={wk.frequency} dataKey="workouts" color="#15213B" unit="workouts" /></div>
              <dl className="grid grid-cols-3 gap-3 px-5 pb-5 text-sm">
                <Stat label="Workouts" value={String(wk.workout_count)} />
                <Stat label="Sets" value={num(wk.total_sets)} />
                <Stat label="Volume" value={`${num(wk.total_volume_kg)} kg`} />
              </dl>
            </>
          ) : <Spinner />}
        </Panel>
        <Panel>
          <PanelTitle title="Exercise progression" />
          {wk && wk.exercises.length ? (
            <>
              <div className="px-5 pt-2">
                <label htmlFor="exercise" className="sr-only">Exercise</label>
                <Select id="exercise" value={exercise || wk.progression_exercise || ""} onChange={(e) => setExercise(e.target.value)}>
                  {wk.exercises.map((e) => <option key={e.exercise} value={e.exercise}>{e.exercise}</option>)}
                </Select>
              </div>
              {wk.progression.length ? (
                <div className="px-2 pb-3"><TrendLine points={wk.progression} xKey="date" yKey="top_weight_kg" unit="kg" color="#2E9C86" /></div>
              ) : <Empty>No weighted sets for this exercise in the range.</Empty>}
            </>
          ) : wk ? <Empty>Log a lift in chat — “squats 100kg 5x5” — to track progression.</Empty> : <Spinner />}
        </Panel>
      </section>

      {wk && wk.personal_records.length > 0 && (
        <Panel>
          <PanelTitle title="Best lifts in this range" aside="estimated 1-rep max uses the Epley formula" />
          <table className="mt-2 w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-ink-soft">
                <th className="px-5 py-2 font-medium">Exercise</th>
                <th className="px-5 py-2 text-right font-medium">Heaviest</th>
                <th className="px-5 py-2 text-right font-medium">Est. 1RM</th>
              </tr>
            </thead>
            <tbody>
              {wk.personal_records.map((p) => (
                <tr key={p.exercise} className="border-b border-line last:border-0">
                  <td className="px-5 py-2 capitalize">{p.exercise}</td>
                  <td className="tabular px-5 py-2 text-right">{num(p.best_weight_kg, 1)} kg</td>
                  <td className="tabular px-5 py-2 text-right">{num(p.best_e1rm_kg, 1)} kg</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-ink-soft">{label}</dt>
      <dd className="tabular font-display text-lg font-semibold">{value}</dd>
    </div>
  );
}
