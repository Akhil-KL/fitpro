"use client";

import { useState } from "react";
import { Button, Empty, ErrorNote, Field, Input, Panel, PanelTitle, Select, Spinner } from "@/components/ui";
import { api, qs } from "@/lib/api";
import { amount, dateTime, num } from "@/lib/format";
import type { Food, FoodLog, Page } from "@/lib/types";
import { useApi } from "@/lib/use-api";

const BLANK = { name: "", serving_size: "100", serving_unit: "g", calories: "", protein_g: "", carbs_g: "", fat_g: "", fiber_g: "" };

export default function FoodsPage() {
  const [q, setQ] = useState("");
  const [term, setTerm] = useState("");
  const [logPage, setLogPage] = useState(1);
  const search = useApi<Page<Food>>(term ? `/foods/search${qs({ q: term, page_size: 15 })}` : null);
  const custom = useApi<Food[]>("/foods/custom");
  const logs = useApi<Page<FoodLog>>(`/food-logs${qs({ page: logPage, page_size: 15 })}`);
  const [form, setForm] = useState(BLANK);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function saveCustom(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const body = {
      name: form.name,
      serving_size: Number(form.serving_size),
      serving_unit: form.serving_unit,
      calories: Number(form.calories),
      protein_g: Number(form.protein_g || 0),
      carbs_g: Number(form.carbs_g || 0),
      fat_g: Number(form.fat_g || 0),
      fiber_g: Number(form.fiber_g || 0),
    };
    try {
      await api(editing ? `/foods/custom/${editing}` : "/foods/custom", { method: editing ? "PUT" : "POST", body });
      setForm(BLANK);
      setEditing(null);
      custom.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(id: string) {
    setError(null);
    try {
      await api(`/foods/custom/${id}`, { method: "DELETE" });
      custom.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function deleteLog(id: string) {
    await api(`/food-logs/${id}`, { method: "DELETE" });
    logs.reload();
  }

  const set = (k: keyof typeof BLANK) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setForm({ ...form, [k]: e.target.value });

  return (
    <div className="mx-auto max-w-5xl space-y-6 px-4 py-6 md:py-8">
      <h1 className="text-[1.75rem] font-semibold">Foods</h1>

      <Panel>
        <PanelTitle title="Look up a food" />
        <form className="flex gap-2 px-5 pb-4 pt-2" onSubmit={(e) => { e.preventDefault(); setTerm(q.trim()); }}>
          <label htmlFor="food-q" className="sr-only">Food name</label>
          <Input id="food-q" placeholder="paneer, roti, oats…" value={q} onChange={(e) => setQ(e.target.value)} />
          <Button type="submit" variant="secondary">Search</Button>
        </form>
        {search.loading && <Spinner label="Searching" />}
        {search.data && (search.data.items.length === 0 ? <Empty>No foods match “{term}”. Add it below as a custom food.</Empty> : (
          <FoodTable foods={search.data.items} />
        ))}
      </Panel>

      <section className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <Panel>
          <PanelTitle title={editing ? "Edit custom food" : "Add a custom food"} />
          <form onSubmit={saveCustom} className="grid grid-cols-2 gap-3 px-5 pb-5 pt-2">
            <div className="col-span-2"><Field label="Name" htmlFor="cf-name"><Input id="cf-name" required value={form.name} onChange={set("name")} /></Field></div>
            <Field label="Amount" htmlFor="cf-size"><Input id="cf-size" type="number" step="any" min="0.01" required value={form.serving_size} onChange={set("serving_size")} /></Field>
            <Field label="Per" htmlFor="cf-unit">
              <Select id="cf-unit" value={form.serving_unit} onChange={set("serving_unit")}>
                <option value="g">grams</option><option value="ml">ml</option><option value="piece">piece</option><option value="serving">serving</option>
              </Select>
            </Field>
            <Field label="Calories (kcal)" htmlFor="cf-cal"><Input id="cf-cal" type="number" step="any" min="0" required value={form.calories} onChange={set("calories")} /></Field>
            <Field label="Protein (g)" htmlFor="cf-p"><Input id="cf-p" type="number" step="any" min="0" value={form.protein_g} onChange={set("protein_g")} /></Field>
            <Field label="Carbs (g)" htmlFor="cf-c"><Input id="cf-c" type="number" step="any" min="0" value={form.carbs_g} onChange={set("carbs_g")} /></Field>
            <Field label="Fat (g)" htmlFor="cf-f"><Input id="cf-f" type="number" step="any" min="0" value={form.fat_g} onChange={set("fat_g")} /></Field>
            <Field label="Fiber (g)" htmlFor="cf-fi"><Input id="cf-fi" type="number" step="any" min="0" value={form.fiber_g} onChange={set("fiber_g")} /></Field>
            <div className="col-span-2 flex gap-2 pt-1">
              <Button type="submit">{editing ? "Save changes" : "Add food"}</Button>
              {editing && <Button type="button" variant="ghost" onClick={() => { setEditing(null); setForm(BLANK); }}>Cancel</Button>}
            </div>
            <div className="col-span-2"><ErrorNote message={error} /></div>
            <p className="col-span-2 text-xs text-ink-faint">Edits apply to future logs. Past entries keep the nutrition they were logged with.</p>
          </form>
        </Panel>

        <Panel>
          <PanelTitle title="Your custom foods" />
          {!custom.data ? <Spinner /> : custom.data.length === 0 ? (
            <Empty>Foods you add here — or describe in chat — are saved for next time.</Empty>
          ) : (
            <FoodTable foods={custom.data} actions={(f) => (
              <div className="flex justify-end gap-1">
                <Button variant="ghost" size="sm" onClick={() => {
                  setEditing(f.id);
                  setForm({ name: f.name, serving_size: String(f.serving_size), serving_unit: f.serving_unit, calories: String(f.calories),
                    protein_g: String(f.protein_g), carbs_g: String(f.carbs_g), fat_g: String(f.fat_g), fiber_g: String(f.fiber_g) });
                }}>Edit</Button>
                <Button variant="ghost" size="sm" onClick={() => remove(f.id)}>Delete</Button>
              </div>
            )} />
          )}
        </Panel>
      </section>

      <Panel>
        <PanelTitle title="Food history" aside={logs.data ? `${logs.data.total} entries` : undefined} />
        {!logs.data ? <Spinner /> : logs.data.items.length === 0 ? <Empty>Nothing logged yet.</Empty> : (
          <>
            <div className="overflow-x-auto">
              <table className="mt-2 w-full min-w-[560px] text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-ink-soft">
                    <th className="px-5 py-2 font-medium">When</th>
                    <th className="px-5 py-2 font-medium">Food</th>
                    <th className="px-5 py-2 text-right font-medium">kcal</th>
                    <th className="px-5 py-2 text-right font-medium">Protein</th>
                    <th className="px-5 py-2"><span className="sr-only">Actions</span></th>
                  </tr>
                </thead>
                <tbody>
                  {logs.data.items.map((l) => (
                    <tr key={l.id} className="border-b border-line last:border-0">
                      <td className="whitespace-nowrap px-5 py-2 text-ink-soft">{dateTime(l.logged_at)}</td>
                      <td className="px-5 py-2">
                        {amount(l.quantity, l.unit, l.food_name)}
                        {l.nutrition?.calculation_source === "user_override" && <span className="ml-2 text-xs text-carbs">edited</span>}
                      </td>
                      <td className="tabular px-5 py-2 text-right">{num(l.nutrition?.calories)}</td>
                      <td className="tabular px-5 py-2 text-right">{num(l.nutrition?.protein_g, 1)} g</td>
                      <td className="px-5 py-2 text-right"><Button variant="ghost" size="sm" onClick={() => deleteLog(l.id)}>Delete</Button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-between px-5 py-3">
              <Button variant="secondary" size="sm" disabled={logPage === 1} onClick={() => setLogPage((p) => p - 1)}>Newer</Button>
              <Button variant="secondary" size="sm" disabled={logPage * 15 >= logs.data.total} onClick={() => setLogPage((p) => p + 1)}>Older</Button>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}

function FoodTable({ foods, actions }: { foods: Food[]; actions?: (f: Food) => React.ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[520px] text-sm">
        <thead>
          <tr className="border-b border-line text-left text-ink-soft">
            <th className="px-5 py-2 font-medium">Food</th>
            <th className="px-5 py-2 font-medium">Per</th>
            <th className="px-5 py-2 text-right font-medium">kcal</th>
            <th className="px-5 py-2 text-right font-medium">P / C / F (g)</th>
            {actions && <th className="px-5 py-2"><span className="sr-only">Actions</span></th>}
          </tr>
        </thead>
        <tbody>
          {foods.map((f) => (
            <tr key={f.id} className="border-b border-line last:border-0">
              <td className="px-5 py-2">{f.name}{f.is_custom && !actions && <span className="ml-2 text-xs text-protein">yours</span>}</td>
              <td className="px-5 py-2 text-ink-soft">{num(f.serving_size, 2)} {f.serving_unit}</td>
              <td className="tabular px-5 py-2 text-right">{num(f.calories)}</td>
              <td className="tabular px-5 py-2 text-right">{num(f.protein_g, 1)} / {num(f.carbs_g, 1)} / {num(f.fat_g, 1)}</td>
              {actions && <td className="px-5 py-1">{actions(f)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
