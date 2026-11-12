"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getAudioContextCtor, pickRecorderMime } from "./index";

export type RecorderState = "idle" | "requesting" | "recording" | "paused" | "stopped" | "denied" | "unsupported";

export interface Recording {
  blob: Blob;
  mimeType: string;
  extension: string;
  /** Measured wall-clock seconds of recording (excluding pauses). */
  duration: number;
  url: string;
}

export interface UseRecorder {
  state: RecorderState;
  elapsed: number;
  analyser: AnalyserNode | null;
  recording: Recording | null;
  error: string | null;
  canPause: boolean;
  start: () => Promise<void>;
  pause: () => void;
  resume: () => void;
  stop: () => void;
  reset: () => void;
}

export function isRecordingSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof MediaRecorder !== "undefined" &&
    typeof navigator !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia)
  );
}

/** Real MediaRecorder-based capture with an AnalyserNode for the live level meter. */
export function useRecorder(): UseRecorder {
  const [state, setState] = useState<RecorderState>("idle");
  const [elapsed, setElapsed] = useState(0);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);
  const [recording, setRecording] = useState<Recording | null>(null);
  const [error, setError] = useState<string | null>(null);

  const streamRef = useRef<MediaStream | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const startedAtRef = useRef(0);
  const accumulatedRef = useRef(0);
  const timerRef = useRef<number | null>(null);
  const mimeRef = useRef<{ mimeType: string | undefined; extension: string }>({ mimeType: undefined, extension: "webm" });
  const urlRef = useRef<string | null>(null);

  useEffect(() => {
    if (!isRecordingSupported()) setState("unsupported");
  }, []);

  const clearTimer = useCallback(() => {
    if (timerRef.current != null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const currentElapsed = useCallback(
    () => accumulatedRef.current + (startedAtRef.current ? (performance.now() - startedAtRef.current) / 1000 : 0),
    [],
  );

  const startTimer = useCallback(() => {
    clearTimer();
    timerRef.current = window.setInterval(() => setElapsed(currentElapsed()), 200);
  }, [clearTimer, currentElapsed]);

  const teardownStream = useCallback(() => {
    clearTimer();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    void ctxRef.current?.close().catch(() => undefined);
    ctxRef.current = null;
    setAnalyser(null);
  }, [clearTimer]);

  const reset = useCallback(() => {
    teardownStream();
    recorderRef.current = null;
    chunksRef.current = [];
    accumulatedRef.current = 0;
    startedAtRef.current = 0;
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = null;
    setRecording(null);
    setElapsed(0);
    setError(null);
    setState(isRecordingSupported() ? "idle" : "unsupported");
  }, [teardownStream]);

  const start = useCallback(async () => {
    if (!isRecordingSupported()) {
      setState("unsupported");
      return;
    }
    setError(null);
    setState("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
      streamRef.current = stream;

      const Ctor = getAudioContextCtor();
      if (Ctor) {
        const ctx = new Ctor();
        const source = ctx.createMediaStreamSource(stream);
        const node = ctx.createAnalyser();
        node.fftSize = 256;
        node.smoothingTimeConstant = 0.6;
        source.connect(node);
        ctxRef.current = ctx;
        setAnalyser(node);
      }

      const mime = pickRecorderMime();
      mimeRef.current = mime;
      const recorder = mime.mimeType ? new MediaRecorder(stream, { mimeType: mime.mimeType }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (ev) => {
        if (ev.data && ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      recorder.onstop = () => {
        const type = recorder.mimeType || mime.mimeType || "audio/webm";
        const blob = new Blob(chunksRef.current, { type });
        if (urlRef.current) URL.revokeObjectURL(urlRef.current);
        const url = URL.createObjectURL(blob);
        urlRef.current = url;
        setRecording({
          blob,
          mimeType: type,
          extension: mime.extension,
          duration: currentElapsed(),
          url,
        });
        startedAtRef.current = 0;
        setState("stopped");
        teardownStream();
      };
      recorder.onerror = () => {
        setError("Recording stopped unexpectedly. Please try again.");
        setState("idle");
        teardownStream();
      };
      recorderRef.current = recorder;
      recorder.start(250);
      accumulatedRef.current = 0;
      startedAtRef.current = performance.now();
      setElapsed(0);
      startTimer();
      setState("recording");
    } catch (e) {
      teardownStream();
      const name = e instanceof Error ? e.name : "";
      if (name === "NotAllowedError" || name === "SecurityError") {
        setState("denied");
        setError("Microphone access was blocked. Allow it in your browser settings, or upload a recording instead.");
      } else if (name === "NotFoundError" || name === "OverconstrainedError") {
        setState("idle");
        setError("No microphone was found. Connect one, or upload a recording instead.");
      } else {
        setState("idle");
        setError("We could not start recording. Please try again or upload a recording.");
      }
    }
  }, [teardownStream, startTimer, currentElapsed]);

  const canPause = typeof MediaRecorder !== "undefined" && typeof MediaRecorder.prototype.pause === "function";

  const pause = useCallback(() => {
    const r = recorderRef.current;
    if (!r || r.state !== "recording" || !canPause) return;
    r.pause();
    accumulatedRef.current = currentElapsed();
    startedAtRef.current = 0;
    clearTimer();
    setElapsed(accumulatedRef.current);
    setState("paused");
  }, [canPause, clearTimer, currentElapsed]);

  const resume = useCallback(() => {
    const r = recorderRef.current;
    if (!r || r.state !== "paused") return;
    r.resume();
    startedAtRef.current = performance.now();
    startTimer();
    setState("recording");
  }, [startTimer]);

  const stop = useCallback(() => {
    const r = recorderRef.current;
    if (!r || r.state === "inactive") return;
    if (r.state === "paused") {
      // Keep accumulated time; nothing more to add.
    } else {
      accumulatedRef.current = currentElapsed();
      startedAtRef.current = 0;
    }
    clearTimer();
    setElapsed(accumulatedRef.current);
    r.stop();
  }, [clearTimer, currentElapsed]);

  useEffect(() => {
    return () => {
      if (timerRef.current != null) window.clearInterval(timerRef.current);
      streamRef.current?.getTracks().forEach((t) => t.stop());
      void ctxRef.current?.close().catch(() => undefined);
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  return { state, elapsed, analyser, recording, error, canPause, start, pause, resume, stop, reset };
}
