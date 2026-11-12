"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { isApiError, type UploadProgress } from "./client";
import { apiKeys, audit, auth, conversation, generations, jobs, system, users, voices } from "./resources";
import type {
  ApiKeyCreated,
  CreateVoiceInput,
  Generation,
  GenerationCreate,
  GenerationListParams,
  Job,
  LoginBody,
  Paginated,
  RegisterBody,
  UpdateMeBody,
  UpdateVoiceBody,
  User,
  Voice,
} from "./types";

export const keys = {
  me: ["me"] as const,
  voices: ["voices"] as const,
  voice: (id: string) => ["voices", id] as const,
  generations: (params: GenerationListParams = {}) => ["generations", params] as const,
  generation: (id: string) => ["generations", "one", id] as const,
  job: (id: string) => ["jobs", id] as const,
  models: ["system", "models"] as const,
  hardware: ["system", "hardware"] as const,
  metrics: ["system", "metrics"] as const,
  languages: ["system", "languages"] as const,
  health: ["system", "health"] as const,
  apiKeys: ["api-keys"] as const,
  audit: ["audit"] as const,
  conversationEngines: ["conversation", "engines"] as const,
};

const noRetryOnClientError = (failureCount: number, error: unknown) => {
  if (isApiError(error) && error.status >= 400 && error.status < 500) return false;
  return failureCount < 2;
};

// Me ------------------------------------------------------------------------------------------

export function useMe(options: { enabled?: boolean; redirect?: boolean } = {}) {
  return useQuery<User>({
    queryKey: keys.me,
    queryFn: () => users.me({ skipAuthRedirect: options.redirect === false }),
    enabled: options.enabled ?? true,
    retry: noRetryOnClientError,
    staleTime: 60_000,
  });
}

export function useUpdateMe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: UpdateMeBody) => users.update(body),
    onSuccess: (user) => qc.setQueryData(keys.me, user),
  });
}

export function useDeleteMe() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (password: string) => users.remove(password),
    onSuccess: () => qc.clear(),
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: LoginBody) => auth.login(body),
    onSuccess: (res) => qc.setQueryData(keys.me, res.user),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: RegisterBody) => auth.register(body),
    onSuccess: (res) => qc.setQueryData(keys.me, res.user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => auth.logout(),
    onSettled: () => qc.clear(),
  });
}

// Voices --------------------------------------------------------------------------------------

export function useVoices(options: { enabled?: boolean } = {}) {
  return useQuery<Paginated<Voice>>({
    queryKey: keys.voices,
    queryFn: () => voices.list({ limit: 100 }),
    enabled: options.enabled ?? true,
    retry: noRetryOnClientError,
    // Poll while any voice is still processing.
    refetchInterval: (query) =>
      query.state.data?.items.some((v) => v.status === "processing") ? 2000 : false,
  });
}

export function useVoice(id: string | null | undefined, options: { poll?: boolean } = {}) {
  return useQuery<Voice>({
    queryKey: keys.voice(id ?? ""),
    queryFn: () => voices.get(id as string),
    enabled: Boolean(id),
    retry: noRetryOnClientError,
    refetchInterval: (query) =>
      options.poll !== false && query.state.data?.status === "processing" ? 2000 : false,
  });
}

export function useCreateVoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ input, onProgress, signal }: { input: CreateVoiceInput; onProgress?: (p: UploadProgress) => void; signal?: AbortSignal }) =>
      voices.create(input, onProgress, signal),
    onSuccess: (voice) => {
      qc.setQueryData(keys.voice(voice.id), voice);
      void qc.invalidateQueries({ queryKey: keys.voices });
    },
  });
}

export function useUpdateVoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: UpdateVoiceBody }) => voices.update(id, body),
    onSuccess: (voice) => {
      qc.setQueryData(keys.voice(voice.id), voice);
      qc.setQueryData<Paginated<Voice>>(keys.voices, (prev) =>
        prev ? { ...prev, items: prev.items.map((v) => (v.id === voice.id ? voice : v)) } : prev,
      );
    },
  });
}

export function useDeleteVoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => voices.remove(id),
    onSuccess: (_void, id) => {
      qc.removeQueries({ queryKey: keys.voice(id) });
      qc.setQueryData<Paginated<Voice>>(keys.voices, (prev) =>
        prev ? { ...prev, total: Math.max(0, prev.total - 1), items: prev.items.filter((v) => v.id !== id) } : prev,
      );
    },
  });
}

export function usePreviewVoice() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, text }: { id: string; text?: string }) => voices.preview(id, text),
    onSuccess: (gen) => qc.setQueryData(keys.generation(gen.id), gen),
  });
}

export function useRevokeConsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => voices.revokeConsent(id),
    onSuccess: (voice) => {
      qc.setQueryData(keys.voice(voice.id), voice);
      void qc.invalidateQueries({ queryKey: keys.voices });
    },
  });
}

export function useGrantConsent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, version }: { id: string; version: string }) => voices.grantConsent(id, version),
    onSuccess: (voice) => {
      qc.setQueryData(keys.voice(voice.id), voice);
      void qc.invalidateQueries({ queryKey: keys.voices });
    },
  });
}

// Generations ---------------------------------------------------------------------------------

export const GENERATION_PAGE = 20;

export function useGenerations(params: Omit<GenerationListParams, "limit" | "offset"> = {}) {
  return useInfiniteQuery<Paginated<Generation>>({
    queryKey: keys.generations(params),
    queryFn: ({ pageParam }) =>
      generations.list({ ...params, limit: GENERATION_PAGE, offset: (pageParam as number) ?? 0 }),
    initialPageParam: 0,
    getNextPageParam: (last) => {
      const next = last.offset + last.items.length;
      return next < last.total && last.items.length > 0 ? next : undefined;
    },
    retry: noRetryOnClientError,
  });
}

const GENERATION_ACTIVE = new Set(["queued", "processing"]);

export function useGeneration(
  id: string | null | undefined,
  options: { poll?: boolean; initialData?: Generation } = {},
) {
  const q: UseQueryOptions<Generation> = {
    queryKey: keys.generation(id ?? ""),
    queryFn: () => generations.get(id as string),
    enabled: Boolean(id),
    retry: noRetryOnClientError,
    refetchInterval: (query) =>
      options.poll !== false && GENERATION_ACTIVE.has(query.state.data?.status ?? "") ? 1500 : false,
  };
  if (options.initialData) q.initialData = options.initialData;
  return useQuery<Generation>(q);
}

export function useCreateGeneration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: GenerationCreate) => generations.create(body),
    onSuccess: (gen) => {
      qc.setQueryData(keys.generation(gen.id), gen);
      void qc.invalidateQueries({ queryKey: ["generations"], exact: false, predicate: (q) => q.queryKey[1] !== "one" });
    },
  });
}

export function useDeleteGeneration() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => generations.remove(id),
    onSuccess: (_v, id) => {
      qc.removeQueries({ queryKey: keys.generation(id) });
      void qc.invalidateQueries({ queryKey: ["generations"], predicate: (q) => q.queryKey[1] !== "one" });
    },
  });
}

// Jobs ----------------------------------------------------------------------------------------

export function useJob(id: string | null | undefined, options: { poll?: boolean } = {}) {
  return useQuery<Job>({
    queryKey: keys.job(id ?? ""),
    queryFn: () => jobs.get(id as string),
    enabled: Boolean(id),
    retry: noRetryOnClientError,
    refetchInterval: (query) => {
      const s = query.state.data?.status;
      return options.poll !== false && (s === undefined || s === "queued" || s === "running") ? 1500 : false;
    },
  });
}

// System --------------------------------------------------------------------------------------

export function useModels(options: { refetchInterval?: number | false } = {}) {
  return useQuery({
    queryKey: keys.models,
    queryFn: system.models,
    retry: noRetryOnClientError,
    staleTime: 10_000,
    refetchInterval: options.refetchInterval ?? false,
  });
}

export function useHardware(options: { refetchInterval?: number | false } = {}) {
  return useQuery({
    queryKey: keys.hardware,
    queryFn: system.hardware,
    retry: false,
    refetchInterval: options.refetchInterval ?? false,
  });
}

export function useMetrics(options: { refetchInterval?: number | false } = {}) {
  return useQuery({
    queryKey: keys.metrics,
    queryFn: system.metrics,
    retry: noRetryOnClientError,
    refetchInterval: options.refetchInterval ?? false,
  });
}

export function useLanguages() {
  return useQuery({
    queryKey: keys.languages,
    queryFn: system.languages,
    retry: false,
    staleTime: 60_000,
  });
}

export function useHealth(options: { refetchInterval?: number | false } = {}) {
  return useQuery({
    queryKey: keys.health,
    queryFn: system.health,
    retry: false,
    refetchInterval: options.refetchInterval ?? false,
  });
}

// API keys / audit ------------------------------------------------------------------------------

export function useApiKeys() {
  return useQuery({ queryKey: keys.apiKeys, queryFn: apiKeys.list, retry: noRetryOnClientError });
}

export function useCreateApiKey() {
  const qc = useQueryClient();
  return useMutation<ApiKeyCreated, unknown, string>({
    mutationFn: (name: string) => apiKeys.create(name),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.apiKeys }),
  });
}

export function useRevokeApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => apiKeys.revoke(id),
    onSuccess: () => void qc.invalidateQueries({ queryKey: keys.apiKeys }),
  });
}

export function useAudit() {
  return useInfiniteQuery({
    queryKey: keys.audit,
    queryFn: ({ pageParam }) => audit.list({ limit: 20, offset: (pageParam as number) ?? 0 }),
    initialPageParam: 0,
    getNextPageParam: (last) => {
      const next = last.offset + last.items.length;
      return next < last.total && last.items.length > 0 ? next : undefined;
    },
    retry: noRetryOnClientError,
  });
}

// Conversation ---------------------------------------------------------------------------------

export function useConversationEngines() {
  return useQuery({
    queryKey: keys.conversationEngines,
    queryFn: conversation.engines,
    retry: noRetryOnClientError,
    staleTime: 30_000,
  });
}
