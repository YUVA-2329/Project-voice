#!/usr/bin/env python
"""PROJECT VOICE — real end-to-end Conversation-mode WebSocket test against a running stack.

Drives one complete audio turn exactly as the browser does:

register → login (httpx, cookie jar) → upload a voice from the ZipVoice test WAVs and wait for
the worker → open ``ws://…/api/v1/conversation/ws?voice_id=…&engine=mirror`` with the session
cookie → ``{"type":"start"}`` → stream real speech (``evidence/generation_short.wav`` resampled to
16 kHz) as PCM16 binary frames of 40 ms, paced in real time → ``{"type":"stop"}`` → assert the
server answers with ``state`` transitions, ``transcript``, ``response``, ``audio_start``, binary
PCM frames and ``audio_end`` within the deadline → save the reply as
``evidence/conversation_reply.wav`` → transcribe it back with ``app.engine.realtime.Transcriber``
so the evidence shows the returned audio is intelligible speech.

Everything is logged to ``evidence/e2e_ws_log.txt`` plus a JSON summary.

Usage (stack running — see docs/LOCAL_DEVELOPMENT.md):

    python scripts/e2e_ws.py [--base http://localhost:8000] [--evidence evidence]
                             [--input evidence/generation_short.wav] [--timeout 120]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import soundfile as sf

REPO = Path(__file__).resolve().parents[1]
BACKEND = REPO / "backend"
TEST_WAVS = REPO / "models" / "zipvoice-distill" / "test_wavs"

INPUT_RATE = 16_000
FRAME_MS = 40
FRAME_SAMPLES = INPUT_RATE * FRAME_MS // 1000  # 640 samples = 1280 bytes


class E2EFailure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise E2EFailure(message)


class Evidence:
    def __init__(self, directory: Path) -> None:
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.dir / "e2e_ws_log.txt"
        self.log_path.write_text("")
        self.started = time.time()
        self.steps: list[dict[str, Any]] = []
        self.extra: dict[str, Any] = {}

    def log(self, line: str) -> None:
        text = f"[{time.time() - self.started:7.2f}s] {line}"
        print(text, flush=True)
        with self.log_path.open("a") as fh:
            fh.write(text + "\n")

    def step(self, name: str, started: float, ok: bool = True, detail: str = "") -> None:
        seconds = round(time.time() - started, 3)
        self.steps.append({"name": name, "ok": ok, "seconds": seconds, "detail": detail})
        self.log(f"{'✓' if ok else '✗'} {name} ({seconds:.2f}s){' — ' + detail if detail else ''}")

    def write_summary(self, *, ok: bool) -> None:
        payload = {
            "ok": ok,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.started)),
            "total_seconds": round(time.time() - self.started, 2),
            "steps": self.steps,
            **self.extra,
        }
        (self.dir / "e2e_ws_summary.json").write_text(json.dumps(payload, indent=2, default=str))


# --------------------------------------------------------------------------------------------
# HTTP side (register / login / voice)
# --------------------------------------------------------------------------------------------


class Client:
    def __init__(self, base: str) -> None:
        self.http = httpx.Client(base_url=base, timeout=60.0, follow_redirects=False)

    @property
    def csrf(self) -> str | None:
        return self.http.cookies.get("pv_csrf")

    def request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        headers = dict(kw.pop("headers", None) or {})
        if method in ("POST", "PATCH", "DELETE") and self.csrf:
            headers.setdefault("X-CSRF-Token", self.csrf)
        return self.http.request(method, path, headers=headers, **kw)


def expect(resp: httpx.Response, status: int, what: str) -> Any:
    if resp.status_code != status:
        raise E2EFailure(f"{what}: expected HTTP {status}, got {resp.status_code}: {resp.text[:600]}")
    return resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp


def prepare_voice(ev: Evidence, c: Client) -> dict[str, Any]:
    t = time.time()
    tag = uuid.uuid4().hex[:8]
    email, password = f"ws-{tag}@example.com", "correct horse battery staple"
    user = expect(
        c.request("POST", "/api/v1/auth/register", json={"email": email, "password": password, "display_name": "WS"}),
        201,
        "register",
    )["user"]
    expect(c.request("POST", "/api/v1/auth/login", json={"email": email, "password": password}), 200, "login")
    check("pv_access" in c.http.cookies and "pv_csrf" in c.http.cookies, "login did not set cookies")
    ev.step("register + login", t, detail=f"user_id={user['id']} email={email}")

    prompts = dict(line.split(" ", 1) for line in (TEST_WAVS / "prompt.txt").read_text().splitlines() if line.strip())
    wav = TEST_WAVS / "leijun-1.wav"
    t = time.time()
    with wav.open("rb") as fh:
        r = c.request(
            "POST",
            "/api/v1/voices",
            data={
                "name": "WS voice",
                "consent_confirmed": "true",
                "consent_text_version": "v1",
                "language_hint": "zh",
                "transcript": prompts[wav.name],
            },
            files={"file": (wav.name, fh, "audio/wav")},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
    voice = expect(r, 202, "upload voice")
    ev.step("upload voice", t, detail=f"voice_id={voice['id']} job_id={voice['job_id']}")

    t = time.time()
    deadline = t + 600
    while time.time() < deadline:
        voice = expect(c.request("GET", f"/api/v1/voices/{voice['id']}"), 200, "get voice")
        if voice["status"] in ("ready", "failed"):
            break
        time.sleep(0.5)
    ev.step("voice ready", t, ok=voice["status"] == "ready", detail=f"status={voice['status']} error={voice.get('error')}")
    check(voice["status"] == "ready", f"voice failed: {voice.get('error')}")
    return voice


# --------------------------------------------------------------------------------------------
# Audio helpers
# --------------------------------------------------------------------------------------------


def load_pcm16_16k(path: Path) -> tuple[bytes, float]:
    import librosa

    audio, rate = sf.read(path, dtype="float32", always_2d=True)
    mono = audio.mean(axis=1)
    if rate != INPUT_RATE:
        mono = librosa.resample(mono, orig_sr=rate, target_sr=INPUT_RATE)
    pcm = (np.clip(mono, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
    return pcm, len(mono) / INPUT_RATE


def transcribe_pcm(pcm: bytes, sample_rate: int, language: str | None = None) -> tuple[str, str | None, float]:
    """Transcribe returned PCM16 with the same realtime Transcriber the API uses."""
    import librosa

    sys.path.insert(0, str(BACKEND))
    os.environ.setdefault("PV_MODELS_DIR", str(REPO / "models"))
    from app.engine.realtime import Transcriber
    from app.engine.types import Language

    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    if sample_rate != INPUT_RATE:
        samples = librosa.resample(samples, orig_sr=sample_rate, target_sr=INPUT_RATE)
    t = time.perf_counter()
    text, lang = Transcriber.get().transcribe(
        np.ascontiguousarray(samples), Language(language) if language else None
    )
    return text, (str(lang.value) if lang else None), time.perf_counter() - t


# --------------------------------------------------------------------------------------------
# The WebSocket turn
# --------------------------------------------------------------------------------------------


async def run_turn(
    ev: Evidence, *, ws_url: str, cookie_header: str, pcm_in: bytes, timeout: float, strict: bool = True
) -> dict[str, Any]:
    """Drive one turn.  With ``strict=False`` a server ``error`` message ends the turn and is
    returned as ``{"error": …}`` instead of failing the run."""
    import websockets

    events: list[dict[str, Any]] = []
    states: list[str] = []
    audio_frames: list[bytes] = []
    result: dict[str, Any] = {}
    t0 = time.time()

    def note(evt: dict[str, Any]) -> None:
        events.append({"t": round(time.time() - t0, 3), **evt})

    async with websockets.connect(
        ws_url, additional_headers={"Cookie": cookie_header}, max_size=None, open_timeout=30
    ) as ws:
        ev.step("websocket connected", t0, detail=ws_url)

        first = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        note(first)
        check(first.get("type") == "state" and first.get("state") == "idle", f"expected idle state first, got {first}")
        states.append("idle")

        await ws.send(json.dumps({"type": "start"}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        note(msg)
        check(msg.get("type") == "state" and msg.get("state") == "listening", f"expected listening after start, got {msg}")
        states.append("listening")
        ev.step("start → listening", t0)

        # Stream the speech as 40 ms PCM16 frames, paced like a microphone. Any server message
        # that arrives meanwhile (e.g. VAD completing the utterance early) is collected.
        t_stream = time.time()
        frame_bytes = FRAME_SAMPLES * 2
        sent = 0

        async def pump_incoming() -> None:
            try:
                while True:
                    raw = await ws.recv()
                    if isinstance(raw, bytes):
                        audio_frames.append(raw)
                    else:
                        note(json.loads(raw))
            except asyncio.CancelledError:
                raise
            except Exception:
                return

        pump = asyncio.create_task(pump_incoming())
        for offset in range(0, len(pcm_in), frame_bytes):
            await ws.send(pcm_in[offset : offset + frame_bytes])
            sent += 1
            await asyncio.sleep(FRAME_MS / 1000.0)
        ev.step("streamed PCM16 frames", t_stream, detail=f"{sent} frames × {FRAME_MS} ms = {sent * FRAME_MS / 1000:.2f}s audio, {len(pcm_in)} bytes")
        await ws.send(json.dumps({"type": "stop"}))
        note({"type": "client", "sent": "stop"})

        # Wait for the full turn: transcript → response → audio_start → frames → audio_end.
        deadline = time.time() + timeout
        while time.time() < deadline:
            done_types = {e.get("type") for e in events}
            if "audio_end" in done_types:
                break
            if any(e.get("type") == "error" for e in events):
                break
            await asyncio.sleep(0.1)
        pump.cancel()
        try:
            await pump
        except (asyncio.CancelledError, Exception):
            pass

        # Give the trailing "listening" state a moment to arrive (it is sent after audio_end).
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                if isinstance(raw, bytes):
                    audio_frames.append(raw)
                else:
                    note(json.loads(raw))
        except Exception:
            pass

    errors = [e for e in events if e.get("type") == "error"]
    order = [e.get("type") if e.get("type") != "state" else f"state:{e.get('state')}" for e in events]
    if errors and not strict:
        return {"events": events, "order": order, "error": errors[0], "seconds": round(time.time() - t0, 2)}
    check(not errors, f"server reported error(s): {errors}")
    types = [e.get("type") for e in events]
    for required in ("transcript", "response", "audio_start", "audio_end"):
        check(required in types, f"missing '{required}' message; got {types}")
    states.extend(e["state"] for e in events if e.get("type") == "state" and e.get("state") not in ("idle",) and e["t"] > 0)
    transcript = next(e["text"] for e in events if e.get("type") == "transcript")
    response = next(e["text"] for e in events if e.get("type") == "response")
    audio_start = next(e for e in events if e.get("type") == "audio_start")
    check(len(audio_frames) > 0, "no binary audio frames received")
    check(transcript.strip() != "", "empty transcript")
    check(response == transcript, f"mirror engine must echo the transcript: {response!r} != {transcript!r}")

    result.update(
        {
            "events": events,
            "order": order,
            "transcript": transcript,
            "response": response,
            "sample_rate": int(audio_start["sample_rate"]),
            "frames": len(audio_frames),
            "pcm": b"".join(audio_frames),
            "seconds": round(time.time() - t0, 2),
        }
    )
    return result


# --------------------------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=os.environ.get("PV_E2E_BASE", "http://localhost:8000"))
    parser.add_argument("--evidence", default=str(REPO / "evidence"))
    parser.add_argument("--input", default=str(REPO / "evidence" / "generation_short.wav"))
    parser.add_argument("--timeout", type=float, default=120.0, help="seconds to wait for the complete turn")
    parser.add_argument("--language", default="en", help="language spoken in --input (pins Whisper for the strict turn)")
    args = parser.parse_args()

    ev = Evidence(Path(args.evidence))
    ok = False
    try:
        c = Client(args.base)
        health = expect(c.request("GET", "/api/v1/system/health"), 200, "health")
        check(health["checks"]["worker"]["status"] == "ok", f"no worker heartbeat: {health['checks']['worker']}")
        ev.log(f"health: {json.dumps(health['checks'])}")

        voice = prepare_voice(ev, c)

        t = time.time()
        pcm_in, seconds_in = load_pcm16_16k(Path(args.input))
        ev.step("input audio resampled to 16 kHz PCM16", t, detail=f"{args.input}: {seconds_in:.2f}s, {len(pcm_in)} bytes")

        cookie_header = "; ".join(f"{k}={v}" for k, v in c.http.cookies.items())
        ws_base = args.base.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_base}/api/v1/conversation/ws?voice_id={voice['id']}&engine=mirror"

        # Turn 0 — no language hint.  whisper-base must auto-detect the language of an 8 s
        # synthetic, Chinese-accented English clip; this documents what it does (it may pin a
        # supported language and complete the turn, or the server answers ``language_unsupported``
        # when the detected language is one no engine speaks — never garbage audio).
        t = time.time()
        turn0 = asyncio.run(
            run_turn(ev, ws_url=ws_url, cookie_header=cookie_header, pcm_in=pcm_in, timeout=args.timeout, strict=False)
        )
        if "error" in turn0:
            ev.step(
                "turn without language hint (auto-detect)",
                t,
                detail=f"server error {turn0['error'].get('code')}: {turn0['error'].get('message')} order={turn0['order']}",
            )
            check(turn0["error"].get("code") in ("language_unsupported", "no_speech"), f"unexpected error {turn0['error']}")
        else:
            ev.step(
                "turn without language hint (auto-detect)",
                t,
                detail=f"transcript={turn0['transcript']!r} reply={turn0['frames']} frames order={turn0['order']}",
            )
        ev.extra["turn_without_hint"] = {k: v for k, v in turn0.items() if k != "pcm"}

        # Turn 1 — the strict one: language pinned to the language actually spoken in the clip.
        ws_url = f"{ws_url}&language={args.language}"
        t = time.time()
        turn = asyncio.run(run_turn(ev, ws_url=ws_url, cookie_header=cookie_header, pcm_in=pcm_in, timeout=args.timeout))
        reply_seconds = len(turn["pcm"]) / 2 / turn["sample_rate"]
        ev.step(
            "full conversation turn",
            t,
            detail=(
                f"order={turn['order']} transcript={turn['transcript']!r} response={turn['response']!r} "
                f"reply={turn['frames']} frames, {turn['sample_rate']} Hz, {reply_seconds:.2f}s"
            ),
        )
        check(reply_seconds >= 1.0, f"reply audio too short: {reply_seconds:.2f}s")

        out = Path(args.evidence) / "conversation_reply.wav"
        samples = np.frombuffer(turn["pcm"], dtype="<i2")
        sf.write(out, samples, turn["sample_rate"], subtype="PCM_16")
        ev.log(f"    saved reply → {out} ({len(turn['pcm'])} bytes, {reply_seconds:.2f}s @ {turn['sample_rate']} Hz)")

        t = time.time()
        back_text, back_lang, asr_seconds = transcribe_pcm(turn["pcm"], turn["sample_rate"], args.language)
        ev.step(
            "round-trip transcription of reply (Transcriber)",
            t,
            ok=bool(back_text.strip()),
            detail=f"{back_text!r} language={back_lang} whisper={asr_seconds:.2f}s",
        )
        check(bool(back_text.strip()), "reply audio transcribed to nothing")

        # Word overlap between what was spoken into the socket and what came back.
        def words(s: str) -> set[str]:
            return {w.strip(".,!?;:'\"").lower() for w in s.split() if w.strip(".,!?;:'\"")}

        overlap = len(words(turn["transcript"]) & words(back_text)) / max(1, len(words(turn["transcript"])))
        ev.log(f"    word overlap(input transcript, reply transcript) = {overlap:.0%}")
        ev.extra.update(
            {
                "voice_id": voice["id"],
                "input_file": args.input,
                "language_hint": args.language,
                "input_seconds": round(seconds_in, 2),
                "message_order": turn["order"],
                "transcript_of_input": turn["transcript"],
                "response_text": turn["response"],
                "reply_sample_rate": turn["sample_rate"],
                "reply_frames": turn["frames"],
                "reply_seconds": round(reply_seconds, 2),
                "reply_file": str(out),
                "reply_transcript": back_text,
                "reply_language": back_lang,
                "word_overlap": round(overlap, 3),
                "events": turn["events"],
            }
        )
        ok = True
    except E2EFailure as exc:
        ev.log(f"✗ FAILED: {exc}")
    except Exception as exc:  # noqa: BLE001
        ev.log(f"✗ CRASHED: {type(exc).__name__}: {exc}")
        import traceback

        traceback.print_exc()
    ev.log(f"RESULT: {'PASS' if ok else 'FAIL'}")
    ev.write_summary(ok=ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
