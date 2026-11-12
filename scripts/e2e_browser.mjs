#!/usr/bin/env node
/**
 * PROJECT VOICE — browser end-to-end test (the 22-step acceptance workflow).
 *
 * Drives the real Next.js frontend against the real API + worker with Chromium. The microphone is
 * Chromium's fake capture device fed by a real speech WAV, so the "Record my voice" path exercises
 * MediaRecorder → upload → decode → VAD → Whisper → engine validation for real. Nothing is mocked.
 *
 * Usage:  node scripts/e2e_browser.mjs [--base http://localhost:3000] [--mic path.wav] [--upload path.wav]
 * Output: evidence/browser/*.png, evidence/browser/download.wav, evidence/e2e_browser_log.txt,
 *         evidence/e2e_browser_summary.json. Exit code 0 only if every step passed.
 */
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
// Resolve Playwright from the project, a global install, or PLAYWRIGHT_PATH.
const { chromium } = require(process.env.PLAYWRIGHT_PATH ?? (() => { try { return require.resolve("playwright"); } catch { return "/opt/npm-tools/node_modules/playwright"; } })());
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, a, i, arr) => {
    if (a.startsWith("--")) acc.push([a.slice(2), arr[i + 1] ?? "true"]);
    return acc;
  }, []),
);
const BASE = args.base ?? "http://localhost:3000";
const MIC_WAV = path.resolve(args.mic ?? path.join(root, "evidence/generation_short.wav"));
const UPLOAD_WAV = path.resolve(
  args.upload ?? path.join(root, "models/zipvoice-distill/test_wavs/news-female.wav"),
);
const OUT = path.join(root, "evidence", "browser");
fs.mkdirSync(OUT, { recursive: true });

const started = Date.now();
const steps = [];
const logLines = [];
function log(msg) {
  const line = `[${((Date.now() - started) / 1000).toFixed(1).padStart(6)}s] ${msg}`;
  logLines.push(line);
  console.log(line);
}
async function step(name, fn) {
  const t0 = Date.now();
  try {
    const detail = (await fn()) ?? "";
    steps.push({ name, ok: true, seconds: (Date.now() - t0) / 1000, detail: String(detail) });
    log(`✓ ${name} (${((Date.now() - t0) / 1000).toFixed(1)}s)${detail ? ` — ${detail}` : ""}`);
  } catch (err) {
    steps.push({ name, ok: false, seconds: (Date.now() - t0) / 1000, detail: String(err?.message ?? err) });
    log(`✗ ${name} — ${err?.message ?? err}`);
    throw err;
  }
}
let shot = 0;
async function snap(page, label) {
  const file = path.join(OUT, `${String(++shot).padStart(2, "0")}-${label}.png`);
  await page.screenshot({ path: file, fullPage: false });
  return file;
}
function wavInfo(buf) {
  if (buf.length < 44 || buf.toString("ascii", 0, 4) !== "RIFF" || buf.toString("ascii", 8, 12) !== "WAVE") {
    throw new Error("not a RIFF/WAVE file");
  }
  let off = 12;
  let fmt = null;
  let dataLen = 0;
  while (off + 8 <= buf.length) {
    const id = buf.toString("ascii", off, off + 4);
    const size = buf.readUInt32LE(off + 4);
    if (id === "fmt ") {
      fmt = {
        channels: buf.readUInt16LE(off + 10),
        sampleRate: buf.readUInt32LE(off + 12),
        bits: buf.readUInt16LE(off + 22),
      };
    } else if (id === "data") {
      dataLen = size;
    }
    off += 8 + size + (size % 2);
  }
  if (!fmt || !dataLen) throw new Error("WAV missing fmt or data chunk");
  const seconds = dataLen / (fmt.sampleRate * fmt.channels * (fmt.bits / 8));
  return { ...fmt, seconds, bytes: buf.length };
}

const stamp = Date.now().toString(36);
const user = { email: `browser-${stamp}@example.com`, name: "Browser Tester", password: `Pv-${stamp}-strong-pass` };
const VOICE_1 = "Recorded voice";
const VOICE_2 = "Uploaded voice";
const SENTENCE_1 = "Hello from the browser test. This sentence was spoken by a voice I recorded a minute ago.";
const SENTENCE_2 = "Here is a second sentence, generated to confirm that history keeps every result.";

const browser = await chromium.launch({
  args: [
    "--use-fake-ui-for-media-stream",
    "--use-fake-device-for-media-stream",
    `--use-file-for-fake-audio-capture=${MIC_WAV}`,
    "--autoplay-policy=no-user-gesture-required",
  ],
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  acceptDownloads: true,
  permissions: ["microphone"],
});
const page = await context.newPage();
page.setDefaultTimeout(30_000);
const consoleErrors = [];
page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text());
});
page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${e.message}`));

let generationId1 = null;
let ok = false;
try {
  await step("1. open introduction and create an account", async () => {
    await page.goto(`${BASE}/`);
    await page.getByRole("heading", { level: 1 }).waitFor();
    await snap(page, "intro");
    await page.goto(`${BASE}/register`);
    await page.getByLabel("Email").fill(user.email);
    await page.getByLabel("Display name").fill(user.name);
    await page.getByLabel("Password").fill(user.password);
    await page.getByRole("button", { name: "Create account" }).click();
    await page.waitForURL(/\/app(\/.*)?$/);
    await snap(page, "app-after-register");
    return `email=${user.email}`;
  });

  await step("2. sign out and log in", async () => {
    await page.getByRole("button", { name: "Account menu" }).click();
    await page.getByRole("menuitem", { name: /sign out/i }).click();
    await page.waitForURL(/\/(login)?$/);
    await page.goto(`${BASE}/login`);
    await page.getByLabel("Email").fill(user.email);
    await page.getByLabel("Password").fill(user.password);
    await page.getByRole("button", { name: "Sign in" }).click();
    await page.waitForURL(/\/app(\/.*)?$/);
    await snap(page, "app-empty");
  });

  await step("3. record a voice with the (fake-device) microphone", async () => {
    await page.goto(`${BASE}/app/voices/create`);
    await page.getByText("Record my voice").click();
    await page.getByRole("button", { name: "Start recording" }).click();
    await snap(page, "recording");
    await page.waitForTimeout(12_500);
    await page.getByRole("button", { name: "Stop" }).click();
    await page.getByRole("button", { name: "Continue" }).waitFor({ state: "visible" });
    const continueBtn = page.getByRole("button", { name: "Continue" });
    await continueBtn.waitFor();
    await page.waitForFunction(
      () => {
        const b = [...document.querySelectorAll("button")].find((x) => x.textContent?.trim() === "Continue");
        return b && !b.disabled;
      },
      null,
      { timeout: 10_000 },
    );
    await snap(page, "recorded");
    await continueBtn.click();
    await page.getByLabel("Voice name").waitFor();
  });

  await step("4. name the voice and confirm consent", async () => {
    const name = page.getByLabel("Voice name");
    await name.fill("");
    await name.fill(VOICE_1);
    const create = page.getByRole("button", { name: "Create voice" });
    const before = await create.getAttribute("aria-disabled");
    await page.getByRole("checkbox").check();
    await snap(page, "details-consent");
    return `create aria-disabled before consent=${before}`;
  });

  await step("5–6. create the voice clone and wait for real processing", async () => {
    await page.getByRole("button", { name: "Create voice" }).click();
    await page.getByText("Your voice is ready.").waitFor({ timeout: 240_000 });
    await snap(page, "voice-ready");
    const heard = await page.getByText(/We heard/).first().textContent().catch(() => "");
    return heard?.trim().slice(0, 120);
  });

  await step("7. the voice appears in My Voices", async () => {
    await page.goto(`${BASE}/app/voices`);
    await page.getByRole("article", { name: VOICE_1 }).or(page.getByText(VOICE_1)).first().waitFor();
    await snap(page, "voices-one");
  });

  await step("8–9. refresh the page — the voice persists", async () => {
    await page.reload();
    await page.getByText(VOICE_1).first().waitFor();
    const cards = await page.getByRole("button", { name: /^(Select|Selected)$/ }).count();
    if (cards < 1) throw new Error("no voice cards after reload");
    return `cards=${cards}`;
  });

  await step("10. select the voice", async () => {
    const select = page.getByRole("button", { name: /^(Select|Selected)$/ }).first();
    if ((await select.textContent())?.trim() === "Select") await select.click();
    await page.waitForURL(/\/app$/, { timeout: 10_000 }).catch(() => page.goto(`${BASE}/app`));
    await page.getByText(VOICE_1).first().waitFor();
    await snap(page, "app-selected");
  });

  await step("11–13. type a sentence, press Run and wait for real inference", async () => {
    const composer = page.getByPlaceholder("What would you like your voice to say?");
    await composer.fill(SENTENCE_1);
    await page.getByRole("button", { name: /^Run/ }).click();
    const t0 = Date.now();
    let sawProgress = "";
    const deadline = Date.now() + 240_000;
    while (Date.now() < deadline) {
      const btn = await page.getByRole("button", { name: /Run|Queued|Processing|Synthesis|Starting|Encoding|Loading|Preparing/i }).first().textContent().catch(() => "");
      if (btn && !/^Run$/.test(btn.trim())) sawProgress = btn.trim();
      if (await page.getByRole("button", { name: "Download" }).or(page.getByLabel("Download")).first().isVisible().catch(() => false)) break;
      await page.waitForTimeout(700);
    }
    await page.getByLabel("Download").first().waitFor({ timeout: 5_000 });
    await snap(page, "generation-result");
    return `waited ${((Date.now() - t0) / 1000).toFixed(1)}s; last progress label="${sawProgress}"`;
  });

  await step("14. play the generated speech in the page", async () => {
    const audioCount = await page.locator("audio").count();
    if (audioCount < 1) throw new Error("no <audio> element in result");
    await page.getByRole("button", { name: /^Play/ }).first().click();
    await page.waitForTimeout(1800);
    const state = await page.evaluate(() => {
      const a = document.querySelector("audio");
      return { t: a?.currentTime ?? 0, dur: a?.duration ?? 0, paused: a?.paused, src: a?.currentSrc ?? "" };
    });
    if (!(state.dur > 0.5)) throw new Error(`audio duration not loaded: ${JSON.stringify(state)}`);
    if (!(state.t > 0.3)) throw new Error(`playback did not advance: ${JSON.stringify(state)}`);
    generationId1 = state.src.match(/generations\/([0-9a-f-]+)\/audio/)?.[1] ?? null;
    await page.getByRole("button", { name: /^Pause/ }).first().click().catch(() => {});
    return `currentTime=${state.t.toFixed(2)}s duration=${state.dur.toFixed(2)}s id=${generationId1}`;
  });

  await step("15–16. download the audio and verify the WAV file", async () => {
    const [download] = await Promise.all([
      page.waitForEvent("download", { timeout: 30_000 }),
      page.getByLabel("Download").first().click(),
    ]);
    const file = path.join(OUT, "download.wav");
    await download.saveAs(file);
    const info = wavInfo(fs.readFileSync(file));
    if (info.seconds < 2) throw new Error(`downloaded WAV too short: ${JSON.stringify(info)}`);
    return `${download.suggestedFilename()} ${info.bytes} bytes, ${info.sampleRate} Hz, ${info.channels}ch, ${info.seconds.toFixed(2)}s`;
  });

  await step("17. generate a second sentence", async () => {
    const composer = page.getByPlaceholder("What would you like your voice to say?");
    await page.getByLabel("Clear text").click().catch(() => {});
    await composer.fill(SENTENCE_2);
    await composer.press("Control+Enter");
    await page.waitForTimeout(500);
    const deadline = Date.now() + 240_000;
    let seen = 0;
    while (Date.now() < deadline) {
      seen = await page.getByLabel("Download").count();
      const running = await page.getByRole("button", { name: /Queued|Processing|Synthesis|Starting|Encoding|Loading|Preparing/i }).count();
      if (seen >= 1 && running === 0) {
        const statusText = await page.getByText(/Ready ·/).first().textContent().catch(() => "");
        if (statusText) break;
      }
      await page.waitForTimeout(700);
    }
    await snap(page, "second-generation");
  });

  await step("18. history lists both generations", async () => {
    await page.goto(`${BASE}/app/history`);
    await page.getByText(SENTENCE_1.slice(0, 30)).first().waitFor();
    await page.getByText(SENTENCE_2.slice(0, 30)).first().waitFor();
    await snap(page, "history");
    const n = await page.getByLabel("Download").count();
    return `download controls=${n}`;
  });

  await step("19. create a second authorised voice by upload", async () => {
    await page.goto(`${BASE}/app/voices/create`);
    await page.getByText("Upload audio").click();
    const input = page.locator('input[type="file"]');
    await input.setInputFiles(UPLOAD_WAV);
    const continueBtn = page.getByRole("button", { name: "Continue" });
    await page.waitForFunction(
      () => {
        const b = [...document.querySelectorAll("button")].find((x) => x.textContent?.trim() === "Continue");
        return b && !b.disabled;
      },
      null,
      { timeout: 15_000 },
    );
    await snap(page, "upload-decoded");
    await continueBtn.click();
    const name = page.getByLabel("Voice name");
    await name.fill("");
    await name.fill(VOICE_2);
    await page.getByRole("checkbox").check();
    await page.getByRole("button", { name: "Create voice" }).click();
    await page.getByText("Your voice is ready.").waitFor({ timeout: 240_000 });
    await snap(page, "second-voice-ready");
  });

  await step("20. both voices are listed separately", async () => {
    await page.goto(`${BASE}/app/voices`);
    await page.getByText(VOICE_1).first().waitFor();
    await page.getByText(VOICE_2).first().waitFor();
    const selects = await page.getByRole("button", { name: /^(Select|Selected)$/ }).count();
    if (selects !== 2) throw new Error(`expected 2 voice cards, saw ${selects}`);
    await snap(page, "voices-two");
  });

  await step("21. delete the uploaded voice", async () => {
    await page.getByRole("button", { name: `More actions for ${VOICE_2}` }).click();
    await page.getByRole("menuitem", { name: "Delete" }).click();
    await page.getByRole("button", { name: "Delete voice" }).click();
    await page.getByText(VOICE_2, { exact: true }).waitFor({ state: "detached", timeout: 15_000 });
  });

  await step("22. deletion persists after reload; recorded voice remains", async () => {
    await page.reload();
    await page.getByText(VOICE_1).first().waitFor();
    const gone = (await page.getByText(VOICE_2, { exact: true }).count()) === 0;
    if (!gone) throw new Error("deleted voice still listed");
    await snap(page, "voices-after-delete");
    await page.goto(`${BASE}/app/history`);
    await page.getByText(SENTENCE_1.slice(0, 30)).first().waitFor();
    return "history still lists generations of the remaining voice";
  });

  ok = true;
} catch (err) {
  await snap(page, "FAILURE").catch(() => {});
  log(`FAILED: ${err?.stack ?? err}`);
} finally {
  await browser.close();
  const summary = {
    ok,
    base: BASE,
    mic_wav: MIC_WAV,
    upload_wav: UPLOAD_WAV,
    user: user.email,
    total_seconds: (Date.now() - started) / 1000,
    steps,
    console_errors: consoleErrors.slice(0, 20),
  };
  fs.writeFileSync(path.join(root, "evidence", "e2e_browser_summary.json"), JSON.stringify(summary, null, 2));
  fs.writeFileSync(path.join(root, "evidence", "e2e_browser_log.txt"), logLines.join("\n") + "\n");
  log(`RESULT: ${ok ? "PASS" : "FAIL"} — ${steps.filter((s) => s.ok).length}/${steps.length} steps, console errors: ${consoleErrors.length}`);
  process.exit(ok ? 0 : 1);
}
