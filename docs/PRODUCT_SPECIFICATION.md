# Product specification

> **PROJECT VOICE** — Your voice. Your words.
> Record once, speak anything. A personal voice-cloning and speech-synthesis product.

This document describes what the product does from the user's side: the journeys, the three
modes plus Conversation mode, every screen, the hard limits, and — honestly — which languages
work today and which do not. Technical references: `docs/ARCHITECTURE.md`,
`docs/API_DOCUMENTATION.md`, `docs/DESIGN.md`, `docs/LANGUAGE_MATRIX.md`, `docs/SECURITY.md`.

---

## 1. Who it is for

A person who wants *their own* voice to read text aloud: a creator narrating drafts, someone
preserving a voice, a developer who wants a clean API for speech in a voice they are allowed to
use. It is **not** a celebrity-voice toy: every voice is tied to a consent record and the
account that created it (§7).

## 2. Core journeys

### J1 — Create a voice (first run, ≈ 1 minute)
1. Register (e-mail + password ≥ 10 chars) → land on `/app`, which is empty and says
   *Let's create your voice.*
2. `/app/voices/create` wizard: **record** 10–20 s in the browser (live level meter, re-take)
   **or upload** a file (`wav mp3 m4a flac ogg webm`, ≤ 25 MB, 3–120 s).
3. Name it (1–60 chars); optionally pick a language hint and type what was said (otherwise the
   system transcribes it).
4. Tick the **consent attestation** (*this is my voice, or I have the speaker's explicit
   permission*). The button stays disabled until it is ticked.
5. Submit → the voice shows *processing* with real stage names (decode → analyse → trim →
   transcribe → validate → fingerprint; 1–3 s on CPU). Then *Your voice is ready.* with the
   detected language, the transcript (editable), and quality notes (noise, clipping, too short)
   when relevant.
6. A **preview** sentence in the voice's language is offered (*Hello! This is my voice. Every
   word you hear was generated from a short recording.*).

### J2 — Say something (Simple mode, the daily loop)
`/app`: pick a voice (or the only one is pre-selected) → type → **Run** (`⌘/Ctrl+Enter`) →
progress with real values (*synthesising sentence 3 of 7*) → inline player with scrubber,
download, regenerate. On CPU an 8-second sentence takes ~5 s; a paragraph ~0.5× its spoken
length (see §8).

### J3 — Find it again
`/app/history`: newest first, filter by voice and status, play/download/delete, copy a
share link that expires after an hour. History survives voice deletion (the voice name is kept).

### J4 — Change your mind about a voice
`/app/voices`: rename, correct the transcript, **revoke consent** (the voice is kept but can no
longer be used until re-granted), or **delete** (recordings and derived files are removed for
real; past generations stay in history).

### J5 — Talk to your voice (Conversation mode)
`/app/conversation`: choose a voice and an engine, press and hold / toggle the microphone,
speak; after a pause the system transcribes what you said and answers in your cloned voice —
either **mirroring** your words back (always available) or via a **language model** when the
operator has configured one. Turn-based, labelled as such; barge-in stops playback.

### J6 — Use it from code (Developer mode)
`/app/developer`: create an API key (shown once), see the exact `curl` for the same journey
(`POST /voices`, `POST /generations`, poll, `GET …/audio`), inspect model availability,
hardware, queue depth and recent audit events.

## 3. The three modes (+ Conversation)

| | Simple | Advanced | Developer |
|---|---|---|---|
| Who | everyone | people who want control | integrators |
| Screen | `/app` — one composer, one Run button | `/app/advanced` — composer + controls | `/app/developer` |
| Controls | voice, text | + language (auto/explicit), engine, speed 0.5–2.0×, quality fast/balanced/high, output wav/mp3/flac, chunk/pause behaviour visible | API keys, endpoint reference, model/hardware/queue status, audit |
| Defaults | from Settings | editable per request | n/a |
| Visible metrics | duration | + inference time, real-time factor, device, chunks, peak level | everything in the API |

**Conversation mode** is a fourth surface rather than a mode: it has its own route and a live
WebSocket; it is turn-based (listen → think → speak), not full-duplex, and the UI says so.

## 4. Screens

| Route | Purpose | Key states |
|---|---|---|
| `/` | Introduction: mark draws in, headline, one CTA (≤ 2.2 s, respects reduced motion) | — |
| `/register`, `/login` | account | validation and rate-limit errors in plain language |
| `/app` | Simple mode composer | no voice yet (empty state → Create) · ready · running (stage text) · result · error with next step |
| `/app/voices` | library: cards with status dot, language, duration, created | empty · processing · ready · failed (reason) · consent revoked |
| `/app/voices/create` | wizard: record/upload → name/details → consent → processing | mic permission denied · file rejected (why) · too short/long |
| `/app/history` | generations list + player | empty · filters · share link copied · expired link |
| `/app/advanced` | composer with full controls | language unsupported for voice/engine (shows what *would* work) |
| `/app/developer` | keys, endpoints, model status, hardware, queue, audit | engine unavailable (reason + fix) |
| `/app/conversation` | live turn-based conversation | idle · listening · thinking · speaking · reconnecting · error (no speech, language unsupported, synthesis timeout) |
| `/app/settings` | default language, engine, output format, speed, theme (system/light/dark), mode; password; delete account | — |

Design rules (`docs/DESIGN.md`): warm paper surfaces, graphite ink, a single red-orange accent
reserved for Run / active voice / live recording; Instrument Serif display, Geist Sans UI, Geist
Mono for ids and numbers; hairlines not shadows; no dashboards in Simple mode; WCAG AA.

## 5. Settings and defaults

`default_language` (`auto` or a code), `default_engine` (auto), `output_format` (`wav`),
`speed` (1.0), `theme` (`system`), `mode` (`simple`). Advanced-mode choices override per request.

## 6. Limits (enforced server-side, surfaced in the UI)

| What | Limit | Error |
|---|---|---|
| Reference upload | `wav mp3 m4a flac ogg webm`; ≤ 25 MB; decoded 3–120 s; a 3–30 s speech window is extracted (12 s preferred) | `unsupported_file_type`, `file_too_large`, `audio_too_short/long`, `invalid_audio` |
| Voice name | 1–60 chars | validation |
| Text per generation | 1–5000 chars after normalisation | `text_too_long` |
| Speed | 0.5–2.0× | validation |
| Rate limits | auth 10/min per IP · uploads 20/min · generations 30/min · other 300/min | `429` + `Retry-After` |
| API keys | ≤ 25 active per account | `too_many_api_keys` |
| Share links | expire after 1 h (configurable) | `410` |
| Conversation | 30 s per utterance, 30 s to transcribe/respond, 60 s to synthesise, 300 s idle, 600 chars per turn | WebSocket error / close `4008` |
| Job timeouts | voice 15 min, generation 30 min | job `failed` |

## 7. Trust rules the product never bends

* **No consent, no voice.** The attestation is stored with time, IP and user agent, can be
  revoked, and blocks generation while revoked. The product cannot verify the attestation is
  true — it makes it explicit and attributable (`docs/SECURITY.md` §12).
* **Your data is yours.** Every object is owned; others get `404`. Deletion removes files.
* **Everything generated is labelled.** Output files carry provenance metadata naming PROJECT
  VOICE and the generation id. This is metadata, not a watermark; stripping it is trivial, and the
  UI's download dialog says so in one line.
* **No invented progress or quality.** Progress numbers come from the pipeline; language status
  (*verified / unverified / unavailable*) comes from real inference runs; the UI never claims an
  engine works until it has.

## 8. What it sounds like and how fast it is (today)

The shipped, verified engine is **ZipVoice-distill** (zero-shot, reference-conditioned flow
matching, 24 kHz). Cross-lingual: a Chinese reference can speak English and vice-versa, with the
speaker's accent. Whisper-base word overlap on English output was 44–100 % across samples (82 %
in the conversation E2E), 91 % on Chinese — intelligible, recognisably the speaker, not studio
quality. On a 2-vCPU machine without GPU: *fast* quality ≈ 0.5–0.6× real time for English (8.5 s
of speech in 5 s), *balanced* ≈ 1.1×, *high* ≈ 1.7×; Chinese roughly double. A GPU worker
changes the numbers, not the behaviour.

## 9. Languages — honestly

| Language | Status today | Why / what changes it |
|---|---|---|
| **English** `en` | **Works — verified** with real inference (ZipVoice) | — |
| **Chinese (Mandarin)** `zh` | **Works — verified** (ZipVoice) | — |
| Telugu `te` — the product's first-priority language | **Not available yet** | Depends entirely on **IndicF5** (`ai4bharat/IndicF5`), whose weights are gated on Hugging Face and could not be fetched where this was built. Operator action: accept the licence, set `PV_HF_TOKEN`, download, restart the worker → status becomes *unverified* until a real check runs. The UI shows the exact reason and does not offer Telugu until then. |
| Hindi `hi` | Not available yet | IndicF5 (above) or the F5-Hindi checkpoint (`--f5tts hindi`, CC-BY-4.0) |
| Kannada `kn`, Tamil `ta`, Malayalam `ml` | Not available yet | IndicF5 only |
| Bengali, Gujarati, Marathi, Odia, Punjabi, Assamese | Spoken by IndicF5 but **not exposed** in the product's language list yet | would need `Language` enum + script detection + UI entries |
| Anything else (Japanese, Spanish, French, …) | **Not supported** | no integrated engine claims them; requests return `language_unsupported` with the list of engines that would help |

Also honest: whisper-base (the transcription model) auto-detects language unreliably on short or
accented clips — in testing it labelled a synthetic English sentence as Japanese. Where the user
knows the language, the UI should let them pin it (voice language hint, generation language,
conversation language), and the server refuses to synthesise text in a language no engine speaks
rather than produce gibberish.

Optional F5-TTS checkpoints (OpenF5 Apache-2.0 for English; SWivid v1 CC-BY-NC-4.0 for en+zh,
*non-commercial*) are supported by the adapter code but not bundled; `docs/MODEL_SETUP.md`.
XTTS-v2 was evaluated and rejected (non-commercial licence, unmaintained).

## 10. Out of scope (for now)

Real-time full-duplex speech, singing, emotion/style controls beyond speed, multi-speaker
dialogue in one generation, voice *conversion* of existing recordings, mobile apps, team
workspaces, payments, public voice marketplace, and any speaker-verification or watermark-based
anti-abuse system (§7).
