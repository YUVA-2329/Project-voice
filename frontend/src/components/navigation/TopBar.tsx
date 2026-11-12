"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Wordmark } from "@/components/brand/Wordmark";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/cn";
import { AccountMenu } from "./AccountMenu";
import type { User } from "@/lib/api/types";

export interface NavItem {
  label: string;
  href: string;
  /** Additional pathnames that should highlight this item. */
  match?: (pathname: string) => boolean;
}

export function useNavItems(): NavItem[] {
  const mode = useAppStore((s) => s.mode);
  const createHref = mode === "advanced" ? "/app/advanced" : "/app";
  return [
    { label: "Create", href: createHref, match: (p) => p === "/app" || p === "/app/advanced" },
    { label: "My Voices", href: "/app/voices", match: (p) => p.startsWith("/app/voices") },
    { label: "History", href: "/app/history", match: (p) => p.startsWith("/app/history") },
    { label: "Settings", href: "/app/settings", match: (p) => p.startsWith("/app/settings") },
  ];
}

export function TopBar({ user }: { user: User }) {
  const pathname = usePathname();
  const items = useNavItems();
  return (
    <header className="sticky top-0 z-30 h-14 border-b border-border bg-bg/95 backdrop-blur-[2px]">
      <div className="mx-auto flex h-full max-w-[1200px] items-center justify-between gap-4 px-4 sm:px-6 lg:px-10">
        <Wordmark href="/app" />
        <nav aria-label="Primary" className="hidden h-full items-center gap-6 nav:flex">
          {items.map((item) => {
            const active = item.match ? item.match(pathname) : pathname === item.href;
            return (
              <Link
                key={item.label}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "relative flex h-14 items-center text-small font-medium transition-colors duration-fast ease-pv",
                  active ? "text-ink" : "text-ink-3 hover:text-ink",
                )}
              >
                {item.label}
                {active && <span aria-hidden className="absolute inset-x-0 bottom-0 h-px bg-ink" />}
              </Link>
            );
          })}
        </nav>
        <AccountMenu user={user} />
      </div>
    </header>
  );
}
