import { describe, expect, it } from "vitest";
import { generationStageText, jobStageText, progressFraction } from "@/lib/stages";

describe("generationStageText", () => {
  it("uses the real progress object, never a fake percentage", () => {
    expect(generationStageText({ status: "queued", progress: null })).toBe("Queued");
    expect(generationStageText({ status: "processing", progress: null })).toBe("Processing");
    expect(generationStageText({ status: "processing", progress: { stage: "load_model", current: 0, total: 1 } })).toBe("Loading model");
    expect(generationStageText({ status: "processing", progress: { stage: "synthesize", current: 2, total: 4 } })).toBe("Synthesising 2 of 4");
    expect(generationStageText({ status: "processing", progress: { stage: "encode", current: 0, total: 1 } })).toBe("Encoding");
    expect(generationStageText({ status: "completed", progress: { stage: "done", current: 1, total: 1 } })).toBe("");
  });
  it("humanises unknown stages", () => {
    expect(generationStageText({ status: "processing", progress: { stage: "post_process", current: 0, total: 1 } })).toBe("Post process");
  });
});

describe("jobStageText", () => {
  it("maps voice job stages observed in the e2e log", () => {
    expect(jobStageText({ status: "running", progress: { stage: "analyse", current: 0, total: 1 } })).toBe("Analysing quality");
    expect(jobStageText({ status: "running", progress: { stage: "transcribe", current: 0, total: 1 } })).toBe("Transcribing");
    expect(jobStageText({ status: "completed", progress: { stage: "done", current: 1, total: 1 } })).toBe("Finishing up");
    expect(jobStageText({ status: "queued", progress: null })).toBe("Queued");
    expect(jobStageText(undefined, "Starting")).toBe("Starting");
  });
});

describe("progressFraction", () => {
  it("returns current/total clamped, or null when unknown", () => {
    expect(progressFraction({ stage: "synthesize", current: 2, total: 4 })).toBe(0.5);
    expect(progressFraction({ stage: "x", current: 9, total: 4 })).toBe(1);
    expect(progressFraction({ stage: "x", current: 0, total: 0 })).toBeNull();
    expect(progressFraction(null)).toBeNull();
  });
});
