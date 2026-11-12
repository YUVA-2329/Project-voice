"use client";

import { X } from "lucide-react";
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, type KeyboardEvent, type ReactNode } from "react";
import { Kbd } from "@/components/ui/Kbd";
import { MAX_TEXT_CHARS } from "@/lib/api/types";
import { cn } from "@/lib/cn";

export interface TextComposerProps {
  value: string;
  onChange: (value: string) => void;
  /** Called on ⌘/Ctrl+Enter. */
  onRun?: () => void;
  disabled?: boolean;
  placeholder?: string;
  maxChars?: number;
  /** Extra chips (e.g. the language chip in Advanced mode) rendered in the footer. */
  chips?: ReactNode;
  id?: string;
  className?: string;
}

export const TextComposer = forwardRef<HTMLTextAreaElement, TextComposerProps>(function TextComposer(
  {
    value,
    onChange,
    onRun,
    disabled,
    placeholder = "What would you like your voice to say?",
    maxChars = MAX_TEXT_CHARS,
    chips,
    id = "composer-text",
    className,
  },
  ref,
) {
  const innerRef = useRef<HTMLTextAreaElement>(null);
  useImperativeHandle(ref, () => innerRef.current as HTMLTextAreaElement);

  const resize = useCallback(() => {
    const el = innerRef.current;
    if (!el) return;
    el.style.height = "0px";
    const next = Math.max(144, Math.min(el.scrollHeight, 480));
    el.style.height = `${next}px`;
  }, []);

  useEffect(() => {
    resize();
  }, [value, resize]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      onRun?.();
    }
  };

  const count = value.length;
  const over = count > maxChars;
  const isMac = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform);

  return (
    <div className={cn("flex flex-col", className)}>
      <label htmlFor={id} className="sr-only">
        Text to speak
      </label>
      <div
        className={cn(
          "group relative rounded-md border border-border bg-surface transition-colors duration-fast ease-pv",
          "focus-within:border-border-strong hover:border-border-strong",
          over && "border-danger focus-within:border-danger",
        )}
      >
        <textarea
          ref={innerRef}
          id={id}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={disabled}
          placeholder={placeholder}
          spellCheck
          aria-describedby={`${id}-count`}
          aria-invalid={over || undefined}
          className={cn(
            "block w-full resize-none bg-transparent px-4 pb-10 pt-4 text-[17px] leading-[1.55] text-ink outline-none",
            "placeholder:text-ink-3 disabled:opacity-60",
          )}
          style={{ minHeight: 144 }}
        />
        <div className="pointer-events-none absolute inset-x-0 bottom-0 flex h-10 items-center justify-between gap-3 px-3">
          <div className="pointer-events-auto flex items-center gap-2">{chips}</div>
          <div className="pointer-events-auto flex items-center gap-2">
            {onRun && (
              <span className="hidden items-center gap-1 text-micro text-ink-3 sm:inline-flex" aria-hidden>
                <Kbd>{isMac ? "⌘" : "Ctrl"}</Kbd>
                <Kbd>↵</Kbd>
              </span>
            )}
            <span
              id={`${id}-count`}
              className={cn("font-mono text-micro tabular", over ? "text-danger" : "text-ink-3")}
              aria-live="polite"
              aria-atomic="true"
            >
              <span className="sr-only">Characters: </span>
              {count.toLocaleString()} / {maxChars.toLocaleString()}
            </span>
            {value.length > 0 && !disabled && (
              <button
                type="button"
                aria-label="Clear text"
                onClick={() => {
                  onChange("");
                  innerRef.current?.focus();
                }}
                className="inline-flex size-8 items-center justify-center rounded-sm text-ink-3 transition-colors duration-fast ease-pv hover:bg-surface-2 hover:text-ink"
              >
                <X className="size-4" aria-hidden />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});
