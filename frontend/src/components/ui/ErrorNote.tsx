import { errorCode, errorMessage } from "@/lib/api/client";
import { cn } from "@/lib/cn";

/** Human message first, error code in small mono underneath. */
export function ErrorNote({
  error,
  message,
  code,
  className,
}: {
  error?: unknown;
  message?: string;
  code?: string | null;
  className?: string;
}) {
  const msg = message ?? (error ? errorMessage(error) : "");
  const c = code ?? (error ? errorCode(error) : null);
  if (!msg) return null;
  return (
    <div role="alert" className={cn("flex flex-col gap-1 text-small text-danger", className)}>
      <p>{msg}</p>
      {c && <p className="font-mono text-micro text-ink-3">{c}</p>}
    </div>
  );
}
