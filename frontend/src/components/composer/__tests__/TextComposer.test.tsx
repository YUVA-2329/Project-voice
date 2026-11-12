import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { TextComposer } from "@/components/composer/TextComposer";

function Harness({ onRun, initial = "" }: { onRun?: () => void; initial?: string }) {
  const [value, setValue] = useState(initial);
  return <TextComposer value={value} onChange={setValue} onRun={onRun} />;
}

describe("TextComposer", () => {
  it("shows the placeholder and a mono character count out of 5000", () => {
    render(<Harness />);
    expect(screen.getByPlaceholderText("What would you like your voice to say?")).toBeInTheDocument();
    expect(screen.getByText(/0 \/ 5,000/)).toBeInTheDocument();
  });

  it("updates the count as the user types and clears", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const ta = screen.getByLabelText("Text to speak");
    await user.type(ta, "Hello");
    expect(screen.getByText(/5 \/ 5,000/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Clear text" }));
    expect(ta).toHaveValue("");
    expect(screen.queryByRole("button", { name: "Clear text" })).not.toBeInTheDocument();
  });

  it("runs on Ctrl/Cmd+Enter but not on plain Enter", () => {
    const onRun = vi.fn();
    render(<Harness onRun={onRun} initial="Say this" />);
    const ta = screen.getByLabelText("Text to speak");
    fireEvent.keyDown(ta, { key: "Enter" });
    expect(onRun).not.toHaveBeenCalled();
    fireEvent.keyDown(ta, { key: "Enter", ctrlKey: true });
    fireEvent.keyDown(ta, { key: "Enter", metaKey: true });
    expect(onRun).toHaveBeenCalledTimes(2);
  });

  it("flags text over the limit", () => {
    render(<Harness initial={"a".repeat(5001)} />);
    expect(screen.getByLabelText("Text to speak")).toHaveAttribute("aria-invalid", "true");
  });
});
