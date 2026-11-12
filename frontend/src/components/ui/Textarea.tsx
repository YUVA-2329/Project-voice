"use client";

import { forwardRef, type TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(
  function Textarea({ className, ...rest }, ref) {
    return (
      <textarea
        ref={ref}
        className={cn(
          "w-full rounded-sm border border-border bg-surface px-3 py-2 text-body text-ink placeholder:text-ink-3",
          "transition-colors duration-fast ease-pv hover:border-border-strong focus:border-border-strong",
          "disabled:opacity-50 resize-none",
          className,
        )}
        {...rest}
      />
    );
  },
);
