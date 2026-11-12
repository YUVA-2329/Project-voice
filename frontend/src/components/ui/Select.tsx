"use client";

import * as RadixSelect from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { useId, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface SelectOption<T extends string> {
  value: T;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}

export function Select<T extends string>({
  value,
  onValueChange,
  options,
  label,
  placeholder = "Select",
  disabled,
  className,
  size = "md",
  ariaLabel,
}: {
  value: T | undefined;
  onValueChange: (v: T) => void;
  options: SelectOption<T>[];
  label?: ReactNode;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  size?: "sm" | "md";
  ariaLabel?: string;
}) {
  const id = useId();
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      {label && (
        <label htmlFor={id} className="text-small font-medium text-ink-2">
          {label}
        </label>
      )}
      <RadixSelect.Root value={value} onValueChange={(v) => onValueChange(v as T)} disabled={disabled}>
        <RadixSelect.Trigger
          id={id}
          aria-label={ariaLabel}
          className={cn(
            "inline-flex w-full items-center justify-between gap-2 rounded-sm border border-border bg-surface px-3 text-left text-body text-ink",
            "transition-colors duration-fast ease-pv hover:border-border-strong data-[placeholder]:text-ink-3 disabled:opacity-50",
            size === "md" ? "h-10" : "h-8 text-small",
          )}
        >
          <RadixSelect.Value placeholder={placeholder} />
          <RadixSelect.Icon>
            <ChevronDown className="size-4 text-ink-3" aria-hidden />
          </RadixSelect.Icon>
        </RadixSelect.Trigger>
        <RadixSelect.Portal>
          <RadixSelect.Content
            position="popper"
            sideOffset={6}
            className="z-50 max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-border bg-surface p-1 shadow-md"
          >
            <RadixSelect.Viewport>
              {options.map((o) => (
                <RadixSelect.Item
                  key={o.value}
                  value={o.value}
                  disabled={o.disabled}
                  className={cn(
                    "relative flex cursor-pointer select-none flex-col rounded-xs py-2 pl-8 pr-3 text-body text-ink outline-none",
                    "data-[highlighted]:bg-surface-2 data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50",
                  )}
                >
                  <RadixSelect.ItemIndicator className="absolute left-2.5 top-2.5">
                    <Check className="size-4 text-accent" aria-hidden />
                  </RadixSelect.ItemIndicator>
                  <RadixSelect.ItemText>{o.label}</RadixSelect.ItemText>
                  {o.description && <span className="text-micro text-ink-3">{o.description}</span>}
                </RadixSelect.Item>
              ))}
            </RadixSelect.Viewport>
          </RadixSelect.Content>
        </RadixSelect.Portal>
      </RadixSelect.Root>
    </div>
  );
}
