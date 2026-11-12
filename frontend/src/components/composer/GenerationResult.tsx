"use client";

import { AudioPlayer } from "@/components/audio/AudioPlayer";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { generations } from "@/lib/api/resources";
import { LANGUAGE_NAMES, type Generation } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatDuration, formatSeconds, formatRtf } from "@/lib/format";
import { generationStageText, progressFraction } from "@/lib/stages";

export function GenerationResult({
  generation,
  onRegenerate,
  regenerateDisabled,
  showMetrics = false,
  className,
}: {
  generation: Generation;
  onRegenerate?: () => void;
  regenerateDisabled?: boolean;
  showMetrics?: boolean;
  className?: string;
}) {
  const g = generation;
  const active = g.status === "queued" || g.status === "processing";
  const lang = g.language ? LANGUAGE_NAMES[g.language]?.name : null;

  return (
    <section aria-label="Result" aria-live="polite" className={cn("flex flex-col gap-3", className)}>
      <div className="flex flex-col gap-2">
        <p className="eyebrow">Output</p>
        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
          <p className="text-small text-ink-2">
            {active && <span>{generationStageText(g)}…</span>}
            {g.status === "completed" && g.output && (
              <span>
                Ready · {formatDuration(g.output.duration_seconds)} · {g.output.format.toUpperCase()}
                {lang ? ` · ${lang}` : ""}
                {g.voice_name ? ` · ${g.voice_name}` : ""}
              </span>
            )}
            {g.status === "failed" && <span className="text-danger">{g.error?.message ?? "Generation failed."}</span>}
            {g.status === "cancelled" && <span>Cancelled.</span>}
          </p>
          {g.status === "failed" && g.error?.code && <span className="font-mono text-micro text-ink-3">{g.error.code}</span>}
          {showMetrics && g.status === "completed" && g.engine_id && (
            <span className="font-mono text-micro text-ink-3">{g.engine_id}</span>
          )}
        </div>
        {active && g.status === "processing" && (
          <ProgressBar fraction={progressFraction(g.progress)} label="Generation progress" />
        )}
      </div>

      {g.status === "completed" && (
        <AudioPlayer
          src={generations.audioUrl(g.id)}
          duration={g.output?.duration_seconds ?? null}
          downloadHref={generations.audioUrl(g.id, true)}
          onRegenerate={onRegenerate}
          regenerateDisabled={regenerateDisabled}
          label={`Generated audio for ${g.voice_name}`}
        />
      )}

      {g.status === "failed" && onRegenerate && (
        <div>
          <button
            type="button"
            onClick={onRegenerate}
            disabled={regenerateDisabled}
            className="text-button font-medium text-ink underline-offset-4 hover:underline disabled:opacity-50"
          >
            Try again
          </button>
        </div>
      )}

      {showMetrics && g.status === "completed" && g.metrics && (
        <p className="font-mono text-micro tabular text-ink-3">
          inference {formatSeconds(g.metrics.inference_seconds)} · total {formatSeconds(g.metrics.total_seconds)} · rtf{" "}
          {formatRtf(g.metrics.real_time_factor)} · {g.metrics.chunks} {g.metrics.chunks === 1 ? "chunk" : "chunks"} ·{" "}
          {g.metrics.device} · peak {g.metrics.peak_dbfs.toFixed(1)} dBFS
          {g.output ? ` · ${(g.output.sample_rate / 1000).toFixed(0)} kHz` : ""}
        </p>
      )}
    </section>
  );
}
