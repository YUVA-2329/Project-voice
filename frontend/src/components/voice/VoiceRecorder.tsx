"use client";

import { Mic, Pause, Play, RotateCcw, Square } from "lucide-react";
import { useEffect, useState } from "react";
import { AudioPlayer } from "@/components/audio/AudioPlayer";
import { LiveLevels } from "@/components/audio/LiveLevels";
import { Waveform } from "@/components/audio/Waveform";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { MIN_REFERENCE_SECONDS } from "@/lib/api/types";
import { decodeAudio } from "@/lib/audio";
import { useRecorder, type Recording } from "@/lib/audio/recorder";
import { cn } from "@/lib/cn";
import { formatDuration } from "@/lib/format";

export const SUGGESTED_PASSAGE =
  "The morning light came in slowly, the way it always did in late autumn. I made a cup of tea, opened the window a little, and listened to the street wake up. Nothing special happened, and that was exactly the point.";

export interface CapturedAudio {
  blob: Blob;
  fileName: string;
  duration: number | null;
  peaks: Float32Array | null;
  source: "recording" | "upload";
}

export function VoiceRecorder({ onCaptured, className }: { onCaptured: (audio: CapturedAudio | null) => void; className?: string }) {
  const rec = useRecorder();
  const [peaks, setPeaks] = useState<Float32Array | null>(null);
  const [tooShort, setTooShort] = useState(false);

  // When a recording finishes, decode it for a static waveform and hand it up.
  useEffect(() => {
    let cancelled = false;
    const r: Recording | null = rec.recording;
    if (!r) {
      setPeaks(null);
      setTooShort(false);
      onCaptured(null);
      return;
    }
    if (r.duration < MIN_REFERENCE_SECONDS) {
      setTooShort(true);
      onCaptured(null);
      return;
    }
    setTooShort(false);
    (async () => {
      let decoded: { peaks: Float32Array; duration: number } | null = null;
      try {
        decoded = await decodeAudio(r.blob);
      } catch {
        decoded = null;
      }
      if (cancelled) return;
      setPeaks(decoded?.peaks ?? null);
      onCaptured({
        blob: r.blob,
        fileName: `recording.${r.extension}`,
        duration: decoded && Number.isFinite(decoded.duration) ? decoded.duration : r.duration,
        peaks: decoded?.peaks ?? null,
        source: "recording",
      });
    })();
    return () => {
      cancelled = true;
    };
    // onCaptured is intentionally excluded: parent passes a stable setter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rec.recording]);

  const live = rec.state === "recording";
  const statusText =
    rec.state === "requesting"
      ? "Waiting for microphone permission…"
      : rec.state === "recording"
        ? `Recording · ${formatDuration(rec.elapsed)}`
        : rec.state === "paused"
          ? `Paused · ${formatDuration(rec.elapsed)}`
          : rec.state === "stopped"
            ? `Recorded ${formatDuration(rec.recording?.duration ?? rec.elapsed)}`
            : "";

  return (
    <div className={cn("flex flex-col gap-6", className)}>
      <div className="flex flex-col gap-2">
        <h2 className="display text-h2 text-ink">Record a sample.</h2>
        <p className="text-body text-ink-2">Read naturally for 10–20 seconds. Quiet room, normal speaking voice.</p>
      </div>

      <figure className="rounded-md border border-border bg-surface-2 p-4">
        <figcaption className="eyebrow mb-2">Suggested passage</figcaption>
        <blockquote className="display text-[22px] leading-[1.3] text-ink">{SUGGESTED_PASSAGE}</blockquote>
      </figure>

      {rec.state === "unsupported" ? (
        <ErrorNote message="This browser cannot record audio. Upload a recording instead." code="media_recorder_unsupported" />
      ) : (
        <div className="flex flex-col gap-4 rounded-md border border-border bg-surface p-4">
          <div className="flex items-center gap-4">
            <LiveLevels analyser={rec.analyser} active={live} size={40} />
            <div className="flex min-w-0 flex-1 flex-col">
              <p className="font-mono text-small tabular text-ink" aria-live="polite" aria-atomic="true" role="status">
                {statusText || (rec.state === "idle" || rec.state === "denied" ? "Ready to record" : "")}
              </p>
              <p className="text-micro text-ink-3">
                {rec.state === "idle" && "We will ask for microphone permission when you press record."}
                {rec.state === "recording" && "Speak at a steady pace. Press stop when you are done."}
                {rec.state === "paused" && "Resume when you are ready."}
                {rec.state === "stopped" && "Listen back, then continue or record again."}
              </p>
            </div>
            {live && <span aria-hidden className="size-2.5 rounded-full bg-accent" />}
          </div>

          {rec.state === "stopped" && peaks && <Waveform peaks={peaks} height={40} />}

          <div className="flex flex-wrap items-center gap-2">
            {(rec.state === "idle" || rec.state === "denied") && (
              <Button variant="primary" size="lg" onClick={() => void rec.start()} leading={<Mic className="size-4" aria-hidden />}>
                Start recording
              </Button>
            )}
            {rec.state === "requesting" && (
              <Button variant="primary" size="lg" loading>
                Requesting microphone
              </Button>
            )}
            {rec.state === "recording" && (
              <>
                <Button variant="primary" size="lg" onClick={rec.stop} leading={<Square className="size-4" aria-hidden />}>
                  Stop
                </Button>
                {rec.canPause && (
                  <Button size="lg" onClick={rec.pause} leading={<Pause className="size-4" aria-hidden />}>
                    Pause
                  </Button>
                )}
              </>
            )}
            {rec.state === "paused" && (
              <>
                <Button variant="primary" size="lg" onClick={rec.resume} leading={<Play className="size-4" aria-hidden />}>
                  Resume
                </Button>
                <Button size="lg" onClick={rec.stop} leading={<Square className="size-4" aria-hidden />}>
                  Stop
                </Button>
              </>
            )}
            {rec.state === "stopped" && (
              <Button size="lg" onClick={rec.reset} leading={<RotateCcw className="size-4" aria-hidden />}>
                Record again
              </Button>
            )}
          </div>

          {rec.state === "stopped" && rec.recording && !tooShort && (
            <AudioPlayer src={rec.recording.url} duration={rec.recording.duration} label="Your recording" />
          )}

          {tooShort && (
            <ErrorNote
              message={`That was under ${MIN_REFERENCE_SECONDS} seconds. Record a little longer — aim for 10 to 20 seconds.`}
              code="reference_too_short"
            />
          )}
          {rec.error && <ErrorNote message={rec.error} code={rec.state === "denied" ? "microphone_denied" : null} />}
        </div>
      )}
    </div>
  );
}
