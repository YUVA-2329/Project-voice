import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AudioPlayer } from "@/components/audio/AudioPlayer";

describe("AudioPlayer", () => {
  let playSpy: ReturnType<typeof vi.spyOn>;
  let pauseSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // jsdom's HTMLMediaElement has no playback; emulate play/pause with events.
    playSpy = vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(function (this: HTMLMediaElement) {
      Object.defineProperty(this, "paused", { value: false, configurable: true });
      this.dispatchEvent(new Event("play"));
      return Promise.resolve();
    });
    pauseSpy = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(function (this: HTMLMediaElement) {
      Object.defineProperty(this, "paused", { value: true, configurable: true });
      this.dispatchEvent(new Event("pause"));
    });
  });

  afterEach(() => {
    playSpy.mockRestore();
    pauseSpy.mockRestore();
  });

  it("renders elapsed/total in mono using the known duration and toggles play/pause", async () => {
    const user = userEvent.setup();
    render(<AudioPlayer src="/api/v1/generations/g1/audio" duration={8.085} downloadHref="/api/v1/generations/g1/audio?download=1" />);
    expect(screen.getByText("0:00")).toBeInTheDocument();
    expect(screen.getByText("0:08")).toBeInTheDocument();

    const play = screen.getByRole("button", { name: "Play" });
    await user.click(play);
    expect(playSpy).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("button", { name: "Pause" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Pause" }));
    expect(pauseSpy).toHaveBeenCalledTimes(1);
    expect(await screen.findByRole("button", { name: "Play" })).toBeInTheDocument();
  });

  it("exposes a download link to the ?download=1 URL", () => {
    render(<AudioPlayer src="/api/v1/generations/g1/audio" duration={5} downloadHref="/api/v1/generations/g1/audio?download=1" />);
    expect(screen.getByRole("link", { name: "Download" })).toHaveAttribute("href", "/api/v1/generations/g1/audio?download=1");
  });

  it("seeks with the scrubber and reports elapsed time from the element", () => {
    const { container } = render(<AudioPlayer src="/x.wav" duration={10} />);
    const audio = container.querySelector("audio") as HTMLAudioElement;
    const slider = screen.getByRole("slider", { name: "Seek" });
    fireEvent.change(slider, { target: { value: "4" } });
    expect(audio.currentTime).toBe(4);
    fireEvent.mouseUp(slider);
    act(() => {
      audio.currentTime = 6;
      audio.dispatchEvent(new Event("timeupdate"));
    });
    expect(screen.getByText("0:06")).toBeInTheDocument();
    expect(slider).toHaveAttribute("aria-valuetext", "0:06 of 0:10");
  });

  it("calls onRegenerate", async () => {
    const onRegenerate = vi.fn();
    render(<AudioPlayer src="/x.wav" duration={1} onRegenerate={onRegenerate} />);
    await userEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(onRegenerate).toHaveBeenCalled();
  });

  it("surfaces load errors", () => {
    const { container } = render(<AudioPlayer src="/missing.wav" />);
    const audio = container.querySelector("audio") as HTMLAudioElement;
    act(() => {
      audio.dispatchEvent(new Event("error"));
    });
    expect(screen.getByRole("alert")).toHaveTextContent("The audio could not be loaded.");
    expect(screen.getByRole("button", { name: "Play" })).toBeDisabled();
  });
});
