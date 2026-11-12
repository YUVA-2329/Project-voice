"use client";

import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { ChevronDown, Code2, LogOut, MessageSquare, Settings, SlidersHorizontal } from "lucide-react";
import { useRouter } from "next/navigation";
import { useLogout, useUpdateMe } from "@/lib/api/hooks";
import type { Mode, User } from "@/lib/api/types";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/cn";

const itemClass =
  "flex h-9 cursor-pointer select-none items-center gap-2.5 rounded-xs px-2.5 text-small text-ink outline-none " +
  "data-[highlighted]:bg-surface-2 data-[disabled]:opacity-50";

export function AccountMenu({ user }: { user: User }) {
  const router = useRouter();
  const logout = useLogout();
  const updateMe = useUpdateMe();
  const mode = useAppStore((s) => s.mode);
  const setMode = useAppStore((s) => s.setMode);

  const initials = (user.display_name || user.email).trim().charAt(0).toUpperCase();

  const changeMode = (next: Mode) => {
    if (next === mode) return;
    setMode(next);
    updateMe.mutate({ preferences: { mode: next } });
    router.push(next === "advanced" ? "/app/advanced" : "/app");
  };

  const signOut = () => {
    logout.mutate(undefined, {
      onSettled: () => {
        useAppStore.getState().setSelectedVoiceId(null);
        window.location.assign("/");
      },
    });
  };

  return (
    <Dropdown.Root modal={false}>
      <Dropdown.Trigger
        aria-label="Account menu"
        className={cn(
          "inline-flex h-10 items-center gap-2 rounded-sm pl-1 pr-2 text-small text-ink-2 transition-colors duration-fast ease-pv",
          "hover:bg-surface-2 hover:text-ink data-[state=open]:bg-surface-2 data-[state=open]:text-ink",
        )}
      >
        <span
          aria-hidden
          className="flex size-7 items-center justify-center rounded-full border border-border bg-surface text-micro font-medium text-ink"
        >
          {initials}
        </span>
        <span className="hidden max-w-32 truncate sm:inline">{user.display_name}</span>
        <ChevronDown className="size-3.5 text-ink-3" aria-hidden />
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content
          align="end"
          sideOffset={6}
          className="z-50 w-60 rounded-md border border-border bg-surface p-1 shadow-md outline-none data-[state=open]:animate-in data-[state=closed]:animate-out"
        >
          <div className="px-2.5 py-2">
            <p className="truncate text-small font-medium text-ink">{user.display_name}</p>
            <p className="truncate font-mono text-micro text-ink-3">{user.email}</p>
          </div>
          <Dropdown.Separator className="my-1 h-px bg-border" />
          <Dropdown.Label className="eyebrow px-2.5 pb-1 pt-2">Mode</Dropdown.Label>
          <Dropdown.RadioGroup value={mode} onValueChange={(v) => changeMode(v as Mode)}>
            <Dropdown.RadioItem value="simple" className={itemClass}>
              <Dot active={mode === "simple"} />
              Simple
            </Dropdown.RadioItem>
            <Dropdown.RadioItem value="advanced" className={itemClass}>
              <Dot active={mode === "advanced"} />
              Advanced
            </Dropdown.RadioItem>
          </Dropdown.RadioGroup>
          <Dropdown.Separator className="my-1 h-px bg-border" />
          <Dropdown.Item className={itemClass} onSelect={() => router.push("/app/advanced")}>
            <SlidersHorizontal className="size-4 text-ink-3" aria-hidden />
            Advanced controls
          </Dropdown.Item>
          <Dropdown.Item className={itemClass} onSelect={() => router.push("/app/conversation")}>
            <MessageSquare className="size-4 text-ink-3" aria-hidden />
            Conversation
          </Dropdown.Item>
          <Dropdown.Item className={itemClass} onSelect={() => router.push("/app/developer")}>
            <Code2 className="size-4 text-ink-3" aria-hidden />
            Developer
          </Dropdown.Item>
          <Dropdown.Item className={itemClass} onSelect={() => router.push("/app/settings")}>
            <Settings className="size-4 text-ink-3" aria-hidden />
            Settings
          </Dropdown.Item>
          <Dropdown.Separator className="my-1 h-px bg-border" />
          <Dropdown.Item className={itemClass} onSelect={signOut} disabled={logout.isPending}>
            <LogOut className="size-4 text-ink-3" aria-hidden />
            Sign out
          </Dropdown.Item>
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

function Dot({ active }: { active: boolean }) {
  return (
    <span
      aria-hidden
      className={cn("size-1.5 rounded-full", active ? "bg-accent" : "border border-border-strong")}
    />
  );
}
