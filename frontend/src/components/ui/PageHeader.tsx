import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

/** Display h1 (Instrument Serif) with an optional one-line description and right-aligned actions. */
export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  eyebrow?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-4 pb-8", className)}>
      <div className="flex flex-col gap-2">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1 className="display text-h2 text-ink sm:text-h1">{title}</h1>
        {description && <p className="text-body text-ink-2">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
