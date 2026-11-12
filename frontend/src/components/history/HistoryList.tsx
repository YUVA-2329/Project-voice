"use client";

import { Download, Play, Trash2, X } from "lucide-react";
import { useState } from "react";
import { AudioPlayer } from "@/components/audio/AudioPlayer";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DialogContent, DialogRoot } from "@/components/ui/Dialog";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { IconButton } from "@/components/ui/IconButton";
import { PageHeader } from "@/components/ui/PageHeader";
import { Skeleton } from "@/components/ui/Skeleton";
import { useDeleteGeneration, useGenerations } from "@/lib/api/hooks";
import { generations } from "@/lib/api/resources";
import type { Generation } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { excerpt, formatDateTime, formatDuration } from "@/lib/format";
import { generationStageText } from "@/lib/stages";

const STATUS: Record<Generation["status"], { label: string; tone: BadgeTone }> = {
  queued: { label: "Queued", tone: "processing" },
  processing: { label: "Processing", tone: "processing" },
  completed: { label: "Ready", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

export function HistoryList() {
  const q = useGenerations();
  const items = q.data?.pages.flatMap((p) => p.items) ?? [];
  const total = q.data?.pages[0]?.total ?? 0;

  return (
    <div className="mx-auto w-full max-w-[1040px] px-4 py-10 sm:px-6 lg:px-10">
      <PageHeader
        title="History"
        description={total > 0 ? `${total.toLocaleString()} ${total === 1 ? "generation" : "generations"}, newest first.` : "Everything you have generated, newest first."}
      />

      {q.isPending && (
        <ul className="flex flex-col divide-y divide-border border-y border-border" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <li key={i} className="flex flex-col gap-2 py-4">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-3 w-48" />
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
          title="Nothing here yet."
          description="Run your first generation and it will appear here."
          action={
            <Button variant="primary" size="lg" asChildLink href="/app">
              Go to Create
            </Button>
          }
        />
      )}

      {items.length > 0 && (
        <ul className="flex flex-col divide-y divide-border border-y border-border">
          {items.map((g) => (
            <HistoryRow key={g.id} generation={g} />
          ))}
        </ul>
      )}

      {q.hasNextPage && (
        <div className="flex justify-center pt-8">
          <Button onClick={() => q.fetchNextPage()} loading={q.isFetchingNextPage}>
            Load more
          </Button>
        </div>
      )}
    </div>
  );
}

function HistoryRow({ generation: g }: { generation: Generation }) {
  const [open, setOpen] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const remove = useDeleteGeneration();
  const status = STATUS[g.status];
  const active = g.status === "queued" || g.status === "processing";

  return (
    <li className="flex flex-col gap-3 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <p className="text-body text-ink">{excerpt(g.text, 160)}</p>
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-small text-ink-3">
            <span className="text-ink-2">{g.voice_name}</span>
            <span aria-hidden>·</span>
            <time dateTime={g.created_at}>{formatDateTime(g.created_at)}</time>
            {g.output && (
              <>
                <span aria-hidden>·</span>
                <span className="font-mono tabular">{formatDuration(g.output.duration_seconds)}</span>
              </>
            )}
            <Badge tone={status.tone} className="ml-1">
              {active ? generationStageText(g) : status.label}
            </Badge>
          </p>
          {g.status === "failed" && g.error && <ErrorNote message={g.error.message} code={g.error.code} />}
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          {g.status === "completed" && (
            <>
              <IconButton label={open ? "Hide player" : "Play"} onClick={() => setOpen((o) => !o)}>
                {open ? <X className="size-4" aria-hidden /> : <Play className="size-4" aria-hidden />}
              </IconButton>
              <IconButton label="Download" asChildAnchor href={generations.audioUrl(g.id, true)}>
                <Download className="size-4" aria-hidden />
              </IconButton>
            </>
          )}
          <IconButton label="Delete" tone="danger" onClick={() => setConfirm(true)} disabled={active}>
            <Trash2 className="size-4" aria-hidden />
          </IconButton>
        </div>
      </div>

      {open && g.status === "completed" && (
        <AudioPlayer
          src={generations.audioUrl(g.id)}
          duration={g.output?.duration_seconds}
          downloadHref={generations.audioUrl(g.id, true)}
          autoPlay
          label={`Generated audio for ${g.voice_name}`}
          className={cn("animate-in")}
        />
      )}

      <DialogRoot open={confirm} onOpenChange={setConfirm}>
        <DialogContent
          title="Delete this generation?"
          description="The audio file is removed. This cannot be undone."
          footer={
            <>
              <Button onClick={() => setConfirm(false)}>Cancel</Button>
              <Button variant="danger" loading={remove.isPending} onClick={() => remove.mutate(g.id, { onSuccess: () => setConfirm(false) })}>
                Delete
              </Button>
            </>
          }
        >
          {remove.isError && <ErrorNote error={remove.error} />}
        </DialogContent>
      </DialogRoot>
    </li>
  );
}
