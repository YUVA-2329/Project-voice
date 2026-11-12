"use client";

import * as RadixSwitch from "@radix-ui/react-switch";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export function Switch({
  checked,
  onCheckedChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <div className="flex items-center justify-between gap-4 py-2">
      <div className="flex flex-col">
        <label htmlFor={id} className="text-body text-ink">
          {label}
        </label>
        {description && <span className="text-small text-ink-3">{description}</span>}
      </div>
      <RadixSwitch.Root
        id={id}
        checked={checked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        className={cn(
          "relative h-6 w-10 shrink-0 rounded-full border border-border bg-surface-2 transition-colors duration-base ease-pv",
          "data-[state=checked]:bg-ink data-[state=checked]:border-ink disabled:opacity-50",
        )}
      >
        <RadixSwitch.Thumb className="block size-4 translate-x-0.5 rounded-full bg-ink shadow-sm transition-transform duration-base ease-pv data-[state=checked]:translate-x-[18px] data-[state=checked]:bg-ink-inverse" />
      </RadixSwitch.Root>
    </div>
  );
}
