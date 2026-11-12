import { cn } from "@/lib/cn";

/** 1px progress bar. `fraction` null → indeterminate sweep (status is still real, only the width is unknown). */
export function ProgressBar({ fraction, className, label }: { fraction: number | null; className?: string; label?: string }) {
  const pct = fraction == null ? null : Math.round(Math.max(0, Math.min(1, fraction)) * 100);
  return (
    <div
      className={cn("pv-progress w-full", className)}
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct ?? undefined}
      data-indeterminate={pct == null ? "true" : undefined}
    >
      <span style={pct == null ? undefined : { width: `${pct}%` }} />
    </div>
  );
}
