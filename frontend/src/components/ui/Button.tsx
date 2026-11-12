"use client";

import Link from "next/link";
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

export type ButtonVariant = "primary" | "accent" | "secondary" | "ghost" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  leading?: ReactNode;
  trailing?: ReactNode;
  block?: boolean;
  /** Render as a Next.js link with button styling. */
  asChildLink?: boolean;
  href?: string;
}

const base =
  "inline-flex items-center justify-center gap-2 rounded-sm font-medium text-button whitespace-nowrap select-none " +
  "transition-[background-color,color,border-color,box-shadow,transform] duration-fast ease-pv " +
  "disabled:opacity-50 disabled:pointer-events-none";

const variants: Record<ButtonVariant, string> = {
  primary: "bg-ink text-ink-inverse hover:bg-ink-2 active:translate-y-px",
  accent: "bg-accent text-on-accent hover:bg-accent-hover active:translate-y-px active:shadow-sm",
  secondary: "bg-surface text-ink border border-border hover:border-border-strong hover:bg-surface-2 active:translate-y-px",
  ghost: "bg-transparent text-ink-2 hover:text-ink hover:bg-surface-2",
  danger: "bg-transparent text-danger border border-border hover:border-danger hover:bg-surface-2",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-8 px-3 text-small",
  md: "h-10 px-4",
  lg: "h-12 px-6",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  {
    variant = "secondary",
    size = "md",
    loading = false,
    leading,
    trailing,
    block,
    className,
    children,
    disabled,
    type = "button",
    asChildLink,
    href,
    ...rest
  },
  ref,
) {
  const cls = cn(base, variants[variant], sizes[size], block && "w-full", className);
  if (asChildLink && href) {
    return (
      <Link href={href} className={cls}>
        {leading}
        {children}
        {trailing}
      </Link>
    );
  }
  return (
    <button ref={ref} type={type} className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : leading}
      {children}
      {!loading && trailing}
    </button>
  );
});
