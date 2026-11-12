"use client";

import { ArrowLeft, Check, Mic, Upload } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { Textarea } from "@/components/ui/Textarea";
import { useCreateVoice, useJob, useUpdateVoice, useVoice } from "@/lib/api/hooks";
import type { UploadProgress } from "@/lib/api/client";
import { CONSENT_TEXT_VERSION, type LanguageHint, type Voice } from "@/lib/api/types";
import { useAppStore } from "@/lib/store";
import { cn } from "@/lib/cn";
import { formatBytes } from "@/lib/format";
import { VOICE_STAGE_LABELS, jobStageText } from "@/lib/stages";
import { AudioUploader } from "./AudioUploader";
import { ConsentCheckbox } from "./ConsentCheckbox";
import { VoiceNameField } from "./VoiceNameField";
import { VoiceRecorder, type CapturedAudio } from "./VoiceRecorder";

type Step = "source" | "capture" | "details" | "uploading" | "processing" | "done";
type Source = "record" | "upload";

const STEP_INDEX: Record<Step, number> = { source: 1, capture: 2, details: 3, uploading: 4, processing: 4, done: 5 };

export function CreateVoiceWizard() {
  const router = useRouter();
  const setSelected = useAppStore((s) => s.setSelectedVoiceId);
  const create = useCreateVoice();

  const [step, setStep] = useState<Step>("source");
  const [source, setSource] = useState<Source | null>(null);
  const [audio, setAudio] = useState<CapturedAudio | null>(null);
  const [name, setName] = useState("");
  const [language, setLanguage] = useState<LanguageHint>("auto");
  const [consent, setConsent] = useState(false);
  const [showErrors, setShowErrors] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [voiceId, setVoiceId] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const onCaptured = useCallback((a: CapturedAudio | null) => setAudio(a), []);

  const nameError = showErrors && !name.trim() ? "Give the voice a name." : null;
  const consentError = showErrors && !consent ? "You need to confirm this before we can continue." : null;
  const canSubmit = Boolean(audio) && name.trim().length > 0 && consent;

  const submit = () => {
    setShowErrors(true);
    if (!audio || !name.trim() || !consent) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setStep("uploading");
    setProgress(null);
    create.mutate(
      {
        input: {
          file: audio.blob,
          fileName: audio.fileName,
          name: name.trim(),
          language_hint: language,
          consent_confirmed: true,
          consent_text_version: CONSENT_TEXT_VERSION,
        },
        onProgress: setProgress,
        signal: controller.signal,
      },
      {
        onSuccess: (voice) => {
          setVoiceId(voice.id);
          setStep("processing");
        },
        onError: () => setStep("details"),
      },
    );
  };

  const cancelUpload = () => {
    abortRef.current?.abort();
    setStep("details");
  };

  const reset = () => {
    setStep("source");
    setSource(null);
    setAudio(null);
    setName("");
    setLanguage("auto");
    setConsent(false);
    setShowErrors(false);
    setProgress(null);
    setVoiceId(null);
    create.reset();
  };

  return (
    <div className="mx-auto w-full max-w-[720px] px-4 py-10 sm:px-6 sm:py-14 lg:px-10">
      <div className="mb-8 flex items-center justify-between">
        <p className="eyebrow">
          Step {STEP_INDEX[step]} of 5
        </p>
        {step !== "source" && step !== "uploading" && step !== "processing" && step !== "done" && (
          <button
            type="button"
            onClick={() => {
              setStep(step === "capture" ? "source" : "capture");
              if (step === "capture") setAudio(null);
            }}
            className="inline-flex h-8 items-center gap-1.5 rounded-sm px-2 text-small font-medium text-ink-2 transition-colors duration-fast ease-pv hover:bg-surface-2 hover:text-ink"
          >
            <ArrowLeft className="size-3.5" aria-hidden />
            Back
          </button>
        )}
      </div>

      {step === "source" && (
        <div className="flex flex-col gap-8">
          <div className="flex flex-col gap-2">
            <h1 className="display text-h1 text-ink sm:text-display-sm">Let&apos;s create your voice.</h1>
            <p className="text-body text-ink-2">Record a sample or upload a recording.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <ChoiceCard
              icon={<Mic className="size-5" aria-hidden />}
              title="Record my voice"
              description="Use your microphone. About 15 seconds."
              onClick={() => {
                setSource("record");
                setStep("capture");
              }}
            />
            <ChoiceCard
              icon={<Upload className="size-5" aria-hidden />}
              title="Upload audio"
              description="WAV, MP3, M4A, FLAC, OGG or WebM."
              onClick={() => {
                setSource("upload");
                setStep("capture");
              }}
            />
          </div>
        </div>
      )}

      {step === "capture" && source === "record" && (
        <div className="flex flex-col gap-8">
          <VoiceRecorder onCaptured={onCaptured} />
          <div className="flex justify-end">
            <Button variant="primary" size="lg" disabled={!audio} onClick={() => setStep("details")}>
              Continue
            </Button>
          </div>
        </div>
      )}

      {step === "capture" && source === "upload" && (
        <div className="flex flex-col gap-8">
          <AudioUploader onCaptured={onCaptured} />
          <div className="flex justify-end">
            <Button variant="primary" size="lg" disabled={!audio} onClick={() => setStep("details")}>
              Continue
            </Button>
          </div>
        </div>
      )}

      {step === "details" && (
        <form
          className="flex flex-col gap-10"
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          noValidate
        >
          <VoiceNameField name={name} onNameChange={setName} language={language} onLanguageChange={setLanguage} nameError={nameError} />
          <div className="flex flex-col gap-3">
            <p className="eyebrow">Consent</p>
            <ConsentCheckbox checked={consent} onCheckedChange={setConsent} error={consentError} />
          </div>
          {create.isError && <ErrorNote error={create.error} />}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-small text-ink-3">
              {audio ? `${audio.source === "recording" ? "Recording" : audio.fileName} · ${formatBytes(audio.blob.size)}` : "No audio selected"}
            </p>
            <Button type="submit" variant="primary" size="lg" disabled={!audio} aria-disabled={!canSubmit || undefined}>
              Create voice
            </Button>
          </div>
        </form>
      )}

      {step === "uploading" && (
        <div className="flex flex-col gap-6">
          <h2 className="display text-h1 text-ink">Uploading…</h2>
          <div className="flex flex-col gap-2">
            <ProgressBar
              fraction={progress && progress.total > 0 ? progress.loaded / progress.total : null}
              label="Upload progress"
            />
            <p className="font-mono text-micro tabular text-ink-3" aria-live="polite">
              {progress ? `${formatBytes(progress.loaded)} of ${formatBytes(progress.total)}` : "Starting upload"}
            </p>
          </div>
          <div>
            <Button onClick={cancelUpload}>Cancel</Button>
          </div>
        </div>
      )}

      {step === "processing" && voiceId && (
        <ProcessingScreen voiceId={voiceId} onReady={() => setStep("done")} onRetry={reset} />
      )}

      {step === "done" && voiceId && (
        <ReadyScreen
          voiceId={voiceId}
          onUse={(v) => {
            setSelected(v.id);
            router.push("/app");
          }}
          onAnother={reset}
        />
      )}
    </div>
  );
}

function ChoiceCard({ icon, title, description, onClick }: { icon: React.ReactNode; title: string; description: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex min-h-40 flex-col items-start justify-between gap-6 rounded-md border border-border bg-surface p-5 text-left",
        "transition-colors duration-fast ease-pv hover:border-border-strong hover:bg-surface-2 active:translate-y-px",
      )}
    >
      <span className="flex size-10 items-center justify-center rounded-sm border border-border text-ink">{icon}</span>
      <span className="flex flex-col gap-1">
        <span className="text-h3 font-medium text-ink">{title}</span>
        <span className="text-small text-ink-2">{description}</span>
      </span>
    </button>
  );
}

const STAGE_SEQUENCE = ["decode", "analyse", "vad", "trim", "transcribe", "validate", "fingerprint", "done"];

function ProcessingScreen({ voiceId, onReady, onRetry }: { voiceId: string; onReady: () => void; onRetry: () => void }) {
  const voice = useVoice(voiceId);
  const job = useJob(voice.data?.job_id ?? null);
  const status = voice.data?.status;

  useEffect(() => {
    if (status === "ready") onReady();
  }, [status, onReady]);

  const currentStage = job.data?.progress?.stage ?? null;
  const currentIdx = currentStage ? STAGE_SEQUENCE.indexOf(currentStage) : -1;
  const seen = useMemo(() => {
    const s = new Set<string>();
    if (currentIdx >= 0) for (let i = 0; i <= currentIdx; i++) s.add(STAGE_SEQUENCE[i]!);
    return s;
  }, [currentIdx]);

  if (status === "failed") {
    return (
      <div className="flex flex-col gap-6">
        <h2 className="display text-h1 text-ink">That didn&apos;t work.</h2>
        <ErrorNote
          message={voice.data?.error?.message ?? "We could not process this recording. Try a cleaner sample."}
          code={voice.data?.error?.code ?? job.data?.error?.code ?? null}
        />
        <div>
          <Button variant="primary" size="lg" onClick={onRetry}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8" aria-busy="true">
      <div className="flex flex-col gap-2">
        <h2 className="display text-h1 text-ink">Listening closely…</h2>
        <p className="text-body text-ink-2">We are checking the quality, finding the speech and learning how you sound.</p>
      </div>
      <div className="flex flex-col gap-3">
        <ProgressBar fraction={null} label="Processing" />
        <p className="font-mono text-small text-ink-2" aria-live="polite" role="status">
          {jobStageText(job.data, voice.data?.job_id ? "Starting" : "Queued")}…
        </p>
      </div>
      <ol className="flex flex-col gap-2" aria-label="Processing stages">
        {STAGE_SEQUENCE.filter((s) => s !== "done").map((s) => {
          const label = VOICE_STAGE_LABELS[s] ?? s;
          const done = seen.has(s) && s !== currentStage;
          const active = s === currentStage;
          return (
            <li key={s} className={cn("flex items-center gap-3 text-small", active ? "text-ink" : done ? "text-ink-2" : "text-ink-3")}>
              <span
                aria-hidden
                className={cn(
                  "flex size-4 items-center justify-center rounded-full border",
                  done ? "border-ink bg-ink text-ink-inverse" : active ? "border-accent" : "border-border",
                )}
              >
                {done && <Check className="size-2.5" strokeWidth={3} />}
                {active && <span className="size-1.5 rounded-full bg-accent" />}
              </span>
              {label}
            </li>
          );
        })}
      </ol>
      {voice.isError && <ErrorNote error={voice.error} />}
    </div>
  );
}

function ReadyScreen({ voiceId, onUse, onAnother }: { voiceId: string; onUse: (v: Voice) => void; onAnother: () => void }) {
  const voice = useVoice(voiceId, { poll: false });
  const update = useUpdateVoice();
  const [transcript, setTranscript] = useState<string | null>(null);
  const v = voice.data;
  const value = transcript ?? v?.transcript ?? "";
  const dirty = v != null && transcript != null && transcript.trim() !== (v.transcript ?? "").trim();

  if (!v) return null;

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-3">
        <h2 className="display text-display-sm text-ink">
          Your voice is <em className="italic">ready.</em>
        </h2>
        <p className="text-body text-ink-2">
          {v.name}
          {v.reference?.speech_seconds != null ? ` · ${v.reference.speech_seconds.toFixed(1)} s of clean speech` : ""}
          {v.quality?.snr_db != null ? ` · ${Math.round(v.quality.snr_db)} dB signal-to-noise` : ""}
        </p>
        {v.quality?.warnings?.length ? <p className="text-small text-ink-3">{v.quality.warnings.join(" · ")}</p> : null}
      </div>

      <div className="flex flex-col gap-3">
        <p className="eyebrow">We heard</p>
        <label htmlFor="transcript" className="text-small text-ink-2">
          Correct it if needed — an accurate transcript improves every generation.
        </label>
        <Textarea id="transcript" rows={4} value={value} onChange={(e) => setTranscript(e.target.value)} />
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            variant={dirty ? "primary" : "secondary"}
            disabled={!dirty || update.isPending}
            loading={update.isPending}
            onClick={() =>
              update.mutate(
                { id: v.id, body: { transcript: value.trim() } },
                { onSuccess: () => setTranscript(null) },
              )
            }
          >
            Save transcript
          </Button>
          {v.transcript_source && (
            <span className="font-mono text-micro text-ink-3">{v.transcript_source === "auto" ? "auto transcript" : "your transcript"}</span>
          )}
          {update.isSuccess && !dirty && <span className="text-small text-success">Saved</span>}
        </div>
        {update.isError && <ErrorNote error={update.error} />}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" size="lg" onClick={() => onUse(v)}>
          Use this voice
        </Button>
        <Button size="lg" onClick={onAnother}>
          Create another
        </Button>
      </div>
    </div>
  );
}
