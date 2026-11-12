"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { conversationWsUrl } from "@/lib/api/resources";
import type { ConversationServerMessage, ConversationState } from "@/lib/api/types";
import { downsample, floatToPcm16, getAudioContextCtor, pcm16ToFloat, rms } from "@/lib/audio";

export type SocketStatus = "disconnected" | "connecting" | "connected" | "reconnecting" | "closed";

export interface Turn {
  id: number;
  transcript: string;
  response: string;
}

export interface ConversationHandle {
  socket: SocketStatus;
  state: ConversationState;
  turns: Turn[];
  live: { transcript: string; response: string };
  error: { code: string; message: string } | null;
  micAnalyser: AnalyserNode | null;
  outAnalyser: AnalyserNode | null;
  reconnectAttempt: number;
  start: () => Promise<void>;
  stop: () => void;
  endTurn: () => void;
  interrupt: () => void;
}

const TARGET_RATE = 16_000;
const SEND_SAMPLES = Math.round(TARGET_RATE * 0.1); // 100 ms frames
const BARGE_IN_RMS = 0.06;
const BARGE_IN_BLOCKS = 4;
const MAX_RECONNECTS = 6;
const FATAL_CLOSE_CODES = new Set([1000, 4001, 4004]);

const WORKLET_SOURCE = `
class PVCapture extends AudioWorkletProcessor {
  constructor() { super(); this.buf = []; this.len = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) {
      this.buf.push(ch.slice(0));
      this.len += ch.length;
      if (this.len >= 2048) {
        const out = new Float32Array(this.len);
        let o = 0;
        for (const b of this.buf) { out.set(b, o); o += b.length; }
        this.port.postMessage(out, [out.buffer]);
        this.buf = []; this.len = 0;
      }
    }
    return true;
  }
}
registerProcessor("pv-capture", PVCapture);
`;

function closeMessage(code: number): { code: string; message: string } {
  switch (code) {
    case 4001:
      return { code: "unauthenticated", message: "Your session has expired. Sign in again." };
    case 4004:
      return { code: "voice_unavailable", message: "That voice is not ready for conversation." };
    case 4008:
      return { code: "turn_timeout", message: "The turn timed out. Reconnecting." };
    case 1011:
      return { code: "engine_unavailable", message: "The conversation engine is not available on this server." };
    default:
      return { code: `ws_close_${code}`, message: "The connection closed." };
  }
}

export function useConversation(opts: { voiceId: string | null; engine: string; language?: string }): ConversationHandle {
  const [socket, setSocket] = useState<SocketStatus>("disconnected");
  const [state, setState] = useState<ConversationState>("idle");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [live, setLive] = useState({ transcript: "", response: "" });
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [micAnalyser, setMicAnalyser] = useState<AnalyserNode | null>(null);
  const [outAnalyser, setOutAnalyser] = useState<AnalyserNode | null>(null);
  const [reconnectAttempt, setReconnectAttempt] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const captureNodeRef = useRef<AudioNode | null>(null);
  const outGainRef = useRef<GainNode | null>(null);
  const pendingRef = useRef<Float32Array[]>([]);
  const pendingLenRef = useRef(0);
  const playbackRateRef = useRef(24_000);
  const nextPlayAtRef = useRef(0);
  const sourcesRef = useRef<Set<AudioBufferSourceNode>>(new Set());
  const stateRef = useRef<ConversationState>("idle");
  const loudBlocksRef = useRef(0);
  const userStoppedRef = useRef(false);
  const reconnectTimerRef = useRef<number | null>(null);
  const attemptsRef = useRef(0);
  const turnIdRef = useRef(0);
  const liveRef = useRef({ transcript: "", response: "" });
  const optsRef = useRef(opts);
  optsRef.current = opts;

  const setConvState = (s: ConversationState) => {
    stateRef.current = s;
    setState(s);
  };

  const stopPlayback = useCallback(() => {
    for (const src of sourcesRef.current) {
      try {
        src.stop();
      } catch {
        /* already stopped */
      }
    }
    sourcesRef.current.clear();
    nextPlayAtRef.current = 0;
  }, []);

  const sendJson = useCallback((msg: object) => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
  }, []);

  const interrupt = useCallback(() => {
    stopPlayback();
    sendJson({ type: "interrupt" });
    setConvState("listening");
  }, [stopPlayback, sendJson]);

  const playFrame = useCallback((buf: ArrayBuffer) => {
    const ctx = ctxRef.current;
    const gain = outGainRef.current;
    if (!ctx || !gain) return;
    const floats = pcm16ToFloat(buf);
    if (floats.length === 0) return;
    const rate = playbackRateRef.current;
    const audio = ctx.createBuffer(1, floats.length, rate);
    audio.copyToChannel(floats as Float32Array<ArrayBuffer>, 0);
    const src = ctx.createBufferSource();
    src.buffer = audio;
    src.connect(gain);
    const now = ctx.currentTime;
    const startAt = Math.max(now + 0.02, nextPlayAtRef.current);
    src.start(startAt);
    nextPlayAtRef.current = startAt + audio.duration;
    sourcesRef.current.add(src);
    src.onended = () => sourcesRef.current.delete(src);
  }, []);

  const handleMessage = useCallback(
    (msg: ConversationServerMessage) => {
      switch (msg.type) {
        case "state":
          setConvState(msg.state);
          if (msg.state === "listening") {
            // A new turn begins once the previous one was spoken.
            if (liveRef.current.transcript || liveRef.current.response) {
              const t = { id: ++turnIdRef.current, ...liveRef.current };
              setTurns((prev) => [...prev, t]);
              liveRef.current = { transcript: "", response: "" };
              setLive(liveRef.current);
            }
          }
          break;
        case "transcript":
          liveRef.current = { ...liveRef.current, transcript: msg.text };
          setLive(liveRef.current);
          break;
        case "response":
          liveRef.current = { ...liveRef.current, response: msg.text };
          setLive(liveRef.current);
          break;
        case "audio_start":
          playbackRateRef.current = msg.sample_rate || 24_000;
          nextPlayAtRef.current = 0;
          break;
        case "audio_end":
          break;
        case "error":
          setError({ code: msg.code, message: msg.message ?? "Something went wrong." });
          break;
      }
    },
    [],
  );

  const flushPending = useCallback(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      pendingRef.current = [];
      pendingLenRef.current = 0;
      return;
    }
    while (pendingLenRef.current >= SEND_SAMPLES) {
      const out = new Float32Array(SEND_SAMPLES);
      let filled = 0;
      while (filled < SEND_SAMPLES && pendingRef.current.length > 0) {
        const head = pendingRef.current[0]!;
        const take = Math.min(head.length, SEND_SAMPLES - filled);
        out.set(head.subarray(0, take), filled);
        filled += take;
        if (take === head.length) pendingRef.current.shift();
        else pendingRef.current[0] = head.subarray(take);
      }
      pendingLenRef.current -= SEND_SAMPLES;
      ws.send(floatToPcm16(out));
    }
  }, []);

  const onCapture = useCallback(
    (block: Float32Array, inputRate: number) => {
      // Barge-in: sustained speech while the assistant is speaking interrupts it.
      if (stateRef.current === "speaking") {
        if (rms(block) > BARGE_IN_RMS) {
          loudBlocksRef.current += 1;
          if (loudBlocksRef.current >= BARGE_IN_BLOCKS) {
            loudBlocksRef.current = 0;
            interrupt();
          }
        } else {
          loudBlocksRef.current = 0;
        }
      } else {
        loudBlocksRef.current = 0;
      }
      const ds = downsample(block, inputRate, TARGET_RATE);
      pendingRef.current.push(ds);
      pendingLenRef.current += ds.length;
      flushPending();
    },
    [flushPending, interrupt],
  );

  const connect = useCallback(() => {
    const { voiceId, engine, language } = optsRef.current;
    if (!voiceId) return;
    if (reconnectTimerRef.current != null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    setSocket(attemptsRef.current > 0 ? "reconnecting" : "connecting");
    const ws = new WebSocket(conversationWsUrl(voiceId, engine, language));
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      attemptsRef.current = 0;
      setReconnectAttempt(0);
      setSocket("connected");
      setError(null);
      ws.send(JSON.stringify({ type: "start" }));
      setConvState("listening");
    };
    ws.onmessage = (ev) => {
      if (ev.data instanceof ArrayBuffer) {
        playFrame(ev.data);
        return;
      }
      try {
        handleMessage(JSON.parse(String(ev.data)) as ConversationServerMessage);
      } catch {
        /* ignore malformed frames */
      }
    };
    ws.onerror = () => {
      /* onclose follows with the code */
    };
    ws.onclose = (ev) => {
      if (wsRef.current !== ws) return;
      wsRef.current = null;
      stopPlayback();
      setConvState("idle");
      if (userStoppedRef.current || FATAL_CLOSE_CODES.has(ev.code)) {
        if (!userStoppedRef.current) setError(closeMessage(ev.code));
        setSocket("closed");
        return;
      }
      if (attemptsRef.current >= MAX_RECONNECTS) {
        setError({ code: "reconnect_failed", message: "Could not reconnect. Check your connection and start again." });
        setSocket("closed");
        return;
      }
      if (ev.code === 4008 || ev.code === 1011) setError(closeMessage(ev.code));
      attemptsRef.current += 1;
      setReconnectAttempt(attemptsRef.current);
      setSocket("reconnecting");
      const delay = Math.min(15_000, 1000 * 2 ** (attemptsRef.current - 1));
      reconnectTimerRef.current = window.setTimeout(connect, delay);
    };
  }, [handleMessage, playFrame, stopPlayback]);

  const teardownAudio = useCallback(() => {
    captureNodeRef.current?.disconnect();
    captureNodeRef.current = null;
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    stopPlayback();
    void ctxRef.current?.close().catch(() => undefined);
    ctxRef.current = null;
    outGainRef.current = null;
    setMicAnalyser(null);
    setOutAnalyser(null);
    pendingRef.current = [];
    pendingLenRef.current = 0;
  }, [stopPlayback]);

  const start = useCallback(async () => {
    if (!optsRef.current.voiceId) return;
    userStoppedRef.current = false;
    attemptsRef.current = 0;
    setError(null);
    setTurns([]);
    liveRef.current = { transcript: "", response: "" };
    setLive(liveRef.current);

    const Ctor = getAudioContextCtor();
    if (!Ctor || !navigator.mediaDevices?.getUserMedia) {
      setError({ code: "unsupported", message: "This browser does not support live audio." });
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
    } catch (e) {
      const name = e instanceof Error ? e.name : "";
      setError(
        name === "NotAllowedError"
          ? { code: "microphone_denied", message: "Microphone access was blocked. Allow it in your browser settings." }
          : { code: "microphone_unavailable", message: "No microphone could be opened." },
      );
      return;
    }
    streamRef.current = stream;
    const ctx = new Ctor();
    ctxRef.current = ctx;
    if (ctx.state === "suspended") await ctx.resume().catch(() => undefined);

    // Output chain: sources → gain → analyser → speakers.
    const gain = ctx.createGain();
    const outA = ctx.createAnalyser();
    outA.fftSize = 256;
    gain.connect(outA);
    outA.connect(ctx.destination);
    outGainRef.current = gain;
    setOutAnalyser(outA);

    // Input chain: mic → analyser (meter) and → capture node (PCM frames).
    const source = ctx.createMediaStreamSource(stream);
    const micA = ctx.createAnalyser();
    micA.fftSize = 256;
    source.connect(micA);
    setMicAnalyser(micA);

    let captureNode: AudioNode | null = null;
    if (ctx.audioWorklet) {
      try {
        const url = URL.createObjectURL(new Blob([WORKLET_SOURCE], { type: "application/javascript" }));
        await ctx.audioWorklet.addModule(url);
        URL.revokeObjectURL(url);
        const node = new AudioWorkletNode(ctx, "pv-capture", { numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1 });
        node.port.onmessage = (ev: MessageEvent<Float32Array>) => onCapture(ev.data, ctx.sampleRate);
        source.connect(node);
        captureNode = node;
      } catch {
        captureNode = null;
      }
    }
    if (!captureNode) {
      // Fallback: ScriptProcessor (deprecated but widely available).
      const sp = ctx.createScriptProcessor(4096, 1, 1);
      sp.onaudioprocess = (ev) => onCapture(ev.inputBuffer.getChannelData(0).slice(0), ctx.sampleRate);
      source.connect(sp);
      const mute = ctx.createGain();
      mute.gain.value = 0;
      sp.connect(mute);
      mute.connect(ctx.destination);
      captureNode = sp;
    }
    captureNodeRef.current = captureNode;

    connect();
  }, [connect, onCapture]);

  const stop = useCallback(() => {
    userStoppedRef.current = true;
    if (reconnectTimerRef.current != null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
    const ws = wsRef.current;
    wsRef.current = null;
    if (ws && ws.readyState === WebSocket.OPEN) {
      try {
        ws.send(JSON.stringify({ type: "stop" }));
      } catch {
        /* ignore */
      }
      ws.close(1000, "client stop");
    } else {
      ws?.close();
    }
    teardownAudio();
    setConvState("idle");
    setSocket("disconnected");
    setReconnectAttempt(0);
  }, [teardownAudio]);

  const endTurn = useCallback(() => {
    flushPending();
    sendJson({ type: "stop" });
  }, [flushPending, sendJson]);

  useEffect(() => () => stop(), [stop]);

  return { socket, state, turns, live, error, micAnalyser, outAnalyser, reconnectAttempt, start, stop, endTurn, interrupt };
}
