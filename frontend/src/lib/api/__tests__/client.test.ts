import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, api, ensureCsrf, isApiError, readCookie, setUnauthenticatedHandler } from "@/lib/api/client";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${value}; path=/`;
}

function clearCookies() {
  for (const c of document.cookie.split(";")) {
    const name = c.split("=")[0]?.trim();
    if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`;
  }
}

describe("api client", () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    clearCookies();
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
    setUnauthenticatedHandler(() => undefined);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("reads cookies", () => {
    setCookie("pv_csrf", "abc123");
    expect(readCookie("pv_csrf")).toBe("abc123");
    expect(readCookie("missing")).toBeNull();
  });

  it("sends X-CSRF-Token from the pv_csrf cookie on mutating requests only", async () => {
    setCookie("pv_csrf", "tok-1");
    fetchMock.mockImplementation(async () => jsonResponse({ ok: true }));

    await api("/voices", { method: "POST", body: { name: "x" } });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/voices");
    expect((init.headers as Record<string, string>)["X-CSRF-Token"]).toBe("tok-1");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(init.credentials).toBe("include");
    expect(init.body).toBe(JSON.stringify({ name: "x" }));

    fetchMock.mockClear();
    await api("/voices");
    const [, getInit] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect((getInit.headers as Record<string, string>)["X-CSRF-Token"]).toBeUndefined();
  });

  it("fetches /auth/csrf once when the cookie is missing", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/auth/csrf")) {
        setCookie("pv_csrf", "fresh");
        return jsonResponse({ csrf_token: "fresh" });
      }
      return jsonResponse({ ok: true });
    });
    const token = await ensureCsrf();
    expect(token).toBe("fresh");
    await api("/generations", { method: "POST", body: { text: "hi" } });
    const calls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(calls.filter((u) => u.endsWith("/auth/csrf"))).toHaveLength(1);
    const post = fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/generations")) as [string, RequestInit];
    expect((post[1].headers as Record<string, string>)["X-CSRF-Token"]).toBe("fresh");
  });

  it("parses the error envelope into ApiError", async () => {
    setCookie("pv_csrf", "t");
    fetchMock.mockResolvedValue(
      jsonResponse(
        {
          error: {
            code: "validation_error",
            message: "Some of the information is not valid.",
            details: { fields: [{ loc: ["body", "password"], msg: "Use at least 10 characters.", type: "value_error" }] },
          },
        },
        { status: 422 },
      ),
    );
    const err = await api("/auth/register", { method: "POST", body: {} }).catch((e: unknown) => e);
    expect(isApiError(err)).toBe(true);
    const apiErr = err as ApiError;
    expect(apiErr.status).toBe(422);
    expect(apiErr.code).toBe("validation_error");
    expect(apiErr.message).toBe("Some of the information is not valid.");
    expect(apiErr.fieldErrors()).toEqual({ password: "Use at least 10 characters." });
  });

  it("falls back to a human message and Retry-After for 429 without a body", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 429, headers: { "Retry-After": "7" } }));
    const err = (await api("/voices").catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(429);
    expect(err.code).toBe("rate_limited");
    expect(err.retryAfter).toBe(7);
    expect(err.message).toContain("7s");
  });

  it("on 401 refreshes once (with CSRF) and retries the original request", async () => {
    setCookie("pv_csrf", "csrf-x");
    let voicesCalls = 0;
    fetchMock.mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.endsWith("/voices")) {
        voicesCalls += 1;
        if (voicesCalls === 1) return jsonResponse({ error: { code: "unauthenticated" } }, { status: 401 });
        return jsonResponse({ items: [], total: 0, limit: 100, offset: 0 });
      }
      if (url.endsWith("/auth/refresh")) {
        expect(init?.method).toBe("POST");
        expect((init?.headers as Record<string, string>)["X-CSRF-Token"]).toBe("csrf-x");
        return jsonResponse({ user: { id: "u1" } });
      }
      throw new Error(`unexpected ${url}`);
    });
    const result = await api<{ total: number }>("/voices");
    expect(result.total).toBe(0);
    expect(voicesCalls).toBe(2);
    expect(fetchMock.mock.calls.some((c) => String(c[0]).endsWith("/auth/refresh"))).toBe(true);
  });

  it("calls the unauthenticated handler when refresh fails", async () => {
    setCookie("pv_csrf", "c");
    const handler = vi.fn();
    setUnauthenticatedHandler(handler);
    fetchMock.mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh")) return jsonResponse({ error: { code: "unauthenticated" } }, { status: 401 });
      return jsonResponse({ error: { code: "unauthenticated" } }, { status: 401 });
    });
    const err = (await api("/users/me").catch((e: unknown) => e)) as ApiError;
    expect(err.status).toBe(401);
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("returns undefined for 204 responses", async () => {
    setCookie("pv_csrf", "c");
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));
    await expect(api("/voices/1", { method: "DELETE" })).resolves.toBeUndefined();
  });
});
