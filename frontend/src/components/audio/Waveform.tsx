import { cn } from "@/lib/cn";

/**
 * Static waveform drawn from normalised peaks (0–1). Decorative — callers must provide the
 * textual equivalent (duration) next to it. `progress` (0–1) tints the played portion.
 */
export function Waveform({
  peaks,
  height = 48,
  progress,
  className,
}: {
  peaks: ArrayLike<number>;
  height?: number;
  progress?: number;
  className?: string;
}) {
  const n = peaks.length;
  if (n === 0) return null;
  const width = 1000;
  const gap = 0.35;
  const barW = (width / n) * (1 - gap);
  const step = width / n;
  const mid = height / 2;
  const splitAt = progress == null ? null : Math.round(Math.max(0, Math.min(1, progress)) * n);

  const bars = (from: number, to: number, cls: string) => {
    const parts: string[] = [];
    for (let i = from; i < to; i++) {
      const v = Math.max(0.04, Math.min(1, peaks[i] ?? 0));
      const h = Math.max(1.5, v * (height - 2));
      const x = i * step + (step - barW) / 2;
      parts.push(`M${x.toFixed(2)} ${(mid - h / 2).toFixed(2)}h${barW.toFixed(2)}v${h.toFixed(2)}h-${barW.toFixed(2)}z`);
    }
    return parts.length ? <path d={parts.join("")} className={cls} /> : null;
  };

  return (
    <svg
      aria-hidden
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={cn("block w-full", className)}
      style={{ height }}
    >
      {splitAt == null ? (
        bars(0, n, "fill-ink-2")
      ) : (
        <>
          {bars(0, splitAt, "fill-ink")}
          {bars(splitAt, n, "fill-border-strong")}
        </>
      )}
    </svg>
  );
}
