import { beforeEach, describe, expect, it } from "vitest";
import { STORE_KEY, useAppStore } from "@/lib/store";

describe("app store", () => {
  beforeEach(() => {
    localStorage.clear();
    useAppStore.setState({ selectedVoiceId: null, mode: "simple" });
  });

  it("holds the selected voice and mode", () => {
    useAppStore.getState().setSelectedVoiceId("v1");
    useAppStore.getState().setMode("advanced");
    expect(useAppStore.getState().selectedVoiceId).toBe("v1");
    expect(useAppStore.getState().mode).toBe("advanced");
  });

  it("persists only selectedVoiceId and mode to localStorage", () => {
    useAppStore.getState().setSelectedVoiceId("v2");
    const raw = localStorage.getItem(STORE_KEY);
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw as string) as { state: Record<string, unknown> };
    expect(parsed.state).toEqual({ selectedVoiceId: "v2", mode: "simple" });
  });
});
