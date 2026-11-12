import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-start gap-4 py-12", className)}>
      <h2 className="display text-h2 text-ink sm:text-h1">{title}</h2>
      {description && <p className="max-w-md text-body text-ink-2">{description}</p>}
      {action && <div className="pt-2">{action}</div>}
    </div>
  );
}
