import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CreateVoiceWizard } from "@/components/voice/CreateVoiceWizard";
import { CONSENT_TEXT } from "@/lib/api/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/app/voices/create",
}));

const mockCreate = vi.fn();
vi.mock("@/lib/api/resources", async (importOriginal) => {
  const mod = await importOriginal<typeof import("@/lib/api/resources")>();
  return {
    ...mod,
    voices: { ...mod.voices, create: (...args: unknown[]) => mockCreate(...args) },
    system: { ...mod.system, languages: () => Promise.resolve([]) },
  };
});

// AudioUploader decodes with Web Audio; jsdom has none, so the uploader keeps the file and
// defers the duration check to the server. Stub URL.createObjectURL for the preview player.
beforeEach(() => {
  mockCreate.mockReset();
  mockCreate.mockImplementation(() => new Promise(() => undefined));
  Object.defineProperty(URL, "createObjectURL", { value: () => "blob:test", writable: true });
  Object.defineProperty(URL, "revokeObjectURL", { value: () => undefined, writable: true });
});

function renderWizard() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <CreateVoiceWizard />
    </QueryClientProvider>,
  );
}

async function reachDetails(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: /Upload audio/ }));
  const input = screen.getByLabelText(/Choose a file/);
  const file = new File([new Uint8Array(4096)], "sample.wav", { type: "audio/wav" });
  await user.upload(input, file);
  await screen.findByText("sample.wav");
  await user.click(screen.getByRole("button", { name: "Continue" }));
  await screen.findByText("What should we call this voice?");
}

describe("CreateVoiceWizard consent gating", () => {
  it("starts with the two choices", () => {
    renderWizard();
    expect(screen.getByText("Let's create your voice.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Record my voice/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Upload audio/ })).toBeInTheDocument();
  });

  it("shows the exact consent text and refuses to submit until it is ticked", async () => {
    const user = userEvent.setup();
    renderWizard();
    await reachDetails(user);

    expect(screen.getByText(CONSENT_TEXT)).toBeInTheDocument();
    await user.type(screen.getByLabelText("Voice name"), "My voice");
    await user.click(screen.getByRole("button", { name: "Create voice" }));

    expect(mockCreate).not.toHaveBeenCalled();
    expect(await screen.findByText("You need to confirm this before we can continue.")).toBeInTheDocument();

    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Create voice" }));
    expect(mockCreate).toHaveBeenCalledTimes(1);
    const input = mockCreate.mock.calls[0]?.[0] as { name: string; consent_confirmed: boolean; consent_text_version: string; fileName: string };
    expect(input.name).toBe("My voice");
    expect(input.consent_confirmed).toBe(true);
    expect(input.consent_text_version).toBe("v1");
    expect(input.fileName).toBe("sample.wav");
    expect(await screen.findByText("Uploading…")).toBeInTheDocument();
  });

  it("requires a name as well", async () => {
    const user = userEvent.setup();
    renderWizard();
    await reachDetails(user);
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Create voice" }));
    expect(mockCreate).not.toHaveBeenCalled();
    expect(await screen.findByText("Give the voice a name.")).toBeInTheDocument();
  });

  it("rejects unsupported file types client-side", async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderWizard();
    await user.click(screen.getByRole("button", { name: /Upload audio/ }));
    const input = screen.getByLabelText(/Choose a file/);
    await user.upload(input, new File([new Uint8Array(10)], "notes.txt", { type: "text/plain" }));
    expect(await screen.findByText(/That file type is not supported/)).toBeInTheDocument();
    expect(screen.getByText("unsupported_format")).toBeInTheDocument();
  });
});
