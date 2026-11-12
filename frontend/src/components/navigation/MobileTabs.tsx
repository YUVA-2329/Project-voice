"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Clock, Mic, PenLine, Settings } from "lucide-react";
import { cn } from "@/lib/cn";
import { useNavItems } from "./TopBar";

const ICONS = [PenLine, Mic, Clock, Settings];

/** Bottom tab bar shown under 720px (DESIGN.md §3). */
export function MobileTabs() {
  const pathname = usePathname();
  const items = useNavItems();
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-bg pb-[env(safe-area-inset-bottom)] nav:hidden"
    >
      <ul className="grid h-14 grid-cols-4">
        {items.map((item, i) => {
          const Icon = ICONS[i] ?? PenLine;
          const active = item.match ? item.match(pathname) : pathname === item.href;
          return (
            <li key={item.label} className="flex">
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex flex-1 flex-col items-center justify-center gap-0.5 text-[11px] font-medium transition-colors duration-fast ease-pv",
                  active ? "text-ink" : "text-ink-3",
                )}
              >
                <Icon className="size-[18px]" aria-hidden strokeWidth={active ? 2 : 1.75} />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
