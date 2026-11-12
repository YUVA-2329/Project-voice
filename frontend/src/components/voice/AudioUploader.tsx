"use client";

import { FileAudio, Upload, X } from "lucide-react";
import { useCallback, useEffect, useId, useRef, useState, type DragEvent } from "react";
import { AudioPlayer } from "@/components/audio/AudioPlayer";
import { Waveform } from "@/components/audio/Waveform";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { MAX_REFERENCE_SECONDS, MAX_UPLOAD_BYTES, MIN_REFERENCE_SECONDS } from "@/lib/api/types";
import { ACCEPT_ATTR, ACCEPTED_EXTENSIONS, decodeAudio, isAcceptedExtension } from "@/lib/audio";
import { cn } from "@/lib/cn";
import { formatBytes, formatDuration } from "@/lib/format";
import type { CapturedAudio } from "./VoiceRecorder";

interface Picked {
  file: File;
  url: string;
  duration: number | null;
  peaks: Float32Array | null;
  decodeFailed: boolean;
}

export function validateFile(file: File): { code: string; message: string } | null {
  if (!isAcceptedExtension(file.name)) {
    return {
      code: "unsupported_format",
      message: `That file type is not supported. Use ${ACCEPTED_EXTENSIONS.map((e) => e.toUpperCase()).join(", ")}.`,
    };
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return { code: "file_too_large", message: `That file is ${formatBytes(file.size)}. The limit is ${formatBytes(MAX_UPLOAD_BYTES)}.` };
  }
  if (file.size === 0) {
    return { code: "file_empty", message: "That file is empty." };
  }
  return null;
}

export function validateDuration(duration: number): { code: string; message: string } | null {
  if (duration < MIN_REFERENCE_SECONDS) {
    return { code: "reference_too_short", message: `That recording is ${formatDuration(duration)}. It needs to be at least ${MIN_REFERENCE_SECONDS} seconds.` };
  }
  if (duration > MAX_REFERENCE_SECONDS) {
    return {
      code: "reference_too_long",
      message: `That recording is ${formatDuration(duration)}. Keep it under ${formatDuration(MAX_REFERENCE_SECONDS)} — 10 to 30 seconds is ideal.`,
    };
  }
  return null;
}

export function AudioUploader({ onCaptured, className }: { onCaptured: (audio: CapturedAudio | null) => void; className?: string }) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  const [picked, setPicked] = useState<Picked | null>(null);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [decoding, setDecoding] = useState(false);

  useEffect(() => {
    return () => {
      if (picked) URL.revokeObjectURL(picked.url);
    };
  }, [picked]);

  const clear = useCallback(() => {
    setPicked(null);
    setError(null);
    onCaptured(null);
    if (inputRef.current) inputRef.current.value = "";
  }, [onCaptured]);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      const invalid = validateFile(file);
      if (invalid) {
        setPicked(null);
        setError(invalid);
        onCaptured(null);
        return;
      }
      setDecoding(true);
      let duration: number | null = null;
      let peaks: Float32Array | null = null;
      let decodeFailed = false;
      try {
        const info = await decodeAudio(file);
        duration = Number.isFinite(info.duration) ? info.duration : null;
        peaks = info.peaks;
      } catch {
        decodeFailed = true;
      }
      setDecoding(false);
      if (duration != null) {
        const bad = validateDuration(duration);
        if (bad) {
          setPicked(null);
          setError(bad);
          onCaptured(null);
          return;
        }
      }
      const url = URL.createObjectURL(file);
      setPicked({ file, url, duration, peaks, decodeFailed });
      onCaptured({ blob: file, fileName: file.name, duration, peaks, source: "upload" });
    },
    [onCaptured],
  );

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) void handleFile(file);
  };

  return (
    <div className={cn("flex flex-col gap-6", className)}>
      <div className="flex flex-col gap-2">
        <h2 className="display text-h2 text-ink">Upload a recording.</h2>
        <p className="text-body text-ink-2">
          Clear speech from one person, {MIN_REFERENCE_SECONDS} seconds to {formatDuration(MAX_REFERENCE_SECONDS)} long. WAV, MP3, M4A, FLAC, OGG or WebM, up to{" "}
          {formatBytes(MAX_UPLOAD_BYTES)}.
        </p>
      </div>

      {!picked ? (
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={cn(
            "flex flex-col items-center justify-center gap-3 rounded-md border border-dashed bg-surface px-6 py-12 text-center transition-colors duration-fast ease-pv",
            dragging ? "border-ink bg-surface-2" : "border-border-strong",
          )}
        >
          <Upload className="size-6 text-ink-3" aria-hidden />
          <p className="text-body text-ink-2">Drag a file here, or</p>
          <label
            htmlFor={inputId}
            className="inline-flex h-10 cursor-pointer items-center rounded-sm border border-border bg-surface px-4 text-button font-medium text-ink transition-colors duration-fast ease-pv hover:border-border-strong hover:bg-surface-2 focus-within:outline focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-accent"
          >
            {decoding ? "Reading file…" : "Choose a file"}
            <input
              ref={inputRef}
              id={inputId}
              type="file"
              accept={ACCEPT_ATTR}
              className="sr-only"
              disabled={decoding}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) void handleFile(f);
              }}
            />
          </label>
        </div>
      ) : (
        <div className="flex flex-col gap-4 rounded-md border border-border bg-surface p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="flex min-w-0 items-center gap-3">
              <FileAudio className="size-5 shrink-0 text-ink-3" aria-hidden />
              <div className="min-w-0">
                <p className="truncate text-body font-medium text-ink">{picked.file.name}</p>
                <p className="font-mono text-micro tabular text-ink-3">
                  {formatBytes(picked.file.size)}
                  {picked.duration != null ? ` · ${formatDuration(picked.duration)}` : ""}
                </p>
              </div>
            </div>
            <Button size="sm" variant="ghost" onClick={clear} leading={<X className="size-3.5" aria-hidden />}>
              Remove
            </Button>
          </div>
          {picked.peaks && <Waveform peaks={picked.peaks} height={40} />}
          {picked.decodeFailed && (
            <p className="text-small text-ink-2">
              This browser could not decode the file to check its length. The server will verify it after upload.
            </p>
          )}
          <AudioPlayer src={picked.url} duration={picked.duration} label="Uploaded recording" />
        </div>
      )}

      {error && <ErrorNote message={error.message} code={error.code} />}
    </div>
  );
}
