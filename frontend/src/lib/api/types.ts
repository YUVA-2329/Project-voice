/**
 * Types mirroring docs/API_DOCUMENTATION.md (API v1) plus the contract clarifications in
 * backend/README.md. Keep this file in lock-step with the backend schemas.
 */

export type LanguageCode = "en" | "te" | "hi" | "kn" | "ta" | "ml" | "zh";
export type LanguageHint = "auto" | LanguageCode;
export type OutputFormat = "wav" | "mp3" | "flac";
export type Quality = "fast" | "balanced" | "high";
export type Theme = "system" | "light" | "dark";
export type Mode = "simple" | "advanced";
export type Device = "cpu" | "cuda";

export interface Paginated<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiErrorEnvelope {
  error: {
    code: string;
    message?: string;
    details?: Record<string, unknown> & {
      fields?: { loc: (string | number)[]; msg: string; type: string }[];
      supported_engines?: string[];
    };
  };
}

// ---------------------------------------------------------------------------------------------
// Users / auth

export interface UserPreferences {
  default_language: LanguageHint;
  default_engine: string | null;
  output_format: OutputFormat;
  speed: number;
  theme: Theme;
  mode: Mode;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  created_at: string;
  preferences: UserPreferences;
}

export interface AuthResponse {
  user: User;
}

export interface RegisterBody {
  email: string;
  password: string;
  display_name: string;
}

export interface LoginBody {
  email: string;
  password: string;
}

export interface UpdateMeBody {
  display_name?: string;
  preferences?: Partial<UserPreferences>;
}

// ---------------------------------------------------------------------------------------------
// Voices

export type VoiceStatus = "processing" | "ready" | "failed" | "consent_revoked";

export interface ResourceError {
  code: string;
  message: string;
}

export interface VoiceReference {
  original_format: string;
  duration_seconds: number;
  sample_rate: number;
  channels: number;
  /** null while the voice is still processing (comes from VAD in the worker). */
  speech_seconds: number | null;
  size_bytes: number;
}

export interface VoiceQuality {
  snr_db: number | null;
  clipping_ratio: number;
  peak_dbfs: number;
  rms_dbfs: number;
  leading_silence_s: number;
  trailing_silence_s: number;
  warnings: string[];
}

export interface Voice {
  id: string;
  name: string;
  status: VoiceStatus;
  error: ResourceError | null;
  language: LanguageCode | null;
  detected_language: LanguageCode | null;
  engine_id: string | null;
  transcript: string | null;
  transcript_source: "auto" | "user" | null;
  reference: VoiceReference | null;
  quality: VoiceQuality | null;
  consent: { given_at: string; text_version: string; revoked_at: string | null };
  preview_generation_id: string | null;
  job_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateVoiceInput {
  file: File | Blob;
  fileName: string;
  name: string;
  language_hint?: LanguageHint;
  consent_confirmed: true;
  consent_text_version: string;
  transcript?: string;
}

export interface UpdateVoiceBody {
  name?: string;
  transcript?: string;
  language?: LanguageCode;
}

// ---------------------------------------------------------------------------------------------
// Generations

export type GenerationStatus = "queued" | "processing" | "completed" | "failed" | "cancelled";

export interface Progress {
  stage: string;
  current: number;
  total: number;
}

export interface GenerationOutput {
  format: string;
  duration_seconds: number;
  sample_rate: number;
  size_bytes: number;
}

export interface GenerationMetrics {
  inference_seconds: number;
  total_seconds: number;
  real_time_factor: number;
  chunks: number;
  device: Device;
  peak_dbfs: number;
  clipping_ratio: number;
}

export interface Generation {
  id: string;
  voice_id: string | null;
  voice_name: string;
  text: string;
  /** May be null when "auto" was requested and the voice has no known language yet. */
  language: LanguageCode | null;
  requested_language: LanguageHint;
  engine_id: string | null;
  status: GenerationStatus;
  progress: Progress | null;
  error: ResourceError | null;
  output: GenerationOutput | null;
  metrics: GenerationMetrics | null;
  job_id: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface GenerationCreate {
  voice_id: string;
  text: string;
  language?: LanguageHint;
  engine_id?: string;
  speed?: number;
  output_format?: OutputFormat;
  quality?: Quality;
}

export interface GenerationListParams {
  voice_id?: string;
  status?: GenerationStatus;
  limit?: number;
  offset?: number;
}

export interface AudioUrl {
  url: string;
  expires_at: string;
}

// ---------------------------------------------------------------------------------------------
// Jobs

export type JobKind = "voice_create" | "generation" | "preview" | "cleanup" | "conversation_turn";
export type JobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";

export interface Job {
  id: string;
  kind: JobKind;
  status: JobStatus;
  progress: Progress | null;
  error: ResourceError | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  resource_type: string;
  resource_id: string;
}

// ---------------------------------------------------------------------------------------------
// System

export interface Health {
  status: "ok" | "degraded";
  version: string;
  checks: {
    database: unknown;
    redis: unknown;
    storage: unknown;
    worker: { status: string; last_heartbeat: string | null };
  };
}

export interface ModelInfo {
  id: string;
  name: string;
  version: string;
  licence: string;
  weight_licence: string;
  available: boolean;
  unavailable_reason: string | null;
  loaded: boolean;
  device: Device | null;
  tts_languages: LanguageCode[];
  cloning_languages: LanguageCode[];
  cross_lingual: boolean;
  requires_reference_text: boolean;
  sample_rate: number;
  resource: { ram_mb: number; vram_mb: number | null };
  stats: { loads: number; inferences: number; avg_rtf: number | null; last_error: string | null };
}

export interface Hardware {
  device: Device;
  cuda_available: boolean;
  gpu: { name: string; vram_total_mb: number; vram_used_mb: number } | null;
  cpu_cores: number;
  ram_total_mb: number;
  ram_used_mb: number;
  disk_free_mb: number;
  torch_version: string | null;
  onnxruntime_version: string | null;
}

export interface Metrics {
  queues: { voice: number; generation: number };
  workers: { name: string; last_heartbeat: string; loaded_engine: string | null }[];
  generations_24h: { total: number; completed: number; failed: number; avg_rtf: number | null };
  voices_total: number;
}

export type Verified = "verified" | "unverified" | "unavailable";

export interface LanguageCapability {
  code: LanguageCode;
  name: string;
  native_name: string;
  script: string;
  engines: { engine_id: string; tts: boolean; cloning: boolean; verified: Verified; note: string }[];
}

// ---------------------------------------------------------------------------------------------
// API keys / audit

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

export interface ApiKeyCreated {
  api_key: ApiKey;
  secret: string;
}

export interface AuditEntry {
  id: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  ip: string | null;
  created_at: string;
  metadata: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------------------------
// Conversation

export type ConversationEngineId = "mirror" | "llm";

export interface ConversationEngine {
  id: ConversationEngineId;
  available: boolean;
  reason: string | null;
}

export type ConversationState = "idle" | "listening" | "thinking" | "speaking";

export type ConversationServerMessage =
  | { type: "state"; state: ConversationState }
  | { type: "transcript"; text: string }
  | { type: "response"; text: string }
  | { type: "audio_start"; sample_rate: number }
  | { type: "audio_end" }
  | { type: "error"; code: string; message?: string };

export type ConversationClientMessage = { type: "start" } | { type: "stop" } | { type: "interrupt" };

// ---------------------------------------------------------------------------------------------
// Static language catalogue (names shown in the UI; availability comes from /system/languages).

export const LANGUAGE_NAMES: Record<LanguageCode, { name: string; native: string }> = {
  en: { name: "English", native: "English" },
  te: { name: "Telugu", native: "తెలుగు" },
  hi: { name: "Hindi", native: "हिन्दी" },
  kn: { name: "Kannada", native: "ಕನ್ನಡ" },
  ta: { name: "Tamil", native: "தமிழ்" },
  ml: { name: "Malayalam", native: "മലയാളം" },
  zh: { name: "Chinese", native: "中文" },
};

export const LANGUAGE_ORDER: LanguageCode[] = ["te", "hi", "kn", "ta", "ml", "en", "zh"];

export const CONSENT_TEXT =
  "I confirm that this is my voice or that I have explicit permission from the voice owner to create this voice clone.";
export const CONSENT_TEXT_VERSION = "v1";
export const MAX_TEXT_CHARS = 5000;
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;
export const MIN_REFERENCE_SECONDS = 3;
export const MAX_REFERENCE_SECONDS = 120;
