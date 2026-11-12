"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { VoiceSelector, useSelectedVoice } from "@/components/voice/VoiceSelector";
import { useCreateGeneration, useGeneration, useMe } from "@/lib/api/hooks";
import { isApiError } from "@/lib/api/client";
import { MAX_TEXT_CHARS, type GenerationCreate } from "@/lib/api/types";
import { GenerationResult } from "./GenerationResult";
import { RunButton } from "./RunButton";
import { TextComposer } from "./TextComposer";

const DRAFT_KEY = "pv-draft";

function readDraft(): string {
  try {
    return sessionStorage.getItem(DRAFT_KEY) ?? "";
  } catch {
    return "";
  }
}

function writeDraft(text: string) {
  try {
    if (text) sessionStorage.setItem(DRAFT_KEY, text);
    else sessionStorage.removeItem(DRAFT_KEY);
  } catch {
    /* ignore */
  }
}

export interface ComposerProps {
  /** Advanced mode: metrics line, language chip, and caller-supplied request parameters. */
  advanced?: boolean;
  /** Extra generation parameters (Advanced mode). Simple mode uses the user's preferences. */
  params?: Partial<Omit<GenerationCreate, "voice_id" | "text">>;
  chips?: ReactNode;
  /** Rendered between the composer and the run row (Advanced controls). */
  controls?: ReactNode;
}

export function Composer({ advanced = false, params, chips, controls }: ComposerProps) {
  const me = useMe();
  const { selected, readyVoices, isPending: voicesPending } = useSelectedVoice();
  const create = useCreateGeneration();
  const [text, setText] = useState("");
  const [generationId, setGenerationId] = useState<string | null>(null);
  const [hydrated, setHydrated] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    setText(readDraft());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) writeDraft(text);
  }, [text, hydrated]);

  const generation = useGeneration(generationId, { initialData: create.data?.id === generationId ? create.data : undefined });
  const current = generation.data ?? null;
  const running = current && (current.status === "queued" || current.status === "processing") ? current : null;

  const trimmed = text.trim();
  let disabledReason: string | null = null;
  if (voicesPending) disabledReason = "Loading your voices";
  else if (readyVoices.length === 0) disabledReason = "Create a voice first";
  else if (!selected) disabledReason = "Choose a voice first";
  else if (!trimmed) disabledReason = "Write something to say";
  else if (text.length > MAX_TEXT_CHARS) disabledReason = `Keep it under ${MAX_TEXT_CHARS.toLocaleString()} characters`;

  const runWith = useCallback(
    (voiceId: string, body_text: string) => {
      if (running || create.isPending) return;
      const prefs = me.data?.preferences;
      const body: GenerationCreate = {
        voice_id: voiceId,
        text: body_text,
        language: params?.language ?? prefs?.default_language ?? "auto",
        speed: params?.speed ?? prefs?.speed ?? 1,
        output_format: params?.output_format ?? prefs?.output_format ?? "wav",
      };
      if (params?.quality) body.quality = params.quality;
      const engine = params?.engine_id ?? (advanced ? (prefs?.default_engine ?? undefined) : undefined);
      if (engine) body.engine_id = engine;
      create.mutate(body, { onSuccess: (gen) => setGenerationId(gen.id) });
    },
    [running, create, me.data, params, advanced],
  );

  const run = useCallback(() => {
    if (disabledReason || !selected) return;
    runWith(selected.id, trimmed);
  }, [disabledReason, selected, runWith, trimmed]);

  /** Same voice, same text, new generation. */
  const regenerate = useCallback(() => {
    if (!current) return;
    const voiceId = current.voice_id ?? selected?.id;
    if (!voiceId) return;
    runWith(voiceId, current.text);
  }, [current, selected, runWith]);

  const showMetrics = advanced;
  const createError = create.isError ? create.error : null;
  const supportedEngines =
    isApiError(createError) && Array.isArray(createError.details?.supported_engines)
      ? (createError.details.supported_engines as string[])
      : null;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-2">
        <p className="eyebrow">Selected voice</p>
        <VoiceSelector />
      </div>

      <div className="flex flex-col gap-4">
        <TextComposer
          ref={textareaRef}
          value={text}
          onChange={setText}
          onRun={run}
          disabled={Boolean(running) || create.isPending}
          chips={chips}
        />
        {controls}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            {createError && (
              <ErrorNote
                error={createError}
                message={
                  supportedEngines && supportedEngines.length > 0
                    ? `${createError instanceof Error ? createError.message : ""} Engines that support it: ${supportedEngines.join(", ")}.`
                    : undefined
                }
              />
            )}
          </div>
          <RunButton onRun={run} disabledReason={disabledReason} running={running} submitting={create.isPending} />
        </div>
      </div>

      {current && (
        <GenerationResult
          generation={current}
          showMetrics={showMetrics}
          onRegenerate={regenerate}
          regenerateDisabled={Boolean(running) || create.isPending || (!current.voice_id && !selected)}
        />
      )}
      {generation.isError && (
        <ErrorNote error={generation.error} />
      )}
    </div>
  );
}
