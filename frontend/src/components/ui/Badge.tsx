import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "accent" | "processing";

const tones: Record<BadgeTone, string> = {
  neutral: "text-ink-2 border-border",
  success: "text-success border-border",
  warning: "text-warning border-border",
  danger: "text-danger border-border",
  accent: "text-accent border-border",
  processing: "text-ink-2 border-border",
};

const dots: Record<BadgeTone, string> = {
  neutral: "bg-ink-3",
  success: "bg-success",
  warning: "bg-warning",
  danger: "bg-danger",
  accent: "bg-accent",
  processing: "bg-ink-3 animate-pulse",
};

export function Badge({
  tone = "neutral",
  children,
  dot = true,
  className,
  mono,
}: {
  tone?: BadgeTone;
  children: ReactNode;
  dot?: boolean;
  className?: string;
  mono?: boolean;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-xs border px-2 text-micro font-medium tracking-[0.01em]",
        mono && "font-mono",
        tones[tone],
        className,
      )}
    >
      {dot && <span className={cn("size-1.5 rounded-full", dots[tone])} aria-hidden />}
      {children}
    </span>
  );
}
