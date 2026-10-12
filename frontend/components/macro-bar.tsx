import { num } from "@/lib/format";

/**
 * Segmented protein / carbs / fat bar. Widths come from backend-provided macro grams converted to
 * display shares (4/4/9 kcal per g) purely for drawing; the numbers shown are the backend's values.
 */
export function MacroBar({ protein, carbs, fat, animate = false, height = "h-2" }: {
  protein: number;
  carbs: number;
  fat: number;
  animate?: boolean;
  height?: string;
}) {
  const p = protein * 4;
  const c = carbs * 4;
  const f = fat * 9;
  const total = p + c + f;
  if (total <= 0) return <div className={`${height} w-full rounded-full bg-line`} />;
  return (
    <div className={`${animate ? "receipt-bar " : ""}flex ${height} w-full gap-0.5 overflow-hidden rounded-full`} aria-hidden>
      <span className="bg-protein" style={{ width: `${(p / total) * 100}%` }} />
      <span className="bg-carbs" style={{ width: `${(c / total) * 100}%` }} />
      <span className="bg-fat" style={{ width: `${(f / total) * 100}%` }} />
    </div>
  );
}

export function MacroLegend({ protein, carbs, fat }: { protein: number; carbs: number; fat: number }) {
  return (
    <dl className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
      <Item color="bg-protein" label="Protein" value={protein} />
      <Item color="bg-carbs" label="Carbs" value={carbs} />
      <Item color="bg-fat" label="Fat" value={fat} />
    </dl>
  );
}

function Item({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${color}`} aria-hidden />
      <dt className="text-ink-soft">{label}</dt>
      <dd className="tabular font-medium text-ink">{num(value, 1)} g</dd>
    </div>
  );
}

export function TargetMeter({ label, consumed, target, unit, color = "bg-ink" }: {
  label: string;
  consumed: number | null;
  target: number | null | undefined;
  unit: string;
  color?: string;
}) {
  const c = consumed ?? 0;
  const pct = target ? Math.min((c / target) * 100, 100) : 0;
  const over = target ? c > target : false;
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm text-ink-soft">{label}</span>
        <span className="tabular text-sm">
          <span className="font-display text-lg font-semibold text-ink">{num(c, unit === "g" ? 1 : 0)}</span>
          {target ? <span className="text-ink-faint"> / {num(target)} {unit}</span> : <span className="text-ink-faint"> {unit}</span>}
        </span>
      </div>
      <div
        className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-line"
        role="progressbar"
        aria-label={label}
        aria-valuenow={Math.round(c)}
        aria-valuemax={target ?? undefined}
      >
        <div className={`h-full rounded-full ${over ? "bg-danger" : color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
