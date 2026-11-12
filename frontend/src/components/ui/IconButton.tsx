"use client";

import { forwardRef, type AnchorHTMLAttributes, type ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

type CommonProps = {
  label: string;
  size?: "sm" | "md";
  tone?: "default" | "danger";
};

export type IconButtonProps = CommonProps &
  ButtonHTMLAttributes<HTMLButtonElement> & {
    /** Render as a link (e.g. a download). */
    asChildAnchor?: boolean;
    href?: string;
    download?: string | boolean;
    target?: AnchorHTMLAttributes<HTMLAnchorElement>["target"];
    rel?: string;
  };

function classes(size: "sm" | "md", tone: "default" | "danger", className?: string) {
  return cn(
    "inline-flex items-center justify-center rounded-sm transition-colors duration-fast ease-pv",
    "disabled:opacity-50 disabled:pointer-events-none",
    size === "md" ? "size-10" : "size-8",
    tone === "danger" ? "text-ink-2 hover:text-danger hover:bg-surface-2" : "text-ink-2 hover:text-ink hover:bg-surface-2",
    className,
  );
}

/** 40px square (minimum touch target) icon-only button with an accessible name. */
export const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(function IconButton(
  { label, size = "md", tone = "default", className, type = "button", children, asChildAnchor, href, download, target, rel, ...rest },
  ref,
) {
  if (asChildAnchor && href) {
    return (
      <a
        href={href}
        download={download}
        target={target}
        rel={rel}
        aria-label={label}
        title={label}
        className={classes(size, tone, className)}
      >
        {children}
      </a>
    );
  }
  return (
    <button ref={ref} type={type} aria-label={label} title={label} className={classes(size, tone, className)} {...rest}>
      {children}
    </button>
  );
});
