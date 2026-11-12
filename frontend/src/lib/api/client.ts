import type { ApiErrorEnvelope } from "./types";

export const API_BASE = "/api/v1";
const CSRF_COOKIE = "pv_csrf";
const CSRF_HEADER = "X-CSRF-Token";
const MUTATING = new Set(["POST", "PATCH", "PUT", "DELETE"]);

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown> | undefined;
  readonly retryAfter: number | undefined;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: Record<string, unknown>,
    retryAfter?: number,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.retryAfter = retryAfter;
  }

  /** Field-level messages from a `validation_error` envelope, keyed by the last path segment. */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    const fields = (this.details as ApiErrorEnvelope["error"]["details"] | undefined)?.fields;
    if (Array.isArray(fields)) {
      for (const f of fields) {
        const key = String(f.loc[f.loc.length - 1] ?? "");
        if (key && !out[key]) out[key] = f.msg;
      }
    }
    return out;
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

const DEFAULT_MESSAGES: Record<number, string> = {
  400: "That request could not be understood.",
  401: "You need to sign in to continue.",
  403: "You do not have permission to do that.",
  404: "We could not find that.",
  409: "That conflicts with the current state. Refresh and try again.",
  413: "That file is too large.",
  422: "Some of the information is not valid.",
  429: "Too many requests. Please wait a moment and try again.",
  500: "Something went wrong on our side. Please try again.",
  502: "The service is unreachable right now. Please try again shortly.",
  503: "The service is temporarily unavailable. Please try again shortly.",
};

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${encodeURIComponent(name)}=`) || row.startsWith(`${name}=`));
  if (!match) return null;
  return decodeURIComponent(match.slice(match.indexOf("=") + 1));
}

type UnauthenticatedHandler = () => void;

let onUnauthenticated: UnauthenticatedHandler = () => {
  if (typeof window === "undefined") return;
  const { pathname, search } = window.location;
  if (!pathname.startsWith("/app")) return;
  const next = encodeURIComponent(pathname + search);
  window.location.assign(`/login?next=${next}`);
};

/** Override where the client sends the user when a session cannot be recovered (tests, shells). */
export function setUnauthenticatedHandler(handler: UnauthenticatedHandler): void {
  onUnauthenticated = handler;
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | undefined | null>;
  /** Do not attempt a token refresh on 401 (used for auth routes themselves). */
  skipAuthRefresh?: boolean;
  /** Do not call the unauthenticated handler on 401 (e.g. optional "am I signed in?" probes). */
  skipAuthRedirect?: boolean;
}

export function buildQuery(query: RequestOptions["query"]): string {
  if (!query) return "";
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === "") continue;
    params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

let csrfPromise: Promise<string | null> | null = null;

/** Make sure a `pv_csrf` cookie exists, fetching `GET /auth/csrf` once if needed. */
export async function ensureCsrf(): Promise<string | null> {
  const existing = readCookie(CSRF_COOKIE);
  if (existing) return existing;
  if (!csrfPromise) {
    csrfPromise = fetch(`${API_BASE}/auth/csrf`, { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) return null;
        const data = (await res.json().catch(() => null)) as { csrf_token?: string } | null;
        return readCookie(CSRF_COOKIE) ?? data?.csrf_token ?? null;
      })
      .catch(() => null)
      .finally(() => {
        csrfPromise = null;
      });
  }
  return csrfPromise;
}

async function parseError(res: Response): Promise<ApiError> {
  let envelope: ApiErrorEnvelope | null = null;
  try {
    const text = await res.text();
    if (text) envelope = JSON.parse(text) as ApiErrorEnvelope;
  } catch {
    envelope = null;
  }
  const retryAfterHeader = res.headers.get("Retry-After");
  const retryAfter = retryAfterHeader ? Number(retryAfterHeader) || undefined : undefined;
  const code = envelope?.error?.code ?? (res.status === 429 ? "rate_limited" : `http_${res.status}`);
  let message = envelope?.error?.message ?? DEFAULT_MESSAGES[res.status] ?? `Request failed (${res.status}).`;
  if (res.status === 429 && retryAfter && !envelope?.error?.message) {
    message = `Too many requests. Try again in ${retryAfter}s.`;
  }
  return new ApiError(res.status, code, message, envelope?.error?.details, retryAfter);
}

let refreshPromise: Promise<boolean> | null = null;

/** POST /auth/refresh (requires the CSRF header). Shared across concurrent 401s. */
export async function refreshSession(): Promise<boolean> {
  if (!refreshPromise) {
    refreshPromise = (async () => {
      const csrf = await ensureCsrf();
      const headers: Record<string, string> = {};
      if (csrf) headers[CSRF_HEADER] = csrf;
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          credentials: "include",
          headers,
        });
        return res.ok;
      } catch {
        return false;
      }
    })().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

async function doFetch(path: string, opts: RequestOptions): Promise<Response> {
  const method = opts.method ?? "GET";
  const headers: Record<string, string> = { Accept: "application/json", ...opts.headers };
  let body: BodyInit | undefined;

  if (opts.body instanceof FormData) {
    body = opts.body;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  if (MUTATING.has(method)) {
    const csrf = await ensureCsrf();
    if (csrf) headers[CSRF_HEADER] = csrf;
  }

  return fetch(`${API_BASE}${path}${buildQuery(opts.query)}`, {
    method,
    headers,
    body,
    credentials: "include",
    signal: opts.signal,
  });
}

/**
 * Typed fetch against the same-origin API. Parses the error envelope into `ApiError`; on a 401
 * attempts one refresh then retries once, otherwise hands off to the unauthenticated handler.
 */
export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  let res = await doFetch(path, opts);

  if (res.status === 401 && !opts.skipAuthRefresh && !path.startsWith("/auth/")) {
    const refreshed = await refreshSession();
    if (refreshed) {
      res = await doFetch(path, opts);
    }
  }

  if (res.status === 401 && !opts.skipAuthRedirect && !path.startsWith("/auth/")) {
    onUnauthenticated();
  }

  if (!res.ok) {
    throw await parseError(res);
  }

  if (res.status === 204 || res.headers.get("content-length") === "0") {
    return undefined as T;
  }
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

export interface UploadProgress {
  loaded: number;
  total: number;
}

/**
 * Multipart upload with real progress events (XMLHttpRequest, since fetch has no upload
 * progress). Same cookie + CSRF semantics as `api()`. One refresh-and-retry on 401.
 */
export async function upload<T>(
  path: string,
  form: FormData,
  options: { onProgress?: (p: UploadProgress) => void; signal?: AbortSignal; headers?: Record<string, string> } = {},
  attempt = 0,
): Promise<T> {
  const csrf = await ensureCsrf();
  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${path}`);
    xhr.withCredentials = true;
    xhr.responseType = "text";
    xhr.setRequestHeader("Accept", "application/json");
    if (csrf) xhr.setRequestHeader(CSRF_HEADER, csrf);
    for (const [k, v] of Object.entries(options.headers ?? {})) xhr.setRequestHeader(k, v);

    const abort = () => xhr.abort();
    options.signal?.addEventListener("abort", abort, { once: true });

    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) options.onProgress?.({ loaded: ev.loaded, total: ev.total });
    };
    xhr.onerror = () => reject(new ApiError(0, "network_error", "The upload failed. Check your connection and try again."));
    xhr.onabort = () => reject(new ApiError(0, "aborted", "Upload cancelled."));
    xhr.onload = async () => {
      options.signal?.removeEventListener("abort", abort);
      const status = xhr.status;
      if (status === 401 && attempt === 0) {
        const ok = await refreshSession();
        if (ok) {
          upload<T>(path, form, options, 1).then(resolve, reject);
          return;
        }
        onUnauthenticated();
      }
      if (status >= 200 && status < 300) {
        try {
          resolve(xhr.responseText ? (JSON.parse(xhr.responseText) as T) : (undefined as T));
        } catch {
          reject(new ApiError(status, "invalid_response", "The server returned an unexpected response."));
        }
        return;
      }
      const headers = new Headers();
      const ra = xhr.getResponseHeader("Retry-After");
      if (ra) headers.set("Retry-After", ra);
      const fake = new Response(xhr.responseText, { status, headers });
      reject(await parseError(fake));
    };
    xhr.send(form);
  });
}

/** Human-readable message for any thrown value. */
export function errorMessage(e: unknown, fallback = "Something went wrong. Please try again."): string {
  if (isApiError(e)) return e.message || fallback;
  if (e instanceof Error && e.message) return e.message;
  return fallback;
}

export function errorCode(e: unknown): string | null {
  return isApiError(e) ? e.code : null;
}
