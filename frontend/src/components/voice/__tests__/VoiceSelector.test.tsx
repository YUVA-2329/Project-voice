import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { VoiceSelector } from "@/components/voice/VoiceSelector";
import type { Paginated, Voice } from "@/lib/api/types";
import { useAppStore } from "@/lib/store";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/app",
}));

const mockList = vi.fn<() => Promise<Paginated<Voice>>>();
vi.mock("@/lib/api/resources", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api/resources")>();
  return { ...mod, voices: { ...mod.voices, list: () => mockList() } };
});

function voice(partial: Partial<Voice> & Pick<Voice, "id" | "name" | "status">): Voice {
  return {
    error: null,
    language: "en",
    detected_language: "en",
    engine_id: "zipvoice_distill",
    transcript: null,
    transcript_source: null,
    reference: null,
    quality: null,
    consent: { given_at: "2026-11-09T12:00:00Z", text_version: "v1", revoked_at: null },
    preview_generation_id: null,
    job_id: null,
    created_at: "2026-11-09T12:00:00Z",
    updated_at: "2026-11-09T12:00:00Z",
    ...partial,
  };
}

function renderWithClient(ui: React.ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("VoiceSelector", () => {
  beforeEach(() => {
    mockList.mockReset();
    useAppStore.setState({ selectedVoiceId: null, mode: "simple" });
  });

  it("shows the empty state with a link to Create when no voice is ready", async () => {
    mockList.mockResolvedValue({ items: [], total: 0, limit: 100, offset: 0 });
    renderWithClient(<VoiceSelector />);
    expect(await screen.findByText("No voice yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Create your voice/ })).toHaveAttribute("href", "/app/voices/create");
  });

  it("auto-selects the first ready voice and lists only ready voices", async () => {
    mockList.mockResolvedValue({
      items: [
        voice({ id: "a", name: "Lei", status: "ready" }),
        voice({ id: "b", name: "Newsreader", status: "ready", language: "zh" }),
        voice({ id: "c", name: "Broken", status: "failed" }),
      ],
      total: 3,
      limit: 100,
      offset: 0,
    });
    const user = userEvent.setup();
    renderWithClient(<VoiceSelector />);
    const trigger = await screen.findByRole("button", { name: /Selected voice: Lei/ });
    await waitFor(() => expect(useAppStore.getState().selectedVoiceId).toBe("a"));
    await user.click(trigger);
    const options = await screen.findAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual([expect.stringContaining("Lei"), expect.stringContaining("Newsreader")]);
    await user.click(within(screen.getByRole("option", { name: /Newsreader/ })).getByRole("button"));
    expect(useAppStore.getState().selectedVoiceId).toBe("b");
  });

  it("drops a persisted selection that no longer exists", async () => {
    useAppStore.setState({ selectedVoiceId: "gone", mode: "simple" });
    mockList.mockResolvedValue({ items: [voice({ id: "a", name: "Lei", status: "ready" })], total: 1, limit: 100, offset: 0 });
    renderWithClient(<VoiceSelector />);
    await waitFor(() => expect(useAppStore.getState().selectedVoiceId).toBe("a"));
  });
});
