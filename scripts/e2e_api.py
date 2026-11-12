#!/usr/bin/env python
"""PROJECT VOICE — real end-to-end API workflow against a running stack (no mocks, no pytest).

Exercises the whole product journey through HTTP exactly as the browser / an API client would:
register → login → CSRF → upload a voice (with and without a user transcript, so Whisper runs) →
wait for the worker → generate speech (short + long paragraph) → stream / range / download / signed
URL → preview → ownership isolation with a second user → second voice → rename → delete → consent
revoke / re-grant → API key → system endpoints → API restart persistence check.

Every step prints a line with its wall-clock duration; the generated WAVs, the log and a JSON
summary are written to ``evidence/``.

Usage (stack must be running — see docs/LOCAL_DEVELOPMENT.md):

    python scripts/e2e_api.py [--base http://localhost:8000] [--evidence evidence]
                              [--restart-cmd "/path/to/restart-api.sh"] [--skip-restart]
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import httpx

REPO = Path(__file__).resolve().parents[1]
TEST_WAVS = REPO / "models" / "zipvoice-distill" / "test_wavs"

SHORT_TEXT = (
    "Hello, this is my cloned voice speaking through Project Voice. Your voice, your words."
)
LONG_TEXT = (
    "Project Voice turns a short recording into a voice you can write for. First, you record "
    "about ten seconds of natural speech; the system trims silence, checks the loudness, and "
    "transcribes what you said. Then it keeps a processed reference, never the raw upload, for "
    "every later request! Does it sound like you? That depends on the recording: a quiet room, "
    "a steady distance from the microphone, and no music in the background make the biggest "
    "difference. Numbers such as 2026 or 3.5 are read out loud; abbreviations like Dr. and "
    "Mr. are expanded where the language rules know them. Long paragraphs are split into "
    "sentences, synthesised one by one, and joined with short pauses derived from the "
    "punctuation; the result is one continuous file. Finally, every file carries provenance "
    "metadata stating that it was generated, together with the generation identifier, so the "
    "origin of the audio is never in doubt."
)


# --------------------------------------------------------------------------------------------
# Evidence log
# --------------------------------------------------------------------------------------------


@dataclass
class Step:
    name: str
    ok: bool
    seconds: float
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class Evidence:
    def __init__(self, directory: Path) -> None:
        self.dir = directory
        self.dir.mkdir(parents=True, exist_ok=True)
        self.steps: list[Step] = []
        self.log_path = self.dir / "e2e_api_log.txt"
        self.log_path.write_text("")
        self.started = time.time()
        self.extra: dict[str, Any] = {}

    def log(self, line: str) -> None:
        stamp = f"[{time.time() - self.started:7.2f}s] "
        text = stamp + line
        print(text, flush=True)
        with self.log_path.open("a") as fh:
            fh.write(text + "\n")

    def step(self, name: str, started: float, ok: bool = True, detail: str = "", **data: Any) -> None:
        seconds = time.time() - started
        self.steps.append(Step(name=name, ok=ok, seconds=round(seconds, 3), detail=detail, data=data))
        mark = "[OK]" if ok else "[FAIL]"
        suffix = f" — {detail}" if detail else ""
        self.log(f"{mark} {name} ({seconds:.2f}s){suffix}")

    def write_summary(self, path: Path, *, ok: bool) -> None:
        payload = {
            "ok": ok,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(self.started)),
            "total_seconds": round(time.time() - self.started, 2),
            "steps": [asdict(s) for s in self.steps],
            **self.extra,
        }
        path.write_text(json.dumps(payload, indent=2, default=str))


class E2EFailure(AssertionError):
    pass


def check(condition: bool, message: str) -> None:
    if not condition:
        raise E2EFailure(message)


# --------------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------------


def wav_header(data: bytes) -> dict[str, Any]:
    """Parse a RIFF/WAVE header (PCM) and return rate / channels / bits / duration."""
    check(len(data) > 44 and data[:4] == b"RIFF" and data[8:12] == b"WAVE", "not a RIFF/WAVE file")
    pos = 12
    fmt: dict[str, Any] = {}
    data_len = None
    info_tags: dict[str, str] = {}
    while pos + 8 <= len(data):
        cid = data[pos : pos + 4]
        size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        body = data[pos + 8 : pos + 8 + size]
        if cid == b"fmt ":
            fmt_tag, channels, rate, _byte_rate, _align, bits = struct.unpack("<HHIIHH", body[:16])
            fmt = {"format_tag": fmt_tag, "channels": channels, "sample_rate": rate, "bits": bits}
        elif cid == b"data":
            data_len = size
        elif cid == b"LIST" and body[:4] == b"INFO":
            p = 4
            while p + 8 <= len(body):
                tag = body[p : p + 4].decode("ascii", "replace")
                tlen = struct.unpack("<I", body[p + 4 : p + 8])[0]
                info_tags[tag] = body[p + 8 : p + 8 + tlen].rstrip(b"\0").decode("utf-8", "replace")
                p += 8 + tlen + (tlen & 1)
        pos += 8 + size + (size & 1)
    check(bool(fmt) and data_len is not None, "WAV has no fmt/data chunk")
    bytes_per_sample = fmt["bits"] // 8 * fmt["channels"]
    duration = data_len / (fmt["sample_rate"] * bytes_per_sample)
    return {**fmt, "data_bytes": data_len, "duration_seconds": round(duration, 3), "info": info_tags}


class Client:
    """Cookie-session HTTP client that echoes the CSRF cookie on mutating requests."""

    def __init__(self, base: str, label: str) -> None:
        self.http = httpx.Client(base_url=base, timeout=60.0, follow_redirects=False)
        self.label = label
        self.user: dict[str, Any] | None = None

    @property
    def csrf(self) -> str | None:
        return self.http.cookies.get("pv_csrf")

    def _headers(self, method: str, headers: dict[str, str] | None) -> dict[str, str]:
        out = dict(headers or {})
        if method.upper() in ("POST", "PATCH", "PUT", "DELETE") and self.csrf and "Authorization" not in out:
            out.setdefault("X-CSRF-Token", self.csrf)
        return out

    def request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        headers = self._headers(method, kw.pop("headers", None))
        return self.http.request(method, path, headers=headers, **kw)

    def get(self, path: str, **kw: Any) -> httpx.Response:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw: Any) -> httpx.Response:
        return self.request("POST", path, **kw)

    def patch(self, path: str, **kw: Any) -> httpx.Response:
        return self.request("PATCH", path, **kw)

    def delete(self, path: str, **kw: Any) -> httpx.Response:
        return self.request("DELETE", path, **kw)


def expect(resp: httpx.Response, status: int, what: str) -> Any:
    if resp.status_code != status:
        body = resp.text[:600]
        raise E2EFailure(f"{what}: expected HTTP {status}, got {resp.status_code}: {body}")
    if resp.headers.get("content-type", "").startswith("application/json"):
        return resp.json()
    return resp


def error_code(resp: httpx.Response) -> str | None:
    try:
        return resp.json()["error"]["code"]
    except Exception:
        return None


# --------------------------------------------------------------------------------------------
# Workflow pieces
# --------------------------------------------------------------------------------------------


def register_and_login(ev: Evidence, c: Client, email: str, password: str, name: str) -> None:
    t = time.time()
    r = c.post("/api/v1/auth/register", json={"email": email, "password": password, "display_name": name})
    user = expect(r, 201, "register")["user"]
    c.user = user
    check("pv_access" in c.http.cookies and "pv_csrf" in c.http.cookies, "register did not set cookies")
    ev.step(f"register {c.label}", t, detail=f"user_id={user['id']} email={email}")

    t = time.time()
    r = c.post("/api/v1/auth/login", json={"email": email, "password": password})
    expect(r, 200, "login")
    ev.step(f"login {c.label}", t)

    t = time.time()
    r = c.get("/api/v1/auth/csrf")
    csrf = expect(r, 200, "csrf")["csrf_token"]
    check(c.csrf == csrf, "csrf token in body does not match pv_csrf cookie")
    ev.step(f"csrf {c.label}", t, detail=f"token_len={len(csrf)}")

    t = time.time()
    me = expect(c.get("/api/v1/users/me"), 200, "users/me")
    check(me["id"] == user["id"], "users/me returned another user")
    ev.step(f"users/me {c.label}", t)


def upload_voice(
    ev: Evidence,
    c: Client,
    *,
    wav: Path,
    name: str,
    transcript: str | None,
    language_hint: str = "auto",
) -> dict[str, Any]:
    t = time.time()
    data = {
        "name": name,
        "consent_confirmed": "true",
        "consent_text_version": "v1",
        "language_hint": language_hint,
    }
    if transcript is not None:
        data["transcript"] = transcript
    with wav.open("rb") as fh:
        r = c.post(
            "/api/v1/voices",
            data=data,
            files={"file": (wav.name, fh, "audio/wav")},
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )
    voice = expect(r, 202, f"upload voice {name}")
    check(voice["status"] == "processing", f"voice status after upload should be processing: {voice['status']}")
    check(voice["job_id"], "voice has no job_id")
    ev.step(
        f"upload voice '{name}' ({'with' if transcript else 'without'} transcript)",
        t,
        detail=f"voice_id={voice['id']} job_id={voice['job_id']} ref={voice['reference']}",
    )
    return voice


def wait_voice(ev: Evidence, c: Client, voice_id: str, *, timeout: float = 600.0) -> dict[str, Any]:
    t = time.time()
    stages: list[str] = []
    last: dict[str, Any] | None = None
    job_id = None
    deadline = t + timeout
    while time.time() < deadline:
        v = expect(c.get(f"/api/v1/voices/{voice_id}"), 200, "get voice")
        job_id = v.get("job_id")
        if job_id:
            j = c.get(f"/api/v1/jobs/{job_id}")
            if j.status_code == 200:
                prog = j.json().get("progress")
                if prog and prog != last:
                    last = prog
                    stage = f"{prog['stage']} {prog['current']}/{prog['total']}"
                    if not stages or stages[-1] != stage:
                        stages.append(stage)
                        ev.log(f"    voice job stage: {stage} (job {j.json()['status']})")
        if v["status"] in ("ready", "failed"):
            ev.step(
                f"voice {voice_id[:8]} processed",
                t,
                ok=v["status"] == "ready",
                detail=f"status={v['status']} stages={stages} error={v.get('error')}",
                stages=stages,
                status=v["status"],
            )
            check(v["status"] == "ready", f"voice failed: {v.get('error')}")
            return v
        time.sleep(0.5)
    raise E2EFailure(f"voice {voice_id} did not finish within {timeout}s")


def create_generation(ev: Evidence, c: Client, body: dict[str, Any], label: str) -> dict[str, Any]:
    t = time.time()
    r = c.post("/api/v1/generations", json=body)
    gen = expect(r, 202, f"create generation ({label})")
    check(gen["status"] == "queued", f"new generation should be queued, got {gen['status']}")
    ev.step(f"POST /generations ({label})", t, detail=f"generation_id={gen['id']} chars={len(body['text'])}")
    return gen


def wait_generation(ev: Evidence, c: Client, gen_id: str, *, timeout: float = 900.0) -> dict[str, Any]:
    t = time.time()
    progress_seen: list[dict[str, Any]] = []
    deadline = t + timeout
    while time.time() < deadline:
        g = expect(c.get(f"/api/v1/generations/{gen_id}"), 200, "get generation")
        p = g.get("progress")
        if p and (not progress_seen or progress_seen[-1] != p):
            progress_seen.append(p)
            ev.log(f"    progress: {json.dumps(p)} status={g['status']}")
        if g["status"] in ("completed", "failed", "cancelled"):
            m = g.get("metrics") or {}
            ev.step(
                f"generation {gen_id[:8]} finished",
                t,
                ok=g["status"] == "completed",
                detail=(
                    f"status={g['status']} engine={g.get('engine_id')} language={g.get('language')} "
                    f"chunks={m.get('chunks')} inference={m.get('inference_seconds')}s "
                    f"rtf={m.get('real_time_factor')} device={m.get('device')} "
                    f"duration={(g.get('output') or {}).get('duration_seconds')}s error={g.get('error')}"
                ),
                progress_seen=progress_seen,
                metrics=m,
                output=g.get("output"),
                status=g["status"],
            )
            check(g["status"] == "completed", f"generation failed: {g.get('error')}")
            return g
        time.sleep(0.5)
    raise E2EFailure(f"generation {gen_id} did not finish within {timeout}s")


def fetch_audio(ev: Evidence, c: Client, gen: dict[str, Any], save_to: Path) -> dict[str, Any]:
    gid = gen["id"]
    t = time.time()
    r = c.get(f"/api/v1/generations/{gid}/audio")
    check(r.status_code == 200, f"audio: expected 200, got {r.status_code} {r.text[:200]}")
    ctype = r.headers.get("content-type", "")
    check(ctype.startswith("audio/wav") or ctype.startswith("audio/x-wav"), f"audio content-type {ctype}")
    check(len(r.content) > 0, "audio body empty")
    hdr = wav_header(r.content)
    save_to.write_bytes(r.content)
    reported = (gen.get("output") or {}).get("duration_seconds")
    check(
        reported is not None and abs(hdr["duration_seconds"] - reported) < 0.05,
        f"WAV duration {hdr['duration_seconds']} != reported {reported}",
    )
    ev.step(
        f"GET audio {gid[:8]}",
        t,
        detail=(
            f"{len(r.content)} bytes, {hdr['sample_rate']} Hz, {hdr['channels']} ch, "
            f"{hdr['bits']}-bit, {hdr['duration_seconds']}s, provenance={hdr['info']} → {save_to.name}"
        ),
        bytes=len(r.content),
        wav=hdr,
        saved=str(save_to),
    )

    t = time.time()
    r = c.get(f"/api/v1/generations/{gid}/audio", headers={"Range": "bytes=0-1023"})
    check(r.status_code == 206, f"range: expected 206, got {r.status_code}")
    check(len(r.content) == 1024, f"range body {len(r.content)} bytes")
    check(r.headers.get("content-range", "").startswith("bytes 0-1023/"), f"content-range {r.headers.get('content-range')}")
    ev.step(f"GET audio Range {gid[:8]}", t, detail=f"206 {r.headers.get('content-range')}")

    t = time.time()
    r = c.get(f"/api/v1/generations/{gid}/audio", params={"download": "1"})
    check(r.status_code == 200, f"download: {r.status_code}")
    cd = r.headers.get("content-disposition", "")
    check("attachment" in cd and f"project-voice-{gid}" in cd, f"content-disposition {cd!r}")
    ev.step(f"GET audio?download=1 {gid[:8]}", t, detail=cd)

    t = time.time()
    r = c.get(f"/api/v1/generations/{gid}/audio-url")
    signed = expect(r, 200, "audio-url")
    url = signed["url"]
    check("/api/v1/media/" in url, f"signed url {url}")
    anon = httpx.Client(base_url=str(c.http.base_url), timeout=60.0)  # no cookies: token is the credential
    path = url if url.startswith("/") else httpx.URL(url).raw_path.decode()
    r2 = anon.get(path)
    check(r2.status_code == 200, f"media token fetch: {r2.status_code} {r2.text[:200]}")
    check(r2.content == save_to.read_bytes(), "media token bytes differ from /audio bytes")
    ev.step(f"audio-url + fetch {gid[:8]}", t, detail=f"expires_at={signed['expires_at']} bytes={len(r2.content)}")
    return hdr


def restart_api(ev: Evidence, cmd: str, base: str) -> None:
    t = time.time()
    subprocess.run(cmd, shell=True, check=True)  # noqa: S602 — operator-supplied command
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base}/api/v1/system/health", timeout=3.0)
            if r.status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    else:
        raise E2EFailure("API did not come back after restart")
    ev.step("restart API process", t, detail=cmd)


# --------------------------------------------------------------------------------------------
# Main workflow
# --------------------------------------------------------------------------------------------


def run(args: argparse.Namespace, ev: Evidence) -> bool:
    base = args.base.rstrip("/")
    run_id = uuid.uuid4().hex[:8]
    ev.log(f"PROJECT VOICE E2E API run {run_id} against {base}")

    # -- preflight ---------------------------------------------------------------------------
    t = time.time()
    health = expect(httpx.get(f"{base}/api/v1/system/health", timeout=10), 200, "health")
    check(health["status"] == "ok", f"health status {health['status']}: {health['checks']}")
    check(health["checks"]["worker"]["status"] == "ok", f"worker check: {health['checks']['worker']}")
    ev.step("GET /system/health", t, detail=json.dumps(health["checks"]))

    a = Client(base, "A")
    b = Client(base, "B")
    password = "correct-horse-battery-" + run_id
    register_and_login(ev, a, f"alice-{run_id}@example.com", password, "Alice")

    t = time.time()
    models = expect(a.get("/api/v1/system/models"), 200, "system/models")
    zip_model = next((m for m in models if m["id"] == "zipvoice_distill"), None)
    check(zip_model is not None and zip_model["available"], f"zipvoice_distill not available: {models}")
    ev.step(
        "GET /system/models",
        t,
        detail=", ".join(f"{m['id']}={'available' if m['available'] else 'unavailable'}" for m in models),
    )

    prompt_lines = (TEST_WAVS / "prompt.txt").read_text(encoding="utf-8").splitlines()
    prompts = {ln.split(" ", 1)[0]: ln.split(" ", 1)[1].strip() for ln in prompt_lines if " " in ln}

    # -- voice 1: user-supplied transcript ------------------------------------------------
    voice1 = upload_voice(
        ev, a, wav=TEST_WAVS / "leijun-1.wav", name="Lei", transcript=prompts["leijun-1.wav"]
    )
    voice1 = wait_voice(ev, a, voice1["id"])
    check(voice1["transcript"], "voice1 transcript missing")
    check(voice1["transcript_source"] == "user", f"voice1 transcript_source {voice1['transcript_source']}")
    check(voice1["engine_id"] == "zipvoice_distill", f"voice1 engine {voice1['engine_id']}")
    check(voice1["reference"]["speech_seconds"], "voice1 speech_seconds missing")
    ev.log(
        f"    voice1 language={voice1['language']} detected={voice1['detected_language']} "
        f"speech={voice1['reference']['speech_seconds']}s quality={voice1['quality']}"
    )

    # -- voice 1b: no transcript → Whisper --------------------------------------------------
    voice1b = upload_voice(ev, a, wav=TEST_WAVS / "leijun-1.wav", name="Lei (auto transcript)", transcript=None)
    voice1b = wait_voice(ev, a, voice1b["id"])
    check(voice1b["transcript"], "Whisper transcript missing")
    check(voice1b["transcript_source"] == "auto", f"voice1b transcript_source {voice1b['transcript_source']}")
    ev.log(f"    whisper transcript: {voice1b['transcript']!r} detected_language={voice1b['detected_language']}")
    ev.extra["whisper_transcript"] = voice1b["transcript"]
    ev.extra["user_transcript"] = prompts["leijun-1.wav"]

    # -- list voices ------------------------------------------------------------------------
    t = time.time()
    page = expect(a.get("/api/v1/voices"), 200, "list voices")
    ids = {v["id"] for v in page["items"]}
    check({voice1["id"], voice1b["id"]} <= ids and page["total"] == 2, f"voice list {page['total']} {ids}")
    ev.step("GET /voices", t, detail=f"total={page['total']}")

    # -- generation 1 (short, auto language) -----------------------------------------------
    gen1 = create_generation(
        ev, a, {"voice_id": voice1["id"], "text": SHORT_TEXT, "language": "auto"}, "short, auto"
    )
    gen1 = wait_generation(ev, a, gen1["id"])
    check(gen1["language"] == "en", f"detected language {gen1['language']}")
    hdr1 = fetch_audio(ev, a, gen1, ev.dir / "generation_short.wav")

    # -- generation 2 (long paragraph, fast) ----------------------------------------------
    check(len(LONG_TEXT) >= 600, "long text too short for the test")
    gen2 = create_generation(
        ev, a, {"voice_id": voice1["id"], "text": LONG_TEXT, "language": "auto", "quality": "fast"}, "long, fast"
    )
    gen2 = wait_generation(ev, a, gen2["id"])
    check(gen2["metrics"]["chunks"] > 1, f"long text produced {gen2['metrics']['chunks']} chunk(s)")
    hdr2 = fetch_audio(ev, a, gen2, ev.dir / "generation_long.wav")

    # -- list generations -------------------------------------------------------------------
    t = time.time()
    glist = expect(a.get("/api/v1/generations"), 200, "list generations")
    check(glist["total"] >= 2 and glist["items"][0]["id"] == gen2["id"], "generation list order/total")
    filtered = expect(a.get("/api/v1/generations", params={"voice_id": voice1["id"], "status": "completed"}), 200, "filter")
    check(filtered["total"] >= 2, "filtered generation list")
    ev.step("GET /generations (+filters)", t, detail=f"total={glist['total']} filtered={filtered['total']}")

    # -- preview ---------------------------------------------------------------------------
    t = time.time()
    r = a.post(f"/api/v1/voices/{voice1['id']}/preview", json={})
    preview = expect(r, 202, "preview")
    ev.step("POST /voices/{id}/preview", t, detail=f"generation_id={preview['id']} text={preview['text'][:60]!r}")
    preview = wait_generation(ev, a, preview["id"])
    fetch_audio(ev, a, preview, ev.dir / "generation_preview.wav")
    v = expect(a.get(f"/api/v1/voices/{voice1['id']}"), 200, "voice after preview")
    check(v["preview_generation_id"] == preview["id"], "preview_generation_id not recorded on the voice")

    # -- ownership isolation ---------------------------------------------------------------
    register_and_login(ev, b, f"bob-{run_id}@example.com", password, "Bob")
    t = time.time()
    r = b.get(f"/api/v1/voices/{voice1['id']}")
    check(r.status_code == 404 and error_code(r) == "voice_not_found", f"B→A voice: {r.status_code} {r.text[:100]}")
    r = b.get(f"/api/v1/generations/{gen1['id']}/audio")
    check(r.status_code == 404, f"B→A audio: {r.status_code}")
    r = b.get(f"/api/v1/generations/{gen1['id']}")
    check(r.status_code == 404, f"B→A generation: {r.status_code}")
    r = b.post("/api/v1/generations", json={"voice_id": voice1["id"], "text": "hi there"})
    check(r.status_code == 404, f"B generating with A's voice: {r.status_code}")
    page_b = expect(b.get("/api/v1/voices"), 200, "B voices")
    check(page_b["total"] == 0, "B sees voices")
    ev.step("ownership isolation (B → A resources)", t, detail="voice 404, generation 404, audio 404, generate 404, list empty")

    # -- CSRF enforcement ------------------------------------------------------------------
    t = time.time()
    r = a.http.post("/api/v1/voices/%s/consent/revoke" % voice1b["id"])  # bypass helper: no header
    check(r.status_code == 403 and error_code(r) == "csrf_invalid", f"missing CSRF: {r.status_code} {error_code(r)}")
    ev.step("CSRF enforced on cookie mutation", t, detail="403 csrf_invalid without X-CSRF-Token")

    # -- second voice -----------------------------------------------------------------------
    voice2 = upload_voice(
        ev, a, wav=TEST_WAVS / "news-female.wav", name="Newsreader", transcript=prompts["news-female.wav"], language_hint="zh"
    )
    voice2 = wait_voice(ev, a, voice2["id"])
    t = time.time()
    page = expect(a.get("/api/v1/voices"), 200, "list voices")
    check(page["total"] == 3 and {v["id"] for v in page["items"]} == {voice1["id"], voice1b["id"], voice2["id"]}, "3 voices expected")
    ev.step("GET /voices (3 voices listed separately)", t, detail=", ".join(f"{v['name']}={v['status']}" for v in page["items"]))

    # -- rename ------------------------------------------------------------------------------
    t = time.time()
    r = a.patch(f"/api/v1/voices/{voice2['id']}", json={"name": "Newsreader (renamed)"})
    renamed = expect(r, 200, "rename")
    check(renamed["name"] == "Newsreader (renamed)", "rename did not apply")
    ev.step("PATCH /voices/{id} rename", t, detail=renamed["name"])

    # -- delete voice 1 → 404; its generations keep the name snapshot ----------------------
    t = time.time()
    r = a.delete(f"/api/v1/voices/{voice1['id']}")
    check(r.status_code == 204, f"delete voice: {r.status_code} {r.text[:200]}")
    r = a.get(f"/api/v1/voices/{voice1['id']}")
    check(r.status_code == 404, f"deleted voice still visible: {r.status_code}")
    r = a.get(f"/api/v1/voices/{voice1['id']}/reference-audio")
    check(r.status_code == 404, f"deleted voice reference still served: {r.status_code}")
    g = expect(a.get(f"/api/v1/generations/{gen1['id']}"), 200, "generation after voice delete")
    check(g["voice_id"] is None, f"generation voice_id should be null after delete: {g['voice_id']}")
    check(g["voice_name"] == "Lei", f"voice_name snapshot {g['voice_name']!r}")
    r = a.get(f"/api/v1/generations/{gen1['id']}/audio")
    check(r.status_code == 200, "generation audio must survive voice deletion")
    glist = expect(a.get("/api/v1/generations"), 200, "list after delete")
    check(any(x["id"] == gen1["id"] for x in glist["items"]), "generation missing from list after voice delete")
    storage_dir = Path(args.storage_dir) if args.storage_dir else None
    if storage_dir and storage_dir.exists():
        leftovers = list(storage_dir.glob(f"users/{a.user['id']}/voices/{voice1['id']}/**/*"))
        check(not [p for p in leftovers if p.is_file()], f"voice objects not removed from storage: {leftovers}")
        ev.log("    storage objects for deleted voice removed from disk")
    ev.step("DELETE /voices/{id} + history retained", t, detail=f"voice 404; generation voice_id=null voice_name={g['voice_name']!r}")

    # -- consent revoke / re-grant -----------------------------------------------------------
    t = time.time()
    v = expect(a.post(f"/api/v1/voices/{voice2['id']}/consent/revoke"), 200, "revoke")
    check(v["status"] == "consent_revoked" and v["consent"]["revoked_at"], f"revoke status {v['status']}")
    r = a.post("/api/v1/generations", json={"voice_id": voice2["id"], "text": "这是一个测试。", "language": "zh"})
    check(r.status_code == 403 and error_code(r) == "consent_required", f"revoked voice generation: {r.status_code} {error_code(r)}")
    ev.step("consent revoke → generation 403 consent_required", t)
    t = time.time()
    v = expect(
        a.post(f"/api/v1/voices/{voice2['id']}/consent", json={"consent_confirmed": True, "consent_text_version": "v1"}),
        200,
        "re-grant",
    )
    check(v["status"] == "ready" and v["consent"]["revoked_at"] is None, f"re-grant status {v['status']}")
    gen3 = create_generation(ev, a, {"voice_id": voice2["id"], "text": "各位听众，晚上好。这是一次语音克隆测试。", "language": "zh"}, "zh after re-grant")
    gen3 = wait_generation(ev, a, gen3["id"])
    check(gen3["language"] == "zh", f"gen3 language {gen3['language']}")
    hdr3 = fetch_audio(ev, a, gen3, ev.dir / "generation_zh.wav")
    ev.step("consent re-grant → generation works", t, detail=f"gen {gen3['id'][:8]} {hdr3['duration_seconds']}s")

    # -- API key -----------------------------------------------------------------------------
    t = time.time()
    created = expect(a.post("/api/v1/api-keys", json={"name": "e2e"}), 201, "create api key")
    secret = created["secret"]
    check(secret.startswith("pv_live_"), f"api key prefix {secret[:10]}")
    anon = httpx.Client(base_url=base, timeout=30.0)
    r = anon.get("/api/v1/voices", headers={"Authorization": f"Bearer {secret}"})
    page = expect(r, 200, "voices via api key")
    check(page["total"] == 2, f"api key voice list total {page['total']}")
    r = anon.post(
        "/api/v1/generations",
        headers={"Authorization": f"Bearer {secret}"},
        json={"voice_id": voice2["id"], "text": "测试。", "language": "zh"},
    )
    check(r.status_code == 202, f"api key POST without CSRF should work: {r.status_code} {r.text[:200]}")
    gen_key = r.json()
    r = anon.get("/api/v1/voices", headers={"Authorization": "Bearer pv_live_invalid"})
    check(r.status_code == 401, f"invalid api key: {r.status_code}")
    keys = expect(a.get("/api/v1/api-keys"), 200, "list keys")
    check(any(k["id"] == created["api_key"]["id"] for k in keys), "api key not listed")
    ev.step("API key: create, Bearer GET /voices, Bearer POST /generations (no CSRF), invalid → 401", t, detail=f"prefix={created['api_key']['prefix']}")
    wait_generation(ev, a, gen_key["id"])

    # -- system / audit ----------------------------------------------------------------------
    t = time.time()
    metrics = expect(a.get("/api/v1/system/metrics"), 200, "metrics")
    check(metrics["workers"] and metrics["generations_24h"]["completed"] >= 4, f"metrics {metrics}")
    langs = expect(a.get("/api/v1/system/languages"), 200, "languages")
    en = next(x for x in langs if x["code"] == "en")
    zip_en = next(e for e in en["engines"] if e["engine_id"] == "zipvoice_distill")
    check(zip_en["cloning"] and zip_en["verified"] in ("verified", "unverified"), f"languages en {zip_en}")
    hw = expect(a.get("/api/v1/system/hardware"), 200, "hardware")
    audit = expect(a.get("/api/v1/audit", params={"limit": 100}), 200, "audit")
    actions = {e["action"] for e in audit["items"]}
    for needed in ("auth.login", "voice.created", "voice.deleted", "consent.revoked", "generation.created", "api_key.created"):
        check(any(x.startswith(needed.split(".")[0]) for x in actions), f"audit missing {needed}: {sorted(actions)}")
    ev.step(
        "GET /system/metrics, /system/languages, /system/hardware, /audit",
        t,
        detail=(
            f"workers={len(metrics['workers'])} gen24h={metrics['generations_24h']} voices={metrics['voices_total']} "
            f"device={hw['device']} cpu={hw['cpu_cores']} audit_total={audit['total']} actions={sorted(actions)}"
        ),
    )
    ev.extra["metrics"] = metrics
    ev.extra["audit_actions"] = sorted(actions)

    # -- persistence across API restart ----------------------------------------------------
    if not args.skip_restart and args.restart_cmd:
        restart_api(ev, args.restart_cmd, base)
        t = time.time()
        page = expect(a.get("/api/v1/voices"), 200, "voices after restart")
        glist = expect(a.get("/api/v1/generations"), 200, "generations after restart")
        check(page["total"] == 2 and glist["total"] >= 5, f"after restart voices={page['total']} gens={glist['total']}")
        r = a.get(f"/api/v1/generations/{gen2['id']}/audio")
        check(r.status_code == 200 and len(r.content) == hdr2["data_bytes"] + (len(r.content) - hdr2["data_bytes"]), "audio after restart")
        ev.step("persistence after API restart", t, detail=f"voices={page['total']} generations={glist['total']} (session cookie still valid)")
    else:
        ev.log("    (API restart check skipped)")

    # -- logout ------------------------------------------------------------------------------
    t = time.time()
    r = a.post("/api/v1/auth/logout")
    check(r.status_code == 204, f"logout {r.status_code}")
    r = a.get("/api/v1/users/me")
    check(r.status_code == 401, f"after logout users/me {r.status_code}")
    ev.step("logout revokes the session", t)

    ev.extra["generations"] = {
        "short": {"id": gen1["id"], "metrics": gen1["metrics"], "wav": hdr1},
        "long": {"id": gen2["id"], "metrics": gen2["metrics"], "wav": hdr2},
        "zh": {"id": gen3["id"], "metrics": gen3["metrics"], "wav": hdr3},
    }
    ev.extra["voices"] = {
        "voice1_user_transcript": {k: voice1[k] for k in ("id", "language", "detected_language", "engine_id", "reference", "quality")},
        "voice1b_whisper": {k: voice1b[k] for k in ("id", "language", "detected_language", "transcript", "reference")},
        "voice2": {k: voice2[k] for k in ("id", "language", "detected_language", "reference")},
    }
    ev.extra["user_a_id"] = a.user["id"]
    ev.extra["voice2_id"] = voice2["id"]
    ev.extra["credentials_for_followup"] = {"email": f"alice-{run_id}@example.com", "password": password}
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base", default=os.environ.get("PV_E2E_BASE", "http://localhost:8000"))
    parser.add_argument("--evidence", default=str(REPO / "evidence"))
    parser.add_argument("--storage-dir", default=os.environ.get("PV_STORAGE_LOCAL_DIR", str(REPO / "storage")))
    parser.add_argument("--restart-cmd", default=os.environ.get("PV_E2E_RESTART_CMD"), help="shell command that restarts the API")
    parser.add_argument("--skip-restart", action="store_true")
    args = parser.parse_args()
    ev = Evidence(Path(args.evidence))
    ok = False
    try:
        ok = run(args, ev)
    except E2EFailure as exc:
        ev.log(f"[FAIL] E2E FAILED: {exc}")
        ev.extra["failure"] = str(exc)
    except httpx.HTTPError as exc:
        ev.log(f"[FAIL] E2E transport error: {exc!r}")
        ev.extra["failure"] = repr(exc)
    finally:
        ev.log("RESULT: PASS" if ok else "RESULT: FAIL")
        ev.write_summary(ev.dir / "e2e_api_summary.json", ok=ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
