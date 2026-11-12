# PROJECT VOICE — Design System

**Your voice. Your words.**

The interface must feel like a precision instrument made for ordinary people: calm, legible,
confident. Restraint is the brief. No neon gradients, no particles, no glass panels, no floating
cards, no dashboards in Simple mode, no decorative charts, no constant motion.

References for *quality bar only* (never copy layouts or branding): Apple product UI, Linear,
Teenage Engineering hardware, high-end editorial typography, Ableton/Logic-grade audio tools.

## 1. Tokens (`src/styles/tokens.css`)

```css
:root {
  /* Surfaces — warm paper */
  --pv-bg: #F5F2EC;          /* page */
  --pv-surface: #FBFAF7;     /* raised panels, inputs */
  --pv-surface-2: #EEEAE2;   /* subtle sunk areas */
  --pv-border: #D9D3C8;      /* hairlines */
  --pv-border-strong: #B9B1A3;

  /* Ink */
  --pv-ink: #141414;         /* primary text, near-black graphite */
  --pv-ink-2: #4A4843;       /* secondary */
  --pv-ink-3: #817D74;       /* tertiary / placeholders */
  --pv-ink-inverse: #F5F2EC;

  /* The single accent — signal red-orange, used sparingly: Run button, active voice, live recording */
  --pv-accent: #E4572E;
  --pv-accent-hover: #CC4A24;
  --pv-accent-soft: #F8DED3;
  --pv-on-accent: #FFF8F4;

  /* Semantic */
  --pv-success: #2F7A4F; --pv-warning: #B7791F; --pv-danger: #B23A2E;

  /* Geometry */
  --pv-radius-xs: 4px; --pv-radius-sm: 6px; --pv-radius-md: 10px; --pv-radius-lg: 14px;
  --pv-shadow-sm: 0 1px 0 rgba(20,20,20,.04), 0 1px 2px rgba(20,20,20,.06);
  --pv-shadow-md: 0 2px 4px rgba(20,20,20,.05), 0 8px 24px rgba(20,20,20,.08);

  /* Spacing: 4-pt scale. Use Tailwind spacing 1,2,3,4,6,8,12,16,24 only. */
  /* Motion */
  --pv-ease: cubic-bezier(.2,.7,.2,1); --pv-dur-fast: 120ms; --pv-dur: 220ms; --pv-dur-slow: 480ms;
}
:root[data-theme="dark"], @media (prefers-color-scheme: dark) and :root:not([data-theme="light"]) {
  --pv-bg: #121212; --pv-surface: #1A1A1A; --pv-surface-2: #222222;
  --pv-border: #2C2C2C; --pv-border-strong: #3D3D3D;
  --pv-ink: #F1EEE8; --pv-ink-2: #B8B4AC; --pv-ink-3: #7C786F; --pv-ink-inverse: #141414;
  --pv-accent: #FF6A3D; --pv-accent-hover: #FF7F58; --pv-accent-soft: #3A221A; --pv-on-accent: #1A0D08;
}
```

Expose these to Tailwind v4 via `@theme inline` so classes like `bg-bg`, `text-ink-2`,
`border-border`, `bg-accent` exist. Never hard-code hex values in components.

## 2. Typography

* **Display:** Instrument Serif (`@fontsource/instrument-serif`, regular + italic). Used for
  the hero, page titles (`h1`), empty-state headlines, and the "Your voice is ready." moment.
  Tight tracking (`-0.02em`), line-height 1.0–1.05. Italic used for a single emphasised word.
* **Interface:** Geist Sans (`geist` package). Body 15px/1.5, labels 13px, captions 12px with
  `+0.01em` tracking. Buttons 14px medium.
* **Mono:** Geist Mono for Developer mode, IDs, durations, character counts.
* Scale: display 56/64/80 (responsive), h1 40, h2 28, h3 20, body 15, small 13, micro 12.
* Headings in UPPERCASE only for the eyebrow labels (`micro`, tracking `+0.08em`, `ink-3`)
  such as `MY VOICES`, `SELECTED VOICE`, `OUTPUT`.

## 3. Layout

* Max content width 720px for Simple mode (the composer is the hero of `/app`); 1040px for
  library/history; full-bleed for the introduction.
* Side gutters 16px (mobile), 24px (tablet), 40px (desktop).
* Navigation: a slim 56px top bar: wordmark left (`PROJECT VOICE` in Geist Sans 13px, tracking
  `+0.12em`, with the brand mark), four text links centre (`Create · My Voices · History ·
  Settings`), account menu right. No giant nav. Collapses to a bottom tab bar under 720px.
* Hairline borders (1px `--pv-border`) instead of shadows to separate regions. Shadows only
  on popovers and the Run button's pressed state.

## 4. Brand mark

Original mark: five vertical bars of a voice signature arranged symmetrically
(heights 10 / 22 / 32 / 22 / 10 on a 32px grid, 3px wide, 3px gaps, fully rounded ends) with the
centre bar in `--pv-accent` and the others in `--pv-ink`. In motion (recording / speaking) the
bars animate from live audio levels. Provide it as `<BrandMark size animated levels?/>` and as
an SVG favicon. The wordmark is text, not an image.

## 5. Components (src/components)

* `brand/BrandMark`, `brand/Wordmark`
* `navigation/TopBar`, `navigation/MobileTabs`, `navigation/AccountMenu`
* `voice/VoiceSelector` — compact popover listing ready voices with a dot indicator; shows the
  selected voice name + "Change". Empty state links to Create.
* `voice/VoiceCard`, `voice/VoiceLibrary`, `voice/VoiceRecorder`, `voice/AudioUploader`,
  `voice/ConsentCheckbox`, `voice/VoiceNameField`, `voice/CreateVoiceWizard`
* `audio/AudioPlayer` — play/pause, scrubber, elapsed/total (mono), download, regenerate.
  Uses the brand bars for the live level meter while playing.
* `audio/Waveform` — static waveform from decoded buffer; `audio/LiveLevels` for recording.
* `composer/TextComposer` — auto-growing textarea, char count (mono), clear, language chip in
  Advanced mode. Placeholder: *What would you like your voice to say?*
* `composer/RunButton` — the single accent-filled button; label `Run`, keyboard `⌘/Ctrl+Enter`.
  States: idle, disabled (no voice / empty text), running (progress stage text, real values).
* `composer/GenerationResult` — appears directly beneath the composer; status line then player.
* `history/HistoryList`, `settings/SettingsPanel`, `advanced/AdvancedControls`,
  `developer/*` (ModelStatus, HardwarePanel, QueuePanel, ApiKeys, Endpoints, Logs)
* `ui/*` — Button, IconButton, Input, Textarea, Select, Switch, Dialog, Popover, Toast, Tabs,
  Skeleton, EmptyState, Kbd, Badge. Built on Radix primitives for accessibility.

## 6. Motion

* Introduction (`/`): ≤ 2.2 s total. Mark draws in (bars scale from centre, 400 ms) → wordmark
  fades (200 ms) → display headline rises 12px with a 480 ms ease → a thin waveform line draws
  across the width (600 ms, stroke-dashoffset) → tagline → CTA fades in and receives focus ring
  on keyboard. With `prefers-reduced-motion`, everything is simply visible.
* Elsewhere: opacity/translate ≤ 8px, 120–220 ms. No looping animations except the live level
  meter while recording/playing and a 1px progress bar during generation.

## 7. Copy

Short, lower-case-friendly sentences; no exclamation marks except the single success moment.
Examples: *Let's create your voice.* · *Record a sample or upload a recording.* ·
*What should we call this voice?* · *Your voice is ready.* · *All your voices, in one place.* ·
*Nothing here yet. Create your first voice.* · Errors say what happened and what to do next.

## 8. Accessibility

Focus rings 2px `--pv-accent` offset 2px on every interactive element; minimum touch target
40px; colour contrast ≥ 4.5:1 for text; recording state announced via `aria-live`; waveform
and meters are decorative (`aria-hidden`) with textual equivalents (duration, level).
