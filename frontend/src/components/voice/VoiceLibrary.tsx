"use client";

import Link from "next/link";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useVoices } from "@/lib/api/hooks";
import { VoiceCard } from "./VoiceCard";

export function VoiceLibrary() {
  const q = useVoices();
  const items = q.data?.items ?? [];

  return (
    <div className="mx-auto w-full max-w-[1040px] px-4 py-10 sm:px-6 lg:px-10">
      <PageHeader
        title="My voices"
        description="All your voices, in one place."
        actions={
          items.length > 0 ? (
            <Button variant="primary" asChildLink href="/app/voices/create" leading={<Plus className="size-4" aria-hidden />}>
              New voice
            </Button>
          ) : null
        }
      />

      {q.isPending && (
        <ul className="grid gap-4 sm:grid-cols-2" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <li key={i} className="rounded-md border border-border bg-surface p-4">
              <Skeleton className="h-5 w-32" />
              <Skeleton className="mt-2 h-3 w-48" />
              <Skeleton className="mt-6 h-6 w-20" />
            </li>
          ))}
        </ul>
      )}

      {q.isError && (
        <div className="flex flex-col items-start gap-3">
          <ErrorNote error={q.error} />
          <Button onClick={() => q.refetch()}>Try again</Button>
        </div>
      )}

      {q.isSuccess && items.length === 0 && (
        <EmptyState
          title={
            <>
              Nothing here yet. <em className="italic">Create</em> your first voice.
            </>
          }
          description="A 10–20 second recording is all it takes."
          action={
            <Link
              href="/app/voices/create"
              className="inline-flex h-12 items-center gap-2 rounded-sm bg-ink px-6 text-button font-medium text-ink-inverse transition-colors duration-fast ease-pv hover:bg-ink-2"
            >
              Create your voice
            </Link>
          }
        />
      )}

      {q.isSuccess && items.length > 0 && (
        <ul className="grid gap-4 sm:grid-cols-2">
          {items.map((v) => (
            <VoiceCard key={v.id} voice={v} />
          ))}
        </ul>
      )}
    </div>
  );
}
