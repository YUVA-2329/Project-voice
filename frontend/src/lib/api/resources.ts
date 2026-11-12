import { api, upload, type UploadProgress } from "./client";
import type {
  ApiKey,
  ApiKeyCreated,
  AuditEntry,
  AuthResponse,
  ConversationEngine,
  CreateVoiceInput,
  Generation,
  GenerationCreate,
  GenerationListParams,
  Hardware,
  Health,
  Job,
  LanguageCapability,
  LoginBody,
  Metrics,
  ModelInfo,
  Paginated,
  RegisterBody,
  UpdateMeBody,
  UpdateVoiceBody,
  User,
  Voice,
} from "./types";

// Auth --------------------------------------------------------------------------------------
export const auth = {
  register: (body: RegisterBody) =>
    api<AuthResponse>("/auth/register", { method: "POST", body, skipAuthRefresh: true, skipAuthRedirect: true }),
  login: (body: LoginBody) =>
    api<AuthResponse>("/auth/login", { method: "POST", body, skipAuthRefresh: true, skipAuthRedirect: true }),
  logout: () => api<void>("/auth/logout", { method: "POST", skipAuthRefresh: true, skipAuthRedirect: true }),
  refresh: () => api<AuthResponse>("/auth/refresh", { method: "POST", skipAuthRefresh: true, skipAuthRedirect: true }),
};

// Users -------------------------------------------------------------------------------------
export const users = {
  me: (opts: { skipAuthRedirect?: boolean } = {}) => api<User>("/users/me", opts),
  update: (body: UpdateMeBody) => api<User>("/users/me", { method: "PATCH", body }),
  remove: (password: string) => api<void>("/users/me", { method: "DELETE", body: { password } }),
};

// Voices ------------------------------------------------------------------------------------
export const voices = {
  list: (params: { limit?: number; offset?: number } = {}) =>
    api<Paginated<Voice>>("/voices", { query: { limit: params.limit ?? 100, offset: params.offset ?? 0 } }),
  get: (id: string) => api<Voice>(`/voices/${id}`),
  create: (input: CreateVoiceInput, onProgress?: (p: UploadProgress) => void, signal?: AbortSignal) => {
    const form = new FormData();
    form.append("file", input.file, input.fileName);
    form.append("name", input.name);
    if (input.language_hint) form.append("language_hint", input.language_hint);
    form.append("consent_confirmed", "true");
    form.append("consent_text_version", input.consent_text_version);
    if (input.transcript) form.append("transcript", input.transcript);
    return upload<Voice>("/voices", form, {
      onProgress,
      signal,
      headers: { "Idempotency-Key": crypto.randomUUID() },
    });
  },
  update: (id: string, body: UpdateVoiceBody) => api<Voice>(`/voices/${id}`, { method: "PATCH", body }),
  remove: (id: string) => api<void>(`/voices/${id}`, { method: "DELETE" }),
  preview: (id: string, text?: string) =>
    api<Generation>(`/voices/${id}/preview`, { method: "POST", body: text ? { text } : {} }),
  revokeConsent: (id: string) => api<Voice>(`/voices/${id}/consent/revoke`, { method: "POST" }),
  grantConsent: (id: string, consent_text_version: string) =>
    api<Voice>(`/voices/${id}/consent`, { method: "POST", body: { consent_confirmed: true, consent_text_version } }),
  referenceAudioUrl: (id: string) => `/api/v1/voices/${id}/reference-audio`,
};

// Generations -------------------------------------------------------------------------------
export const generations = {
  list: (params: GenerationListParams = {}) =>
    api<Paginated<Generation>>("/generations", {
      query: {
        voice_id: params.voice_id,
        status: params.status,
        limit: params.limit ?? 20,
        offset: params.offset ?? 0,
      },
    }),
  get: (id: string) => api<Generation>(`/generations/${id}`),
  create: (body: GenerationCreate) =>
    api<Generation>("/generations", {
      method: "POST",
      body,
      headers: { "Idempotency-Key": crypto.randomUUID() },
    }),
  remove: (id: string) => api<void>(`/generations/${id}`, { method: "DELETE" }),
  audioUrl: (id: string, download = false) =>
    `/api/v1/generations/${id}/audio${download ? "?download=1" : ""}`,
  signedUrl: (id: string) => api<{ url: string; expires_at: string }>(`/generations/${id}/audio-url`),
};

// Jobs --------------------------------------------------------------------------------------
export const jobs = {
  get: (id: string) => api<Job>(`/jobs/${id}`),
};

// System ------------------------------------------------------------------------------------
export const system = {
  health: () => api<Health>("/system/health", { skipAuthRedirect: true }),
  models: () => api<ModelInfo[]>("/system/models"),
  hardware: () => api<Hardware>("/system/hardware"),
  metrics: () => api<Metrics>("/system/metrics"),
  languages: () => api<LanguageCapability[]>("/system/languages"),
};

// API keys / audit --------------------------------------------------------------------------
export const apiKeys = {
  list: () => api<ApiKey[]>("/api-keys"),
  create: (name: string) => api<ApiKeyCreated>("/api-keys", { method: "POST", body: { name } }),
  revoke: (id: string) => api<void>(`/api-keys/${id}`, { method: "DELETE" }),
};

export const audit = {
  list: (params: { limit?: number; offset?: number } = {}) =>
    api<Paginated<AuditEntry>>("/audit", { query: { limit: params.limit ?? 20, offset: params.offset ?? 0 } }),
};

// Conversation ------------------------------------------------------------------------------
export const conversation = {
  engines: () => api<ConversationEngine[]>("/conversation/engines"),
};

export function conversationWsUrl(voiceId: string, engine: string, language?: string): string {
  const base = process.env.NEXT_PUBLIC_WS_BASE;
  const params = new URLSearchParams({ voice_id: voiceId, engine });
  if (language && language !== "auto") params.set("language", language);
  const path = `/api/v1/conversation/ws?${params.toString()}`;
  if (base) return `${base.replace(/\/$/, "")}${path}`;
  if (typeof window === "undefined") return path;
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}${path}`;
}
