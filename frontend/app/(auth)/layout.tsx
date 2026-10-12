export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh md:grid-cols-[1fr_1.1fr]">
      <div className="hidden flex-col justify-between bg-ink p-10 text-white md:flex">
        <p className="font-display text-2xl font-bold">fitpro</p>
        <div className="max-w-sm space-y-4">
          <p className="font-display text-[2rem] font-semibold leading-tight">
            “3 eggs, 200g rice and 150g chicken for lunch.”
          </p>
          <div className="rounded-xl bg-white/10 p-4 text-sm">
            <p>Logged 3 × egg, 200 g rice and 150 g chicken — 724 kcal and 70.8 g protein.</p>
            <div className="mt-3 flex h-2 gap-0.5 overflow-hidden rounded-full" aria-hidden>
              <span className="bg-protein" style={{ width: "39%" }} />
              <span className="bg-carbs" style={{ width: "33%" }} />
              <span className="bg-fat" style={{ width: "28%" }} />
            </div>
          </div>
        </div>
        <p className="text-sm text-white/60">Type what you ate or lifted. The numbers are worked out for you.</p>
      </div>
      <div className="flex items-center justify-center px-4 py-12">
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
