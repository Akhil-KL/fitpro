"use client";

import Link from "next/link";
import { CaloriesBars, MacroDonut, TrendLine } from "@/components/charts";
import { MacroLegend, TargetMeter } from "@/components/macro-bar";
import { Empty, ErrorNote, Panel, PanelTitle, Spinner } from "@/components/ui";
import { amount, num, time } from "@/lib/format";
import type { Summary } from "@/lib/types";
import { useApi } from "@/lib/use-api";

const MEAL_ORDER = ["breakfast", "lunch", "snack", "dinner", "unspecified"];
const MEAL_LABEL: Record<string, string> = { breakfast: "Breakfast", lunch: "Lunch", snack: "Snacks", dinner: "Dinner", unspecified: "Other" };

export default function DashboardPage() {
  const { data, error, loading } = useApi<Summary>("/analytics/summary");

  if (loading && !data) return <Spinner label="Loading today" />;
  if (error) return <div className="p-6"><ErrorNote message={error} /></div>;
  if (!data) return null;

  const t = data.today;
  const cal = t.calories;
  const remaining = cal.remaining;
  const week = data.week.nutrition;

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 md:py-8">
      <section className="grid gap-6 lg:grid-cols-[1.4fr_1fr]">
        <div>
          <p className="text-sm text-ink-soft">
            {new Date(`${t.date}T00:00:00`).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })}
          </p>
          <h1 className="mt-1 font-display text-[2.6rem] font-semibold leading-none tabular sm:text-[3.25rem]">
            {num(cal.consumed)}
            <span className="text-ink-faint">{cal.target ? ` / ${num(cal.target)}` : ""} kcal</span>
          </h1>
          <p className="mt-2 text-ink-soft">
            {remaining === null || remaining === undefined
              ? "Complete your profile to see what's left for today."
              : remaining >= 0
                ? `${num(remaining)} kcal left today.`
                : `${num(-remaining)} kcal over today's target.`}
          </p>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            <TargetMeter label="Protein" consumed={t.protein_g.consumed} target={t.protein_g.target} unit="g" color="bg-protein" />
            <TargetMeter label="Carbs" consumed={t.carbs_g.consumed} target={t.carbs_g.target} unit="g" color="bg-carbs" />
            <TargetMeter label="Fat" consumed={t.fat_g.consumed} target={t.fat_g.target} unit="g" color="bg-fat" />
            <TargetMeter label="Water" consumed={t.water_ml.consumed} target={t.water_ml.target} unit="ml" color="bg-water" />
          </div>
        </div>

        <Panel className="flex flex-col">
          <PanelTitle title="Macro split" aside="share of calories" />
          <MacroDonut {...t.macro_distribution} />
          <div className="px-5 pb-4">
            <MacroLegend protein={t.protein_g.consumed ?? 0} carbs={t.carbs_g.consumed ?? 0} fat={t.fat_g.consumed ?? 0} />
          </div>
        </Panel>
      </section>

      <section className="grid gap-6 lg:grid-cols-3">
        <Panel>
          <PanelTitle title="Training" />
          <div className="px-5 pb-5 pt-2 text-sm">
            {t.workout.completed ? (
              <>
                <ul className="space-y-1">{t.workout.exercises.map((e, i) => <li key={i}>{e}</li>)}</ul>
                {t.workout.volume_kg > 0 && <p className="mt-2 text-ink-soft">{num(t.workout.volume_kg)} kg volume</p>}
              </>
            ) : (
              <p className="text-ink-soft">
                Nothing logged yet. <Link className="text-protein underline-offset-2 hover:underline" href="/workouts">See today&apos;s plan</Link>
              </p>
            )}
          </div>
        </Panel>
        <Panel>
          <PanelTitle title="Body weight" aside={data.weight.current_weight_kg ? `${num(data.weight.current_weight_kg, 1)} kg` : undefined} />
          {data.weight.points.length > 1 ? (
            <div className="px-2 pb-3"><TrendLine points={data.weight.points} xKey="date" yKey="weight_kg" unit="kg" height={140} target={data.weight.target_weight_kg} /></div>
          ) : (
            <Empty>Log your weight in chat — “my weight is 70kg” — to see a trend.</Empty>
          )}
        </Panel>
        <Panel>
          <PanelTitle title="Recent" />
          {data.recent_activity.length ? (
            <ul className="divide-y divide-line px-5 pb-3 text-sm">
              {data.recent_activity.slice(0, 6).map((r) => (
                <li key={r.id} className="flex justify-between gap-3 py-2">
                  <span className="truncate">{r.label}</span>
                  <span className="tabular shrink-0 text-ink-soft">{r.calories} kcal</span>
                </li>
              ))}
            </ul>
          ) : (
            <Empty>No entries yet. <Link className="text-protein" href="/chat">Log your first meal</Link></Empty>
          )}
        </Panel>
      </section>

      <Panel>
        <PanelTitle
          title="Last 7 days"
          aside={`Average ${num(week.averages.calories)} kcal and ${num(week.averages.protein_g)} g protein a day`}
        />
        <div className="grid gap-2 px-2 pb-3 md:grid-cols-2">
          <CaloriesBars points={week.points} target={week.targets?.calories} />
          <CaloriesBars points={week.points} target={week.targets?.protein_g} dataKey="protein_g" color="#2F5BEA" unit="g" />
        </div>
      </Panel>

      <Panel>
        <PanelTitle title="Today's food" aside={`${t.food_log_count} entries`} />
        {t.food_log_count === 0 ? (
          <Empty>Tell the chat what you ate and it shows up here.</Empty>
        ) : (
          <div className="grid gap-x-8 gap-y-4 px-5 pb-5 pt-2 sm:grid-cols-2">
            {MEAL_ORDER.filter((k) => t.meals[k]?.length).map((k) => (
              <div key={k}>
                <h3 className="mb-1 text-sm font-semibold">{MEAL_LABEL[k]}</h3>
                <ul className="text-sm">
                  {t.meals[k].map((i) => (
                    <li key={i.id} className="flex justify-between gap-3 py-1">
                      <span>{amount(i.quantity, i.unit, i.food_name)}</span>
                      <span className="tabular shrink-0 text-ink-soft">{num(i.calories)} kcal <span className="text-ink-faint">{time(i.logged_at)}</span></span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
