"use client";

import { useMemo, useState } from "react";
import { AudioPlayer } from "@/components/audio/AudioPlayer";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { Select, type SelectOption } from "@/components/ui/Select";
import { Slider } from "@/components/ui/Slider";
import { Textarea } from "@/components/ui/Textarea";
import { useLanguageOptions } from "@/components/voice/VoiceNameField";
import { useModels, useUpdateVoice } from "@/lib/api/hooks";
import { voices as voicesApi } from "@/lib/api/resources";
import { LANGUAGE_NAMES, type GenerationCreate, type LanguageHint, type OutputFormat, type Quality, type Voice } from "@/lib/api/types";
import { formatDuration } from "@/lib/format";

export type AdvancedParams = Required<Pick<GenerationCreate, "language" | "speed" | "output_format" | "quality">> & {
  engine_id: string | undefined;
};

export const AUTO_ENGINE = "__auto__";

export function AdvancedControls({
  params,
  onChange,
  voice,
}: {
  params: AdvancedParams;
  onChange: (next: AdvancedParams) => void;
  voice: Voice | null;
}) {
  const { options: languageOptions, note } = useLanguageOptions();
  const models = useModels();

  const engineOptions = useMemo<SelectOption<string>[]>(() => {
    const opts: SelectOption<string>[] = [{ value: AUTO_ENGINE, label: "Automatic", description: "Best available engine for the language." }];
    for (const m of models.data ?? []) {
      const langs = m.tts_languages.map((l) => LANGUAGE_NAMES[l]?.name ?? l).join(", ");
      opts.push({
        value: m.id,
        label: m.available ? `${m.name} ${m.version}` : `${m.name} — unavailable`,
        description: m.available ? `${langs}${m.loaded ? ` · loaded on ${m.device}` : ""}` : m.unavailable_reason ?? "Weights missing.",
        disabled: !m.available,
      });
    }
    return opts;
  }, [models.data]);

  const set = <K extends keyof AdvancedParams>(key: K, value: AdvancedParams[K]) => onChange({ ...params, [key]: value });

  return (
    <div className="flex flex-col gap-6 rounded-md border border-border bg-surface p-4 sm:p-5">
      <p className="eyebrow">Controls</p>
      <div className="grid gap-5 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <Select<LanguageHint> label="Language" value={params.language} onValueChange={(v) => set("language", v)} options={languageOptions} />
          {note && <p className="text-micro text-ink-3">{note}</p>}
        </div>
        <Select<string>
          label="Engine"
          value={params.engine_id ?? AUTO_ENGINE}
          onValueChange={(v) => set("engine_id", v === AUTO_ENGINE ? undefined : v)}
          options={engineOptions}
          disabled={models.isPending}
        />
        <Select<OutputFormat>
          label="Output format"
          value={params.output_format}
          onValueChange={(v) => set("output_format", v)}
          options={[
            { value: "wav", label: "WAV" },
            { value: "flac", label: "FLAC" },
            { value: "mp3", label: "MP3" },
          ]}
        />
        <Select<Quality>
          label="Quality"
          value={params.quality}
          onValueChange={(v) => set("quality", v)}
          options={[
            { value: "fast", label: "Fast", description: "Fewer steps, quicker." },
            { value: "balanced", label: "Balanced", description: "Default trade-off." },
            { value: "high", label: "High", description: "More steps, slower." },
          ]}
        />
      </div>
      <Slider label="Speed" min={0.5} max={2} step={0.05} value={params.speed} onValueChange={(v) => set("speed", v)} format={(v) => `${v.toFixed(2)}×`} />
      {models.isError && <ErrorNote error={models.error} />}

      {voice && <ReferencePanel voice={voice} />}
    </div>
  );
}

function ReferencePanel({ voice }: { voice: Voice }) {
  const update = useUpdateVoice();
  const [draft, setDraft] = useState<string | null>(null);
  const value = draft ?? voice.transcript ?? "";
  const dirty = draft != null && draft.trim() !== (voice.transcript ?? "").trim();

  return (
    <div className="flex flex-col gap-4 border-t border-border pt-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="eyebrow">Reference audio</p>
        <div className="flex items-center gap-2">
          {voice.engine_id && <Badge dot={false} mono>{voice.engine_id}</Badge>}
          {voice.reference && (
            <span className="font-mono text-micro tabular text-ink-3">
              {voice.reference.speech_seconds != null ? `${formatDuration(voice.reference.speech_seconds)} speech · ` : ""}
              {(voice.reference.sample_rate / 1000).toFixed(0)} kHz · {voice.reference.channels === 1 ? "mono" : `${voice.reference.channels} ch`}
            </span>
          )}
        </div>
      </div>
      {voice.status === "ready" ? (
        <AudioPlayer src={voicesApi.referenceAudioUrl(voice.id)} duration={voice.reference?.speech_seconds ?? voice.reference?.duration_seconds} label={`Reference audio for ${voice.name}`} compact />
      ) : (
        <p className="text-small text-ink-3">Reference audio is available once the voice is ready.</p>
      )}
      <div className="flex flex-col gap-2">
        <label htmlFor="ref-transcript" className="text-small font-medium text-ink-2">
          Reference transcript
        </label>
        <Textarea id="ref-transcript" rows={3} value={value} onChange={(e) => setDraft(e.target.value)} />
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant={dirty ? "primary" : "secondary"}
            disabled={!dirty}
            loading={update.isPending}
            onClick={() => update.mutate({ id: voice.id, body: { transcript: value.trim() } }, { onSuccess: () => setDraft(null) })}
          >
            Save transcript
          </Button>
          {voice.transcript_source && (
            <span className="font-mono text-micro text-ink-3">{voice.transcript_source === "auto" ? "auto transcript" : "your transcript"}</span>
          )}
        </div>
        {update.isError && <ErrorNote error={update.error} />}
      </div>
    </div>
  );
}
