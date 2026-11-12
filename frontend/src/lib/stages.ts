import type { Generation, Job, Progress } from "./api/types";

/** Voice-creation job stages → human labels (docs/INTERNAL_CONTRACTS.md). */
export const VOICE_STAGE_LABELS: Record<string, string> = {
  decode: "Decoding audio",
  analyse: "Analysing quality",
  analyze: "Analysing quality",
  vad: "Finding speech",
  trim: "Trimming silence",
  transcribe: "Transcribing",
  validate: "Validating",
  fingerprint: "Creating voice signature",
  done: "Finishing up",
};

export const VOICE_STAGE_ORDER = ["decode", "analyse", "vad", "trim", "transcribe", "validate", "fingerprint"];

/** Generation stages → human labels. */
export const GENERATION_STAGE_LABELS: Record<string, string> = {
  prepare: "Preparing",
  load_model: "Loading model",
  synthesize: "Synthesising",
  synthesise: "Synthesising",
  encode: "Encoding",
  validate: "Validating",
  done: "Finishing up",
};

function humanise(stage: string): string {
  const s = stage.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Real stage text for a generation; never fabricates percentages. */
export function generationStageText(gen: Pick<Generation, "status" | "progress">): string {
  if (gen.status === "queued") return "Queued";
  if (gen.status !== "processing") return "";
  const p = gen.progress;
  if (!p) return "Processing";
  const label = GENERATION_STAGE_LABELS[p.stage] ?? humanise(p.stage);
  if (p.total > 1 && p.current >= 0) return `${label} ${Math.min(p.current, p.total)} of ${p.total}`;
  return label;
}

export function jobStageText(job: Pick<Job, "status" | "progress"> | undefined, fallback = "Processing"): string {
  if (!job) return fallback;
  if (job.status === "queued") return "Queued";
  const p = job.progress;
  if (!p) return fallback;
  return VOICE_STAGE_LABELS[p.stage] ?? humanise(p.stage);
}

/** Fraction 0–1 of real progress, or null when unknown. */
export function progressFraction(p: Progress | null | undefined): number | null {
  if (!p || !Number.isFinite(p.total) || p.total <= 0) return null;
  return Math.max(0, Math.min(1, p.current / p.total));
}
