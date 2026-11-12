import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RunButton } from "@/components/composer/RunButton";
import { TooltipProvider } from "@/components/ui/Tooltip";

const wrap = (ui: React.ReactElement) => render(<TooltipProvider>{ui}</TooltipProvider>);

describe("RunButton", () => {
  it("is enabled and labelled Run when idle", async () => {
    const onRun = vi.fn();
    wrap(<RunButton onRun={onRun} />);
    const btn = screen.getByRole("button", { name: "Run" });
    expect(btn).toBeEnabled();
    await userEvent.click(btn);
    expect(onRun).toHaveBeenCalledTimes(1);
  });

  it("is disabled with an accessible reason", () => {
    wrap(<RunButton onRun={() => undefined} disabledReason="Create a voice first" />);
    const btn = screen.getByRole("button", { name: "Run" });
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-describedby", "run-reason");
    expect(screen.getByText("Create a voice first")).toBeInTheDocument();
  });

  it("shows Queued while queued, without a progress bar", () => {
    wrap(<RunButton onRun={() => undefined} running={{ status: "queued", progress: null }} />);
    expect(screen.getByRole("button")).toHaveTextContent("Queued");
    expect(screen.getByRole("button")).toBeDisabled();
    expect(screen.queryByTestId("run-progress")).not.toBeInTheDocument();
  });

  it("shows the real stage text and a bar whose width is current/total", () => {
    wrap(<RunButton onRun={() => undefined} running={{ status: "processing", progress: { stage: "synthesize", current: 2, total: 4 } }} />);
    expect(screen.getByRole("button")).toHaveTextContent("Synthesising 2 of 4");
    expect(screen.getByTestId("run-progress")).toHaveStyle({ width: "50%" });
  });

  it("shows Processing with an empty bar when progress is null", () => {
    wrap(<RunButton onRun={() => undefined} running={{ status: "processing", progress: null }} />);
    expect(screen.getByRole("button")).toHaveTextContent("Processing");
    expect(screen.getByTestId("run-progress")).toHaveStyle({ width: "0%" });
  });

  it("shows Starting while the request is in flight", () => {
    wrap(<RunButton onRun={() => undefined} submitting />);
    expect(screen.getByRole("button")).toHaveTextContent("Starting");
  });
});
