"use client";

import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Wordmark } from "@/components/brand/Wordmark";
import { Skeleton } from "@/components/ui/Skeleton";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { useMe } from "@/lib/api/hooks";
import { isApiError } from "@/lib/api/client";
import { applyTheme } from "@/lib/theme";
import { useAppStore } from "@/lib/store";
import { MobileTabs } from "./MobileTabs";
import { TopBar } from "./TopBar";

/**
 * Guards every `/app/**` route behind `GET /users/me`, applies the user's theme and mode
 * preferences, and lays out the top bar / bottom tabs.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const me = useMe();
  const router = useRouter();
  const pathname = usePathname();
  const setMode = useAppStore((s) => s.setMode);

  useEffect(() => {
    if (!me.data) return;
    applyTheme(me.data.preferences.theme);
    setMode(me.data.preferences.mode);
  }, [me.data, setMode]);

  useEffect(() => {
    if (me.isError && isApiError(me.error) && me.error.status === 401) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [me.isError, me.error, pathname, router]);

  if (me.isPending) {
    return (
      <div className="min-h-dvh bg-bg">
        <header className="h-14 border-b border-border">
          <div className="mx-auto flex h-full max-w-[1200px] items-center justify-between px-4 sm:px-6 lg:px-10">
            <Wordmark href={null} />
            <Skeleton className="h-7 w-7 rounded-full" />
          </div>
        </header>
        <main className="mx-auto max-w-[720px] px-4 py-12 sm:px-6 lg:px-10" aria-busy="true" aria-live="polite">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-4 h-10 w-64" />
          <Skeleton className="mt-8 h-32 w-full" />
          <span className="sr-only">Loading your account</span>
        </main>
      </div>
    );
  }

  if (me.isError) {
    const unauthenticated = isApiError(me.error) && me.error.status === 401;
    return (
      <div className="flex min-h-dvh flex-col items-center justify-center gap-4 px-4 text-center">
        <Wordmark href="/" />
        {unauthenticated ? (
          <p className="text-body text-ink-2">Redirecting you to sign in…</p>
        ) : (
          <>
            <p className="text-body text-ink-2">We could not reach the server.</p>
            <ErrorNote error={me.error} className="items-center" />
            <Button onClick={() => me.refetch()}>Try again</Button>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col bg-bg">
      <TopBar user={me.data} />
      <main className="flex-1 pb-20 nav:pb-0">{children}</main>
      <MobileTabs />
    </div>
  );
}
