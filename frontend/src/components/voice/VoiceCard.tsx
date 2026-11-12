"use client";

import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { Check, MoreHorizontal, Play } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { AudioPlayer } from "@/components/audio/AudioPlayer";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DialogContent, DialogRoot } from "@/components/ui/Dialog";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { IconButton } from "@/components/ui/IconButton";
import { Input } from "@/components/ui/Input";
import { useToast } from "@/components/ui/Toast";
import { useDeleteVoice, useGeneration, useGrantConsent, usePreviewVoice, useRevokeConsent, useUpdateVoice } from "@/lib/api/hooks";
import { generations } from "@/lib/api/resources";
import { CONSENT_TEXT_VERSION, LANGUAGE_NAMES, type Voice } from "@/lib/api/types";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/cn";
import { formatDate, formatDuration } from "@/lib/format";
import { generationStageText } from "@/lib/stages";

const STATUS: Record<Voice["status"], { label: string; tone: BadgeTone }> = {
  processing: { label: "Processing", tone: "processing" },
  ready: { label: "Ready", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  consent_revoked: { label: "Consent revoked", tone: "warning" },
};

const menuItem =
  "flex h-9 cursor-pointer select-none items-center rounded-xs px-2.5 text-small text-ink outline-none data-[highlighted]:bg-surface-2 data-[disabled]:opacity-50";

export function VoiceCard({ voice }: { voice: Voice }) {
  const router = useRouter();
  const { toast } = useToast();
  const selectedId = useAppStore((s) => s.selectedVoiceId);
  const setSelected = useAppStore((s) => s.setSelectedVoiceId);
  const update = useUpdateVoice();
  const remove = useDeleteVoice();
  const preview = usePreviewVoice();
  const revoke = useRevokeConsent();
  const grant = useGrantConsent();

  const [renameOpen, setRenameOpen] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [name, setName] = useState(voice.name);
  const [previewId, setPreviewId] = useState<string | null>(null);
  const previewGen = useGeneration(previewId, { initialData: preview.data?.id === previewId ? preview.data : undefined });

  const status = STATUS[voice.status];
  const isSelected = selectedId === voice.id;
  const lang = voice.language ?? voice.detected_language;
  const duration = voice.reference?.speech_seconds ?? voice.reference?.duration_seconds ?? null;
  const previewActive = previewGen.data && (previewGen.data.status === "queued" || previewGen.data.status === "processing");

  const select = () => {
    setSelected(voice.id);
    router.push("/app");
  };

  const startPreview = () => {
    preview.mutate(
      { id: voice.id },
      {
        onSuccess: (gen) => setPreviewId(gen.id),
        onError: (e) => toast({ title: "Preview could not start", description: e instanceof Error ? e.message : undefined, tone: "danger" }),
      },
    );
  };

  const submitRename = () => {
    const next = name.trim();
    if (!next || next === voice.name) {
      setRenameOpen(false);
      return;
    }
    update.mutate(
      { id: voice.id, body: { name: next } },
      {
        onSuccess: () => setRenameOpen(false),
      },
    );
  };

  return (
    <li
      className={cn(
        "flex flex-col gap-4 rounded-md border bg-surface p-4 transition-colors duration-fast ease-pv",
        isSelected ? "border-border-strong" : "border-border",
      )}
      aria-label={voice.name}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-1">
          <div className="flex items-center gap-2">
            {isSelected && <span aria-hidden className="size-2 shrink-0 rounded-full bg-accent" />}
            <h2 className="truncate text-h3 font-medium text-ink">{voice.name}</h2>
          </div>
          <p className="text-small text-ink-3">
            Created {formatDate(voice.created_at)}
            {duration != null && <> · {formatDuration(duration)} of speech</>}
          </p>
        </div>
        <Dropdown.Root modal={false}>
          <Dropdown.Trigger asChild>
            <IconButton label={`More actions for ${voice.name}`} size="sm">
              <MoreHorizontal className="size-4" aria-hidden />
            </IconButton>
          </Dropdown.Trigger>
          <Dropdown.Portal>
            <Dropdown.Content
              align="end"
              sideOffset={4}
              className="z-50 w-48 rounded-md border border-border bg-surface p-1 shadow-md outline-none data-[state=open]:animate-in data-[state=closed]:animate-out"
            >
              <Dropdown.Item className={menuItem} onSelect={() => setRenameOpen(true)}>
                Rename
              </Dropdown.Item>
              {voice.status === "consent_revoked" ? (
                <Dropdown.Item
                  className={menuItem}
                  onSelect={() => grant.mutate({ id: voice.id, version: CONSENT_TEXT_VERSION })}
                >
                  Re-grant consent
                </Dropdown.Item>
              ) : (
                <Dropdown.Item
                  className={menuItem}
                  disabled={voice.status === "processing"}
                  onSelect={() => revoke.mutate(voice.id)}
                >
                  Revoke consent
                </Dropdown.Item>
              )}
              <Dropdown.Separator className="my-1 h-px bg-border" />
              <Dropdown.Item className={cn(menuItem, "text-danger")} onSelect={() => setDeleteOpen(true)}>
                Delete
              </Dropdown.Item>
            </Dropdown.Content>
          </Dropdown.Portal>
        </Dropdown.Root>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={status.tone}>{status.label}</Badge>
        {lang && (
          <Badge dot={false} tone="neutral">
            {LANGUAGE_NAMES[lang]?.name ?? lang}
            {voice.detected_language && voice.detected_language !== voice.language && voice.language ? ` (heard ${LANGUAGE_NAMES[voice.detected_language]?.name ?? voice.detected_language})` : ""}
          </Badge>
        )}
        {voice.quality?.warnings?.length ? (
          <span className="text-micro text-ink-3">{voice.quality.warnings.join(" · ")}</span>
        ) : null}
      </div>

      {voice.status === "failed" && voice.error && <ErrorNote message={voice.error.message} code={voice.error.code} />}
      {voice.status === "consent_revoked" && (
        <p className="text-small text-ink-2">Generation is paused for this voice until consent is granted again.</p>
      )}
      {(revoke.isError || grant.isError) && <ErrorNote error={revoke.error ?? grant.error} />}

      <div className="mt-auto flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <Button
          size="sm"
          variant={isSelected ? "secondary" : "primary"}
          onClick={select}
          disabled={voice.status !== "ready"}
          leading={isSelected ? <Check className="size-3.5" aria-hidden /> : undefined}
        >
          {isSelected ? "Selected" : "Select"}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          onClick={startPreview}
          disabled={voice.status !== "ready" || preview.isPending || Boolean(previewActive)}
          loading={preview.isPending}
          leading={<Play className="size-3.5" aria-hidden />}
        >
          {previewActive ? `${generationStageText(previewGen.data!)}…` : "Preview"}
        </Button>
      </div>

      {previewGen.data?.status === "completed" && (
        <AudioPlayer
          compact
          autoPlay
          src={generations.audioUrl(previewGen.data.id)}
          duration={previewGen.data.output?.duration_seconds}
          label={`Preview of ${voice.name}`}
        />
      )}
      {previewGen.data?.status === "failed" && (
        <ErrorNote message={previewGen.data.error?.message ?? "Preview failed."} code={previewGen.data.error?.code} />
      )}

      <DialogRoot open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent
          title="Rename voice"
          footer={
            <>
              <Button onClick={() => setRenameOpen(false)}>Cancel</Button>
              <Button variant="primary" onClick={submitRename} loading={update.isPending} disabled={!name.trim()}>
                Save
              </Button>
            </>
          }
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              submitRename();
            }}
            className="flex flex-col gap-3"
          >
            <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} autoFocus />
            {update.isError && <ErrorNote error={update.error} />}
          </form>
        </DialogContent>
      </DialogRoot>

      <DialogRoot open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent
          title={`Delete “${voice.name}”?`}
          description="The reference recording and voice signature are removed. Past generations keep their audio."
          footer={
            <>
              <Button onClick={() => setDeleteOpen(false)}>Cancel</Button>
              <Button
                variant="danger"
                loading={remove.isPending}
                onClick={() =>
                  remove.mutate(voice.id, {
                    onSuccess: () => {
                      if (isSelected) setSelected(null);
                      setDeleteOpen(false);
                      toast({ title: "Voice deleted" });
                    },
                  })
                }
              >
                Delete voice
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
