/** Browser audio helpers shared by the recorder, uploader, player and conversation mode. */

export const ACCEPTED_EXTENSIONS = ["wav", "mp3", "m4a", "flac", "ogg", "webm"] as const;
export const ACCEPT_ATTR = ACCEPTED_EXTENSIONS.map((e) => `.${e}`).join(",") + ",audio/*";

export function fileExtension(name: string): string {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
}

export function isAcceptedExtension(name: string): boolean {
  return (ACCEPTED_EXTENSIONS as readonly string[]).includes(fileExtension(name));
}

type AudioContextCtor = typeof AudioContext;

export function getAudioContextCtor(): AudioContextCtor | null {
  if (typeof window === "undefined") return null;
  const w = window as Window & { webkitAudioContext?: AudioContextCtor };
  return window.AudioContext ?? w.webkitAudioContext ?? null;
}

export interface DecodedInfo {
  duration: number;
  sampleRate: number;
  channels: number;
  /** Normalised peak magnitudes (0–1) for a static waveform. */
  peaks: Float32Array;
}

/** Compute `buckets` normalised peaks from an AudioBuffer (mono mix). */
export function computePeaks(buffer: AudioBuffer, buckets = 160): Float32Array {
  const channels = buffer.numberOfChannels;
  const length = buffer.length;
  const out = new Float32Array(buckets);
  if (length === 0) return out;
  const step = Math.max(1, Math.floor(length / buckets));
  const data: Float32Array[] = [];
  for (let c = 0; c < channels; c++) data.push(buffer.getChannelData(c));
  let max = 0;
  for (let b = 0; b < buckets; b++) {
    const start = b * step;
    const end = Math.min(length, start + step);
    let peak = 0;
    for (let i = start; i < end; i += 4) {
      let v = 0;
      for (let c = 0; c < channels; c++) v += Math.abs(data[c]?.[i] ?? 0);
      v /= channels;
      if (v > peak) peak = v;
    }
    out[b] = peak;
    if (peak > max) max = peak;
  }
  if (max > 0) for (let b = 0; b < buckets; b++) out[b] = (out[b] ?? 0) / max;
  return out;
}

/** Decode a Blob with the Web Audio API. Throws when the browser cannot decode the format. */
export async function decodeAudio(blob: Blob, buckets = 160): Promise<DecodedInfo> {
  const Ctor = getAudioContextCtor();
  if (!Ctor) throw new Error("Web Audio is not supported in this browser.");
  const ctx = new Ctor();
  try {
    const bytes = await blob.arrayBuffer();
    const buffer = await ctx.decodeAudioData(bytes.slice(0));
    return {
      duration: buffer.duration,
      sampleRate: buffer.sampleRate,
      channels: buffer.numberOfChannels,
      peaks: computePeaks(buffer, buckets),
    };
  } finally {
    void ctx.close().catch(() => undefined);
  }
}

/** Pick the best supported MediaRecorder MIME type. */
export function pickRecorderMime(): { mimeType: string | undefined; extension: string } {
  if (typeof MediaRecorder === "undefined") return { mimeType: undefined, extension: "webm" };
  const candidates: [string, string][] = [
    ["audio/webm;codecs=opus", "webm"],
    ["audio/webm", "webm"],
    ["audio/mp4", "m4a"],
    ["audio/ogg;codecs=opus", "ogg"],
  ];
  for (const [mime, ext] of candidates) {
    try {
      if (MediaRecorder.isTypeSupported(mime)) return { mimeType: mime, extension: ext };
    } catch {
      /* ignore */
    }
  }
  return { mimeType: undefined, extension: "webm" };
}

export function extensionForMime(mime: string): string {
  if (mime.includes("mp4") || mime.includes("aac")) return "m4a";
  if (mime.includes("ogg")) return "ogg";
  if (mime.includes("wav")) return "wav";
  if (mime.includes("mpeg")) return "mp3";
  if (mime.includes("flac")) return "flac";
  return "webm";
}

// --- Conversation-mode PCM helpers -----------------------------------------------------------

/** Linear-interpolation downsample of Float32 PCM to a target rate. */
export function downsample(input: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (inputRate === outputRate) return input;
  const ratio = inputRate / outputRate;
  const outLength = Math.max(0, Math.floor(input.length / ratio));
  const out = new Float32Array(outLength);
  for (let i = 0; i < outLength; i++) {
    const pos = i * ratio;
    const i0 = Math.floor(pos);
    const i1 = Math.min(input.length - 1, i0 + 1);
    const frac = pos - i0;
    const a = input[i0] ?? 0;
    const b = input[i1] ?? a;
    out[i] = a + (b - a) * frac;
  }
  return out;
}

export function floatToPcm16(input: Float32Array): ArrayBuffer {
  const buf = new ArrayBuffer(input.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < input.length; i++) {
    const s = Math.max(-1, Math.min(1, input[i] ?? 0));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buf;
}

export function pcm16ToFloat(buf: ArrayBuffer): Float32Array {
  const view = new DataView(buf);
  const n = Math.floor(buf.byteLength / 2);
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) out[i] = view.getInt16(i * 2, true) / 0x8000;
  return out;
}

/** RMS level 0–1 of a Float32 block. */
export function rms(input: Float32Array): number {
  if (input.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < input.length; i++) {
    const v = input[i] ?? 0;
    sum += v * v;
  }
  return Math.sqrt(sum / input.length);
}

/** Split analyser time-domain data into five band-ish levels for the brand bars. */
export function levelsFromAnalyser(analyser: AnalyserNode, scratch: Uint8Array<ArrayBuffer>): number[] {
  analyser.getByteFrequencyData(scratch);
  const bands = 5;
  const usable = Math.floor(scratch.length * 0.6);
  const per = Math.max(1, Math.floor(usable / bands));
  const out: number[] = [];
  for (let b = 0; b < bands; b++) {
    let sum = 0;
    for (let i = b * per; i < (b + 1) * per; i++) sum += scratch[i] ?? 0;
    out.push(Math.min(1, sum / per / 180));
  }
  // Symmetric arrangement: centre gets the loudest band.
  const sorted = [...out].sort((a, b) => a - b);
  return [sorted[0] ?? 0, sorted[2] ?? 0, sorted[4] ?? 0, sorted[3] ?? 0, sorted[1] ?? 0];
}
