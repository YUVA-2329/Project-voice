"use client";

import { Download, Pause, Play, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { IconButton } from "@/components/ui/IconButton";
import { Button } from "@/components/ui/Button";
import { getAudioContextCtor } from "@/lib/audio";
import { cn } from "@/lib/cn";
import { formatDuration } from "@/lib/format";
import { LiveLevels } from "./LiveLevels";

interface MeterGraph {
  ctx: AudioContext;
  analyser: AnalyserNode;
}

// A media element can only be wrapped in one MediaElementSourceNode for its lifetime.
const graphs = new WeakMap<HTMLMediaElement, MeterGraph>();

function attachMeter(el: HTMLMediaElement): MeterGraph | null {
  const existing = graphs.get(el);
  if (existing) return existing;
  const Ctor = getAudioContextCtor();
  if (!Ctor) return null;
  try {
    const ctx = new Ctor();
    const source = ctx.createMediaElementSource(el);
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    analyser.smoothingTimeConstant = 0.7;
    source.connect(analyser);
    analyser.connect(ctx.destination);
    const graph = { ctx, analyser };
    graphs.set(el, graph);
    return graph;
  } catch {
    return null;
  }
}

export interface AudioPlayerProps {
  src: string;
  /** Known duration in seconds (recorder blobs often report Infinity until fully buffered). */
  duration?: number | null;
  downloadHref?: string;
  downloadName?: string;
  onRegenerate?: () => void;
  regenerateDisabled?: boolean;
  autoPlay?: boolean;
  compact?: boolean;
  /** Accessible name for the player region. */
  label?: string;
  className?: string;
  onError?: (message: string) => void;
}

export function AudioPlayer({
  src,
  duration: knownDuration,
  downloadHref,
  downloadName,
  onRegenerate,
  regenerateDisabled,
  autoPlay = false,
  compact = false,
  label = "Audio player",
  className,
  onError,
}: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState<number>(knownDuration && Number.isFinite(knownDuration) ? knownDuration : 0);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const [seeking, setSeeking] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);

  useEffect(() => {
    if (knownDuration && Number.isFinite(knownDuration)) setDuration(knownDuration);
  }, [knownDuration]);

  // Reset on source change.
  useEffect(() => {
    setCurrent(0);
    setPlaying(false);
    setFailed(null);
  }, [src]);

  const togglePlay = useCallback(async () => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) {
      const graph = attachMeter(el);
      if (graph) {
        if (graph.ctx.state === "suspended") await graph.ctx.resume().catch(() => undefined);
        setAnalyser(graph.analyser);
      }
      try {
        await el.play();
      } catch (e) {
        const msg = e instanceof Error && e.name === "NotSupportedError" ? "This browser cannot play the audio format." : "Playback could not start.";
        setFailed(msg);
        onError?.(msg);
      }
    } else {
      el.pause();
    }
  }, [onError]);

  useEffect(() => {
    if (!autoPlay) return;
    const el = audioRef.current;
    if (!el) return;
    const onCanPlay = () => void togglePlay();
    el.addEventListener("canplay", onCanPlay, { once: true });
    return () => el.removeEventListener("canplay", onCanPlay);
  }, [autoPlay, src, togglePlay]);

  const onLoaded = () => {
    const el = audioRef.current;
    if (!el) return;
    if (Number.isFinite(el.duration) && el.duration > 0) setDuration(el.duration);
  };

  const onTime = () => {
    const el = audioRef.current;
    if (!el || seeking) return;
    setCurrent(el.currentTime);
    // Recorder blobs: duration becomes known as playback proceeds.
    if (Number.isFinite(el.duration) && el.duration > 0 && Math.abs(el.duration - duration) > 0.05) setDuration(el.duration);
  };

  const seekTo = (value: number) => {
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = value;
    setCurrent(value);
  };

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === " " || e.key === "k") {
      e.preventDefault();
      void togglePlay();
    }
  };

  const max = duration > 0 ? duration : 0;
  const pct = max > 0 ? Math.min(100, (current / max) * 100) : 0;

  return (
    <div
      role="group"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={cn("flex flex-col gap-3 rounded-md border border-border bg-surface p-3", className)}
    >
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        crossOrigin="anonymous"
        onLoadedMetadata={onLoaded}
        onDurationChange={onLoaded}
        onTimeUpdate={onTime}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => {
          setPlaying(false);
          setCurrent(0);
        }}
        onError={() => {
          const msg = "The audio could not be loaded.";
          setFailed(msg);
          onError?.(msg);
        }}
      />
      <div className="flex items-center gap-3">
        <IconButton
          label={playing ? "Pause" : "Play"}
          onClick={() => void togglePlay()}
          disabled={Boolean(failed)}
          className={cn("shrink-0 rounded-full border border-border bg-surface text-ink hover:border-border-strong hover:bg-surface-2")}
        >
          {playing ? <Pause className="size-4" aria-hidden /> : <Play className="ml-0.5 size-4" aria-hidden />}
        </IconButton>

        <div className="flex min-w-0 flex-1 flex-col gap-1.5">
          <div className="relative flex h-6 items-center">
            <div aria-hidden className="absolute inset-x-0 h-px bg-border-strong" />
            <div aria-hidden className="absolute left-0 h-px bg-ink" style={{ width: `${pct}%` }} />
            <input
              type="range"
              aria-label="Seek"
              aria-valuetext={`${formatDuration(current)} of ${formatDuration(max)}`}
              min={0}
              max={max || 1}
              step={0.01}
              value={Math.min(current, max || 1)}
              disabled={max <= 0 || Boolean(failed)}
              onPointerDown={() => setSeeking(true)}
              onPointerUp={() => setSeeking(false)}
              onKeyUp={() => setSeeking(false)}
              onChange={(e) => {
                setSeeking(true);
                seekTo(Number(e.target.value));
              }}
              onMouseUp={() => setSeeking(false)}
              onTouchEnd={() => setSeeking(false)}
              className="pv-scrubber relative h-6 w-full cursor-pointer appearance-none bg-transparent disabled:cursor-default"
            />
          </div>
          {!compact && (
            <div className="flex items-center justify-between font-mono text-micro tabular text-ink-3">
              <span>{formatDuration(current)}</span>
              <span>{formatDuration(max)}</span>
            </div>
          )}
        </div>

        <LiveLevels analyser={analyser} active={playing} size={compact ? 20 : 24} className="shrink-0" />

        {compact && (
          <span className="shrink-0 font-mono text-micro tabular text-ink-3">
            {formatDuration(current)} / {formatDuration(max)}
          </span>
        )}

        {(downloadHref || onRegenerate) && (
          <div className="flex shrink-0 items-center gap-1">
            {downloadHref && (
              <IconButton label="Download" asChildAnchor href={downloadHref} download={downloadName}>
                <Download className="size-4" aria-hidden />
              </IconButton>
            )}
            {onRegenerate && !compact && (
              <Button size="sm" variant="ghost" onClick={onRegenerate} disabled={regenerateDisabled} leading={<RotateCcw className="size-3.5" aria-hidden />}>
                Regenerate
              </Button>
            )}
            {onRegenerate && compact && (
              <IconButton label="Regenerate" size="sm" onClick={onRegenerate} disabled={regenerateDisabled}>
                <RotateCcw className="size-4" aria-hidden />
              </IconButton>
            )}
          </div>
        )}
      </div>
      {failed && (
        <p role="alert" className="text-small text-danger">
          {failed}
        </p>
      )}
    </div>
  );
}
