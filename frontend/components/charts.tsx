"use client";

/** Recharts views. They only draw backend-provided series; no totals are computed here. */
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { num, shortDate } from "@/lib/format";

const INK = "#15213B";
const GRID = "#E3E7ED";
const AXIS = { fontSize: 12, fill: "#8792A8" };
const COLORS = { protein: "#2F5BEA", carbs: "#D99A1E", fat: "#2E9C86" };

const tooltipStyle = {
  contentStyle: { borderRadius: 10, border: "1px solid #D6DCE4", fontSize: 13, boxShadow: "none" },
  labelStyle: { color: INK, fontWeight: 600 },
};

export function MacroDonut({ protein, carbs, fat }: { protein: number; carbs: number; fat: number }) {
  // Input is the backend's macro_distribution (percent of macro calories).
  const data = [
    { name: "Protein", value: protein, color: COLORS.protein },
    { name: "Carbs", value: carbs, color: COLORS.carbs },
    { name: "Fat", value: fat, color: COLORS.fat },
  ];
  const empty = protein + carbs + fat === 0;
  return (
    <ResponsiveContainer width="100%" height={180}>
      <PieChart>
        <Pie
          data={empty ? [{ name: "None", value: 1, color: GRID }] : data}
          dataKey="value"
          innerRadius={55}
          outerRadius={80}
          paddingAngle={empty ? 0 : 2}
          stroke="none"
          isAnimationActive={false}
        >
          {(empty ? [{ color: GRID }] : data).map((d, i) => <Cell key={i} fill={d.color} />)}
        </Pie>
        {!empty && <Tooltip {...tooltipStyle} formatter={(v: unknown) => `${v}%`} />}
      </PieChart>
    </ResponsiveContainer>
  );
}

export function CaloriesBars({ points, target, dataKey = "calories", color = INK, unit = "kcal" }: {
  points: { period_start: string; [k: string]: number | string }[];
  target?: number | null;
  dataKey?: string;
  color?: string;
  unit?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={points} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey="period_start" tickFormatter={shortDate} tick={AXIS} tickLine={false} axisLine={false} minTickGap={12} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={52} />
        <Tooltip {...tooltipStyle} labelFormatter={(l: string) => shortDate(l)} formatter={(v: unknown) => [`${num(Number(v), 1)} ${unit}`, ""]} cursor={{ fill: "#15213B0A" }} />
        {target ? <ReferenceLine y={target} stroke="#C2412D" strokeDasharray="4 4" label={{ value: "target", position: "insideTopRight", fill: "#C2412D", fontSize: 11 }} /> : null}
        <Bar dataKey={dataKey} fill={color} radius={[4, 4, 0, 0]} maxBarSize={36} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TrendLine({ points, xKey, yKey, color = INK, unit, target, height = 220 }: {
  points: Record<string, number | string | null>[];
  xKey: string;
  yKey: string;
  color?: string;
  unit: string;
  target?: number | null;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey={xKey} tickFormatter={shortDate} tick={AXIS} tickLine={false} axisLine={false} minTickGap={16} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} width={52} domain={["auto", "auto"]} />
        <Tooltip {...tooltipStyle} labelFormatter={(l: string) => shortDate(l)} formatter={(v: unknown) => [`${num(Number(v), 1)} ${unit}`, ""]} />
        {target ? <ReferenceLine y={target} stroke="#C2412D" strokeDasharray="4 4" /> : null}
        <Line type="monotone" dataKey={yKey} stroke={color} strokeWidth={2.5} dot={{ r: 3, fill: color }} activeDot={{ r: 5 }} connectNulls />
      </LineChart>
    </ResponsiveContainer>
  );
}
