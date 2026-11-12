"use client";

import Link from "next/link";
import { Check, ChevronDown, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PopoverContent, PopoverRoot, PopoverTrigger } from "@/components/ui/Popover";
import { Skeleton } from "@/components/ui/Skeleton";
import { useVoices } from "@/lib/api/hooks";
import { LANGUAGE_NAMES, type Voice } from "@/lib/api/types";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/cn";

export function useSelectedVoice(): {
  voices: Voice[];
  readyVoices: Voice[];
  selected: Voice | null;
  isPending: boolean;
  isError: boolean;
  error: unknown;
  select: (id: string | null) => void;
} {
  const q = useVoices();
  const selectedId = useAppStore((s) => s.selectedVoiceId);
  const setSelectedVoiceId = useAppStore((s) => s.setSelectedVoiceId);
  const voices = useMemo(() => q.data?.items ?? [], [q.data]);
  const readyVoices = useMemo(() => voices.filter((v) => v.status === "ready"), [voices]);
  const selected = useMemo(() => voices.find((v) => v.id === selectedId) ?? null, [voices, selectedId]);

  // Keep the persisted selection honest: drop deleted voices, pick the newest ready one when empty.
  useEffect(() => {
    if (!q.isSuccess) return;
    if (selectedId && !voices.some((v) => v.id === selectedId)) {
      setSelectedVoiceId(null);
      return;
    }
    if (!selectedId && readyVoices.length > 0) {
      setSelectedVoiceId(readyVoices[0]?.id ?? null);
    }
  }, [q.isSuccess, voices, readyVoices, selectedId, setSelectedVoiceId]);

  return {
    voices,
    readyVoices,
    selected,
    isPending: q.isPending,
    isError: q.isError,
    error: q.error,
    select: setSelectedVoiceId,
  };
}

/** Compact popover listing ready voices; shows the selected voice name and "Change". */
export function VoiceSelector({ className }: { className?: string }) {
  const { readyVoices, voices, selected, isPending, select } = useSelectedVoice();
  const [open, setOpen] = useState(false);
  const processing = voices.filter((v) => v.status === "processing").length;

  if (isPending) {
    return (
      <div className={cn("flex h-10 items-center", className)}>
        <Skeleton className="h-5 w-40" />
      </div>
    );
  }

  if (readyVoices.length === 0) {
    return (
      <div className={cn("flex flex-wrap items-center gap-x-3 gap-y-1", className)}>
        <span className="text-h3 text-ink-3">
          {processing > 0 ? `${processing === 1 ? "A voice is" : `${processing} voices are`} still processing` : "No voice yet"}
        </span>
        <Link href="/app/voices/create" className="inline-flex h-10 items-center gap-1.5 text-button font-medium text-ink underline-offset-4 hover:underline">
          <Plus className="size-4" aria-hidden />
          Create your voice
        </Link>
      </div>
    );
  }

  return (
    <PopoverRoot open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        aria-label={selected ? `Selected voice: ${selected.name}. Change voice` : "Choose a voice"}
        className={cn(
          "group inline-flex h-10 max-w-full items-center gap-3 rounded-sm pr-2 text-left transition-colors duration-fast ease-pv hover:bg-surface-2",
          className,
        )}
      >
        <span className="flex items-center gap-2.5 truncate">
          <span aria-hidden className={cn("size-2 shrink-0 rounded-full", selected ? "bg-accent" : "border border-border-strong")} />
          <span className="truncate text-h3 text-ink">{selected?.name ?? "Choose a voice"}</span>
        </span>
        <span className="inline-flex shrink-0 items-center gap-0.5 text-small font-medium text-ink-3 group-hover:text-ink">
          Change
          <ChevronDown className="size-3.5" aria-hidden />
        </span>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-1">
        <ul role="listbox" aria-label="Ready voices" className="max-h-72 overflow-y-auto">
          {readyVoices.map((v) => {
            const active = v.id === selected?.id;
            const lang = v.language ? LANGUAGE_NAMES[v.language]?.name : null;
            return (
              <li key={v.id} role="option" aria-selected={active}>
                <button
                  type="button"
                  onClick={() => {
                    select(v.id);
                    setOpen(false);
                  }}
                  className={cn(
                    "flex h-10 w-full items-center gap-2.5 rounded-xs px-2.5 text-left text-body transition-colors duration-fast ease-pv hover:bg-surface-2",
                    active ? "text-ink" : "text-ink-2",
                  )}
                >
                  <span aria-hidden className={cn("size-1.5 shrink-0 rounded-full", active ? "bg-accent" : "bg-ink-3")} />
                  <span className="flex-1 truncate">{v.name}</span>
                  {lang && <span className="text-micro text-ink-3">{lang}</span>}
                  {active && <Check className="size-4 text-ink" aria-hidden />}
                </button>
              </li>
            );
          })}
        </ul>
        <div className="mt-1 border-t border-border pt-1">
          <Link
            href="/app/voices/create"
            onClick={() => setOpen(false)}
            className="flex h-10 items-center gap-2.5 rounded-xs px-2.5 text-small font-medium text-ink-2 transition-colors duration-fast ease-pv hover:bg-surface-2 hover:text-ink"
          >
            <Plus className="size-4" aria-hidden />
            Create a new voice
          </Link>
        </div>
      </PopoverContent>
    </PopoverRoot>
  );
}
