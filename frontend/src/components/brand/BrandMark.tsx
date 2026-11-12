import { cn } from "@/lib/cn";

/**
 * Five vertical bars of a voice signature (heights 10/22/32/22/10 on a 32px grid, 3px wide,
 * 3px gaps, rounded ends). Centre bar in accent, others in ink. `levels` (0–1 per bar) drives
 * the live meter while recording / speaking. Decorative: aria-hidden unless given a label.
 */
export const BAR_HEIGHTS = [10, 22, 32, 22, 10] as const;
const BAR_W = 3;
const GAP = 3;
const GRID = 32;
const TOTAL_W = BAR_HEIGHTS.length * BAR_W + (BAR_HEIGHTS.length - 1) * GAP; // 27

export interface BrandMarkProps {
  size?: number;
  levels?: number[] | null;
  animated?: boolean;
  className?: string;
  label?: string;
  /** Animation delay per bar for the intro draw-in (CSS transition handled by caller). */
  style?: React.CSSProperties;
}

export function BrandMark({ size = 32, levels, animated = false, className, label, style }: BrandMarkProps) {
  const scale = size / GRID;
  const width = TOTAL_W * scale;
  return (
    <svg
      width={width}
      height={size}
      viewBox={`0 0 ${TOTAL_W} ${GRID}`}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={cn("shrink-0 overflow-visible", className)}
      style={style}
    >
      {BAR_HEIGHTS.map((h, i) => {
        const level = levels?.[i];
        const live = animated && typeof level === "number";
        // Live mode: bar height follows the level, with the static silhouette as the floor at 35%.
        const height = live ? Math.max(4, h * (0.35 + 0.65 * Math.max(0, Math.min(1, level)))) : h;
        const x = i * (BAR_W + GAP);
        const y = (GRID - height) / 2;
        const isCentre = i === 2;
        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={BAR_W}
            height={height}
            rx={BAR_W / 2}
            className={cn(
              isCentre ? "fill-accent" : "fill-ink",
              live && "transition-[y,height] duration-[80ms] ease-linear",
            )}
            data-bar={i}
          />
        );
      })}
    </svg>
  );
}
