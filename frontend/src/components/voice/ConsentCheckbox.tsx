"use client";

import * as Checkbox from "@radix-ui/react-checkbox";
import { Check } from "lucide-react";
import { useId } from "react";
import { CONSENT_TEXT } from "@/lib/api/types";
import { cn } from "@/lib/cn";

export function ConsentCheckbox({
  checked,
  onCheckedChange,
  error,
  className,
}: {
  checked: boolean;
  onCheckedChange: (v: boolean) => void;
  error?: string | null;
  className?: string;
}) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-start gap-3">
        <Checkbox.Root
          id={id}
          checked={checked}
          onCheckedChange={(v) => onCheckedChange(v === true)}
          required
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? errorId : undefined}
          className={cn(
            "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-xs border bg-surface transition-colors duration-fast ease-pv",
            checked ? "border-ink bg-ink text-ink-inverse" : "border-border-strong hover:border-ink",
            error && !checked && "border-danger",
          )}
        >
          <Checkbox.Indicator>
            <Check className="size-3.5" aria-hidden strokeWidth={3} />
          </Checkbox.Indicator>
        </Checkbox.Root>
        <label htmlFor={id} className="cursor-pointer text-body leading-snug text-ink">
          {CONSENT_TEXT}
        </label>
      </div>
      {error && (
        <p id={errorId} role="alert" className="pl-8 text-small text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
