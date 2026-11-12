"use client";

import * as RadixSlider from "@radix-ui/react-slider";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Slider({
  value,
  onValueChange,
  min,
  max,
  step,
  label,
  format = (v) => String(v),
  className,
  disabled,
}: {
  value: number;
  onValueChange: (v: number) => void;
  min: number;
  max: number;
  step: number;
  label: ReactNode;
  format?: (v: number) => string;
  className?: string;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center justify-between">
        <label id={id} className="text-small font-medium text-ink-2">
          {label}
        </label>
        <span className="font-mono text-small tabular text-ink-2">{format(value)}</span>
      </div>
      <RadixSlider.Root
        aria-labelledby={id}
        value={[value]}
        onValueChange={(v) => onValueChange(v[0] ?? value)}
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        className="relative flex h-10 w-full touch-none select-none items-center"
      >
        <RadixSlider.Track className="relative h-px w-full grow bg-border-strong">
          <RadixSlider.Range className="absolute h-full bg-ink" />
        </RadixSlider.Track>
        <RadixSlider.Thumb
          aria-label={typeof label === "string" ? label : undefined}
          className="block size-4 rounded-full border border-border-strong bg-surface shadow-sm transition-colors hover:border-ink"
        />
      </RadixSlider.Root>
    </div>
  );
}
