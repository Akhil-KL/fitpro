"use client";

/**
 * Small primitives in the shadcn/ui style (owned source, Tailwind classes, no runtime theme lib).
 */
import * as React from "react";
import { cn } from "@/lib/format";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", size = "md", ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-8 px-3 text-sm" : "h-10 px-4 text-[15px]",
        variant === "primary" && "bg-ink text-white hover:bg-ink/90",
        variant === "secondary" && "border border-line bg-surface text-ink hover:bg-paper",
        variant === "ghost" && "text-ink-soft hover:bg-ink/5 hover:text-ink",
        variant === "danger" && "border border-danger/30 bg-surface text-danger hover:bg-danger/5",
        className,
      )}
      {...props}
    />
  );
});

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...props },
  ref,
) {
  return (
    <input
      ref={ref}
      className={cn(
        "h-10 w-full rounded-lg border border-line bg-surface px-3 text-[15px] text-ink placeholder:text-ink-faint focus:border-protein focus:outline-none",
        className,
      )}
      {...props}
    />
  );
});

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn("h-10 w-full rounded-lg border border-line bg-surface px-3 text-[15px] text-ink focus:border-protein focus:outline-none", className)}
      {...props}
    />
  );
}

export function Field({ label, hint, htmlFor, children }: { label: string; hint?: string; htmlFor: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-ink">
        {label}
      </label>
      {children}
      {hint ? <p className="text-xs text-ink-faint">{hint}</p> : null}
    </div>
  );
}

export function Panel({ className, children, ...props }: React.HTMLAttributes<HTMLElement>) {
  return (
    <section className={cn("rounded-xl border border-line bg-surface", className)} {...props}>
      {children}
    </section>
  );
}

export function PanelTitle({ title, aside }: { title: string; aside?: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 px-5 pt-4">
      <h2 className="text-base font-semibold">{title}</h2>
      {aside ? <div className="text-sm text-ink-soft">{aside}</div> : null}
    </div>
  );
}

export function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="rounded-lg border border-danger/25 bg-danger/5 px-3 py-2 text-sm text-danger">
      {message}
    </p>
  );
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="px-5 py-10 text-center text-sm text-ink-soft">{children}</div>;
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 px-5 py-8 text-sm text-ink-soft" role="status">
      <span className="h-3 w-3 animate-spin rounded-full border-2 border-ink-faint border-t-transparent" />
      {label}…
    </div>
  );
}
