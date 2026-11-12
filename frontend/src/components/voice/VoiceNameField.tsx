"use client";

import { Input } from "@/components/ui/Input";
import { Select, type SelectOption } from "@/components/ui/Select";
import { useLanguages } from "@/lib/api/hooks";
import { isApiError } from "@/lib/api/client";
import { LANGUAGE_NAMES, LANGUAGE_ORDER, type LanguageCapability, type LanguageHint } from "@/lib/api/types";

export const SUGGESTED_NAME = "My voice";

/** Which languages the server can clone right now, derived from /system/languages. */
export function cloningAvailability(languages: LanguageCapability[] | undefined): Record<string, boolean> | null {
  if (!languages) return null;
  const out: Record<string, boolean> = {};
  for (const l of languages) {
    out[l.code] = l.engines.some((e) => e.cloning && e.verified !== "unavailable");
  }
  return out;
}

export function useLanguageOptions(includeAuto = true): { options: SelectOption<LanguageHint>[]; note: string | null } {
  const q = useLanguages();
  const availability = cloningAvailability(q.data);
  const unavailable503 = q.isError && isApiError(q.error) && q.error.status === 503;
  const options: SelectOption<LanguageHint>[] = [];
  if (includeAuto) options.push({ value: "auto", label: "Auto-detect", description: "We listen and work it out." });
  for (const code of LANGUAGE_ORDER) {
    const name = LANGUAGE_NAMES[code];
    const available = availability ? availability[code] !== false : true;
    options.push({
      value: code,
      label: available ? `${name.name} · ${name.native}` : `${name.name} · ${name.native} — not available on this server yet`,
      disabled: !available,
    });
  }
  const note = unavailable503 ? "Language availability could not be checked (engine unavailable). Auto-detect still works." : null;
  return { options, note };
}

export function VoiceNameField({
  name,
  onNameChange,
  language,
  onLanguageChange,
  nameError,
}: {
  name: string;
  onNameChange: (v: string) => void;
  language: LanguageHint;
  onLanguageChange: (v: LanguageHint) => void;
  nameError?: string | null;
}) {
  const { options, note } = useLanguageOptions();
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 className="display text-h2 text-ink">What should we call this voice?</h2>
        <Input
          label="Voice name"
          value={name}
          onChange={(e) => onNameChange(e.target.value)}
          placeholder={SUGGESTED_NAME}
          maxLength={60}
          error={nameError}
          hint={!nameError ? `Suggestion: “${SUGGESTED_NAME}”. 1–60 characters.` : undefined}
          autoComplete="off"
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Select<LanguageHint>
          label="Language (optional)"
          value={language}
          onValueChange={onLanguageChange}
          options={options}
        />
        <p className="text-small text-ink-3">{note ?? "A hint helps transcription. Leave on Auto if unsure."}</p>
      </div>
    </div>
  );
}
