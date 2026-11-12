import { describe, expect, it } from "vitest";
import { excerpt, formatBytes, formatDuration, formatMegabytes, formatRelative, formatRtf, formatSeconds } from "@/lib/format";

describe("formatDuration", () => {
  it("formats seconds as m:ss", () => {
    expect(formatDuration(0)).toBe("0:00");
    expect(formatDuration(8.085)).toBe("0:08");
    expect(formatDuration(90.003)).toBe("1:30");
    expect(formatDuration(3725)).toBe("1:02:05");
  });
  it("handles bad input", () => {
    expect(formatDuration(null)).toBe("0:00");
    expect(formatDuration(Number.POSITIVE_INFINITY)).toBe("0:00");
    expect(formatDuration(-5)).toBe("0:00");
  });
});

describe("formatBytes / formatMegabytes", () => {
  it("scales units", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(388274)).toBe("379 KB");
    expect(formatBytes(25 * 1024 * 1024)).toBe("25 MB");
    expect(formatBytes(null)).toBe("—");
    expect(formatMegabytes(2048)).toBe("2.0 GB");
    expect(formatMegabytes(512)).toBe("512 MB");
  });
});

describe("formatSeconds / formatRtf", () => {
  it("rounds to one decimal and marks unknowns", () => {
    expect(formatSeconds(11.2337)).toBe("11.2 s");
    expect(formatSeconds(null)).toBe("—");
    expect(formatRtf(1.3893)).toBe("1.39×");
    expect(formatRtf(null)).toBe("—");
  });
});

describe("formatRelative", () => {
  const now = Date.parse("2026-11-09T12:00:00Z");
  it("describes heartbeats", () => {
    expect(formatRelative("2026-11-09T11:59:58Z", now)).toBe("just now");
    expect(formatRelative("2026-11-09T11:59:18Z", now)).toBe("42 s ago");
    expect(formatRelative("2026-11-09T11:57:00Z", now)).toBe("3 min ago");
    expect(formatRelative(null, now)).toBe("never");
  });
});

describe("excerpt", () => {
  it("collapses whitespace and truncates with an ellipsis", () => {
    expect(excerpt("hello   world")).toBe("hello world");
    const long = "a".repeat(200);
    expect(excerpt(long, 50)).toHaveLength(50);
    expect(excerpt(long, 50).endsWith("…")).toBe(true);
  });
});
