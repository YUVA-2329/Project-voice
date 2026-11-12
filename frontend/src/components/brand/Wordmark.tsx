import Link from "next/link";
import { cn } from "@/lib/cn";
import { BrandMark } from "./BrandMark";

/** The wordmark is text, not an image: Geist Sans 13px, tracking +0.12em, with the mark. */
export function Wordmark({
  href = "/",
  withMark = true,
  className,
  markSize = 18,
}: {
  href?: string | null;
  withMark?: boolean;
  className?: string;
  markSize?: number;
}) {
  const inner = (
    <>
      {withMark && <BrandMark size={markSize} />}
      <span className="text-[13px] font-medium uppercase tracking-[0.12em] text-ink">PROJECT VOICE</span>
    </>
  );
  const cls = cn("inline-flex items-center gap-2.5 whitespace-nowrap", className);
  if (!href) return <span className={cls}>{inner}</span>;
  return (
    <Link href={href} className={cls} aria-label="PROJECT VOICE home">
      {inner}
    </Link>
  );
}
