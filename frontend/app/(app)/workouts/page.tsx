"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Empty, ErrorNote, Panel, PanelTitle, Spinner } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { cn, dateTime, num } from "@/lib/format";
import type { DocumentStatus, Page, PlannedExercise, WorkoutDetail, WorkoutPlan, WorkoutPlanSummary, WorkoutSummary } from "@/lib/types";
import { useApi } from "@/lib/use-api";

type Today = { plan: { id: string; name: string } | null; day: { day_number: number; name: string; description: string | null; exercises: PlannedExercise[] } | null };

function spec(e: PlannedExercise): string {
  const parts: string[] = [];
  if (e.sets && (e.rep_range || e.target_reps)) parts.push(`${e.sets} × ${e.rep_range ?? e.target_reps}`);
  else if (e.sets && e.duration_seconds) parts.push(`${e.sets} × ${e.duration_seconds}s`);
  else if (e.duration_seconds) parts.push(e.duration_seconds >= 60 ? `${num(e.duration_seconds / 60)} min` : `${e.duration_seconds}s`);
  if (e.target_weight) parts.push(`@ ${num(e.target_weight, 1)} kg`);
  return parts.join(" ");
}

export default function WorkoutsPage() {
  const [page, setPage] = useState(1);
  const today = useApi<Today>("/workout-plans/today");
  const plans = useApi<WorkoutPlanSummary[]>("/workout-plans");
  const history = useApi<Page<WorkoutSummary>>(`/workouts${qs({ page, page_size: 10 })}`);

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 md:py-8">
      <h1 className="text-[1.75rem] font-semibold">Workouts</h1>

      <section className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
        <Panel>
          <PanelTitle title="Today's workout" aside={today.data?.plan?.name} />
          {today.loading && !today.data ? <Spinner /> : !today.data?.plan ? (
            <Empty>Upload your split to see what to train each day.</Empty>
          ) : !today.data.day || today.data.day.exercises.length === 0 ? (
            <Empty>{today.data.day ? `${today.data.day.name}: ` : ""}rest day. Recover well.</Empty>
          ) : (
            <div className="px-5 pb-5 pt-1">
              <p className="font-display text-lg font-semibold">Day {today.data.day.day_number}: {today.data.day.name}</p>
              <ol className="mt-3 divide-y divide-line">
                {today.data.day.exercises.map((e, i) => (
                  <li key={i} className="flex justify-between gap-4 py-2 text-[15px]">
                    <span>{e.exercise_name}</span>
                    <span className="tabular text-ink-soft">{spec(e)}</span>
                  </li>
                ))}
              </ol>
              <p className="mt-3 text-sm text-ink-soft">Log sets in chat as you go, e.g. “{today.data.day.exercises[0].exercise_name} 60kg 4x8”.</p>
            </div>
          )}
        </Panel>
        <Upload onDone={() => { today.reload(); plans.reload(); }} />
      </section>

      <Plans plans={plans.data} onChange={() => { plans.reload(); today.reload(); }} />

      <Panel>
        <PanelTitle title="History" aside={history.data ? `${history.data.total} sessions` : undefined} />
        <ErrorNote message={history.error} />
        {!history.data ? <Spinner /> : history.data.items.length === 0 ? (
          <Empty>No workouts yet. Tell the chat what you did, like “squats 100kg 5x5”.</Empty>
        ) : (
          <>
            <ul className="divide-y divide-line">
              {history.data.items.map((w) => <HistoryRow key={w.id} w={w} />)}
            </ul>
            <div className="flex justify-between px-5 py-3">
              <Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage((p) => p - 1)}>Newer</Button>
              <Button variant="secondary" size="sm" disabled={page * 10 >= history.data.total} onClick={() => setPage((p) => p + 1)}>Older</Button>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}

function HistoryRow({ w }: { w: WorkoutSummary }) {
  const [open, setOpen] = useState(false);
  const [detail, setDetail] = useState<WorkoutDetail | null>(null);

  async function toggle() {
    setOpen((o) => !o);
    if (!detail) setDetail(await api<WorkoutDetail>(`/workouts/${w.id}`));
  }
  return (
    <li>
      <button onClick={toggle} aria-expanded={open} className="flex w-full items-start justify-between gap-4 px-5 py-3 text-left hover:bg-paper/60">
        <div>
          <p className="font-medium">{dateTime(w.started_at)}{w.plan_day_name ? ` — ${w.plan_day_name}` : ""}</p>
          <p className="text-sm capitalize text-ink-soft">{w.exercise_names.join(", ")}</p>
        </div>
        <div className="tabular shrink-0 text-right text-sm text-ink-soft">
          <p>{w.set_count} sets</p>
          {w.total_volume_kg > 0 && <p>{num(w.total_volume_kg)} kg</p>}
        </div>
      </button>
      {open && (
        <div className="px-5 pb-4">
          {!detail ? <Spinner /> : (
            <table className="w-full text-sm">
              <tbody>
                {detail.exercises.map((e) => (
                  <tr key={e.id} className="border-t border-line align-top">
                    <td className="py-2 pr-4 capitalize">{e.exercise_name}</td>
                    <td className="tabular py-2 text-ink-soft">
                      {e.sets.map((s) => [s.reps ? `${s.reps}` : null, s.weight_kg ? `${num(s.weight_kg, 1)} kg` : null,
                        s.duration_seconds ? `${s.duration_seconds}s` : null].filter(Boolean).join(" × ")).join(", ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </li>
  );
}

function Upload({ onDone }: { onDone: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [doc, setDoc] = useState<DocumentStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!doc || doc.processing_status === "completed" || doc.processing_status === "failed") return;
    const t = setTimeout(async () => {
      try {
        const next = await api<DocumentStatus>(`/documents/${doc.id}`);
        setDoc(next);
        if (next.processing_status === "completed") onDone();
      } catch (e) {
        setError((e as Error).message);
      }
    }, 1200);
    return () => clearTimeout(t);
  }, [doc, onDone]);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const created = await api<DocumentStatus>("/workout-plans/upload", { form });
      setDoc(created);
      if (fileRef.current) fileRef.current.value = "";
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const status = doc?.processing_status;
  return (
    <Panel>
      <PanelTitle title="Import a workout plan" />
      <form onSubmit={upload} className="space-y-3 px-5 pb-5 pt-2">
        <p className="text-sm text-ink-soft">
          PDF or TXT, up to 5 MB. Use lines like “Day 1 - Push” followed by “Bench Press 4x8”.
        </p>
        <label htmlFor="plan-file" className="sr-only">Workout plan file</label>
        <input id="plan-file" ref={fileRef} type="file" accept=".pdf,.txt,application/pdf,text/plain" required
          className="block w-full text-sm file:mr-3 file:rounded-lg file:border file:border-line file:bg-paper file:px-3 file:py-2 file:text-ink" />
        <Button type="submit" disabled={busy}>{busy ? "Uploading…" : "Import plan"}</Button>
        <ErrorNote message={error} />
        {doc && (
          <p role="status" className={cn("text-sm", status === "failed" ? "text-danger" : status === "completed" ? "text-fat" : "text-ink-soft")}>
            {status === "completed" && "Your workout plan has been imported. Ask the chat “what is today's workout?”"}
            {status === "failed" && `Couldn't import ${doc.file_name}: ${doc.error_message ?? "processing failed."}`}
            {(status === "pending" || status === "processing") && `Reading ${doc.file_name}…`}
          </p>
        )}
      </form>
    </Panel>
  );
}

function Plans({ plans, onChange }: { plans: WorkoutPlanSummary[] | null; onChange: () => void }) {
  const [open, setOpen] = useState<WorkoutPlan | null>(null);
  if (!plans || plans.length === 0) return null;
  return (
    <Panel>
      <PanelTitle title="Your plans" />
      <ul className="divide-y divide-line">
        {plans.map((p) => (
          <li key={p.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
            <div>
              <p className="font-medium">{p.name}{p.is_active && <span className="ml-2 rounded-full bg-fat/10 px-2 py-0.5 text-xs text-fat">Active</span>}</p>
              <p className="text-sm text-ink-soft">{p.day_count} days, imported {dateTime(p.created_at)}</p>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={async () => setOpen(open?.id === p.id ? null : await api<WorkoutPlan>(`/workout-plans/${p.id}`))}>
                {open?.id === p.id ? "Hide days" : "View days"}
              </Button>
              {!p.is_active && (
                <Button variant="secondary" size="sm" onClick={async () => { await api(`/workout-plans/${p.id}/activate`, { method: "POST" }); onChange(); }}>
                  Make active
                </Button>
              )}
            </div>
            {open?.id === p.id && (
              <div className="grid w-full gap-4 pt-2 sm:grid-cols-2">
                {open.days.map((d) => (
                  <div key={d.id}>
                    <p className="text-sm font-semibold">Day {d.day_number}: {d.name}</p>
                    {d.exercises.length === 0 ? <p className="text-sm text-ink-soft">{d.description ?? "Rest"}</p> : (
                      <ul className="text-sm text-ink-soft">
                        {d.exercises.map((e, i) => <li key={i}>{e.exercise_name} <span className="tabular">{spec(e)}</span></li>)}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </Panel>
  );
}
