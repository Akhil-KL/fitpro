/** Presentation-only formatting. No authoritative calculations happen in the frontend. */

export function num(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return v.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

export function shortDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function time(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}

export function isoDay(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return isoDay(d);
}

export function amount(quantity: number, unit: string, name: string): string {
  const q = num(quantity, 2);
  if (unit === "piece") return quantity === 1 ? `${q} ${name}` : `${q} × ${name}`;
  if (unit === "serving") return `${q} serving${quantity === 1 ? "" : "s"} of ${name}`;
  return `${q} ${unit} ${name}`;
}

export const GOALS: Record<string, string> = {
  lose_fat: "Lose fat",
  maintain: "Maintain",
  gain_muscle: "Build muscle",
  recomp: "Recomposition",
};

export const ACTIVITY: Record<string, string> = {
  sedentary: "Sedentary (desk job, little exercise)",
  light: "Light (exercise 1–3 days/week)",
  moderate: "Moderate (exercise 3–5 days/week)",
  active: "Active (hard exercise 6–7 days/week)",
  very_active: "Very active (physical job + training)",
};

export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}
