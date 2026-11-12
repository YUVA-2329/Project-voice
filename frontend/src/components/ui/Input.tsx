"use client";

import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  mono?: boolean;
}

export const inputClass =
  "h-10 w-full rounded-sm border border-border bg-surface px-3 text-body text-ink placeholder:text-ink-3 " +
  "transition-colors duration-fast ease-pv hover:border-border-strong focus:border-border-strong " +
  "disabled:opacity-50 aria-[invalid=true]:border-danger";

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, hint, error, mono, className, id: idProp, ...rest },
  ref,
) {
  const autoId = useId();
  const id = idProp ?? autoId;
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={id} className="text-small font-medium text-ink-2">
          {label}
        </label>
      )}
      <input
        ref={ref}
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={cn(hint && hintId, error && errorId) || undefined}
        className={cn(inputClass, mono && "font-mono text-small", className)}
        {...rest}
      />
      {error ? (
        <p id={errorId} className="text-small text-danger" role="alert">
          {error}
        </p>
      ) : hint ? (
        <p id={hintId} className="text-small text-ink-3">
          {hint}
        </p>
      ) : null}
    </div>
  );
});
