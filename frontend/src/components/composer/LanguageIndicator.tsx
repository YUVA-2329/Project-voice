"use client";

import { Globe, ChevronDown, Check } from "lucide-react";
import { useMemo, useState } from "react";
import type { LanguageHint } from "@/lib/api/types";
import { cn } from "@/lib/cn";

export interface DetectionResult {
  code: LanguageHint;
  name: string;
  nativeName: string;
  confidence: number;
  isRomanized: boolean;
}

const INDIC_LANGUAGES: { code: LanguageHint; name: string; nativeName: string }[] = [
  { code: "auto", name: "Auto Detect", nativeName: "Automatic" },
  { code: "te", name: "Telugu", nativeName: "తెలుగు" },
  { code: "ta", name: "Tamil", nativeName: "தமிழ்" },
  { code: "hi", name: "Hindi", nativeName: "हिन्दी" },
  { code: "kn", name: "Kannada", nativeName: "ಕನ್ನಡ" },
  { code: "ml", name: "Malayalam", nativeName: "മലയാളം" },
  { code: "en", name: "English", nativeName: "English" },
];

const HINDI_MARKERS = new Set(["hai", "hain", "kya", "kaise", "ho", "aap", "hum", "bhai", "nahi", "nahin", "namaste", "shukriya", "dhanyawad", "bohot", "achha"]);
const TELUGU_MARKERS = new Set(["ela", "unnaru", "unnara", "bagunnara", "enti", "cheppandi", "chala", "meeru", "nenu", "namaskaram", "dhanyavadalu", "randi"]);
const TAMIL_MARKERS = new Set(["vanakkam", "epdi", "eppadi", "irukeenga", "nanba", "nalla", "enna", "romba", "thamizh", "tamil", "nandri", "vaanga"]);
const KANNADA_MARKERS = new Set(["namaskara", "hegiddira", "chennagiddira", "kannada", "dhanyavadagalu", "swagatha", "neevu", "haudu", "banni"]);
const MALAYALAM_MARKERS = new Set(["namaskaram", "sughamano", "malayalam", "nandi", "swagatham", "ningal", "athe", "varoo"]);

export function detectLanguageClient(text: string): DetectionResult {
  const clean = text.trim();
  if (!clean) {
    return { code: "en", name: "English", nativeName: "English", confidence: 0.95, isRomanized: false };
  }

  let teCount = 0;
  let taCount = 0;
  let hiCount = 0;
  let knCount = 0;
  let mlCount = 0;
  let latinCount = 0;
  let totalLetters = 0;

  for (const ch of clean) {
    const code = ch.charCodeAt(0);
    if (code >= 0x0c00 && code <= 0x0c7f) {
      teCount++;
      totalLetters++;
    } else if (code >= 0x0b80 && code <= 0x0bff) {
      taCount++;
      totalLetters++;
    } else if (code >= 0x0900 && code <= 0x097f) {
      hiCount++;
      totalLetters++;
    } else if (code >= 0x0c80 && code <= 0x0cff) {
      knCount++;
      totalLetters++;
    } else if (code >= 0x0d00 && code <= 0x0d7f) {
      mlCount++;
      totalLetters++;
    } else if ((code >= 65 && code <= 90) || (code >= 97 && code <= 122)) {
      latinCount++;
      totalLetters++;
    }
  }

  if (totalLetters === 0) totalLetters = 1;

  if (teCount / totalLetters >= 0.15) {
    const conf = Math.min(0.99, (teCount / totalLetters) + 0.15);
    return { code: "te", name: "Telugu", nativeName: "తెలుగు", confidence: conf, isRomanized: false };
  }
  if (taCount / totalLetters >= 0.15) {
    const conf = Math.min(0.99, (taCount / totalLetters) + 0.15);
    return { code: "ta", name: "Tamil", nativeName: "தமிழ்", confidence: conf, isRomanized: false };
  }
  if (hiCount / totalLetters >= 0.15) {
    const conf = Math.min(0.99, (hiCount / totalLetters) + 0.15);
    return { code: "hi", name: "Hindi", nativeName: "हिन्दी", confidence: conf, isRomanized: false };
  }
  if (knCount / totalLetters >= 0.15) {
    const conf = Math.min(0.99, (knCount / totalLetters) + 0.15);
    return { code: "kn", name: "Kannada", nativeName: "ಕನ್ನಡ", confidence: conf, isRomanized: false };
  }
  if (mlCount / totalLetters >= 0.15) {
    const conf = Math.min(0.99, (mlCount / totalLetters) + 0.15);
    return { code: "ml", name: "Malayalam", nativeName: "മലയാളം", confidence: conf, isRomanized: false };
  }

  // Romanized heuristic
  const words = clean.toLowerCase().replace(/[^\w\s]/g, "").split(/\s+/).filter(Boolean);
  const totalWords = words.length || 1;
  const hiHits = words.filter((w) => HINDI_MARKERS.has(w)).length;
  const teHits = words.filter((w) => TELUGU_MARKERS.has(w)).length;
  const taHits = words.filter((w) => TAMIL_MARKERS.has(w)).length;
  const knHits = words.filter((w) => KANNADA_MARKERS.has(w)).length;
  const mlHits = words.filter((w) => MALAYALAM_MARKERS.has(w)).length;

  if (teHits > 0 && teHits >= hiHits && teHits >= taHits && teHits >= knHits && teHits >= mlHits) {
    return { code: "te", name: "Telugu", nativeName: "తెలుగు", confidence: 0.95, isRomanized: true };
  }
  if (taHits > 0 && taHits >= hiHits && taHits >= knHits && taHits >= mlHits) {
    return { code: "ta", name: "Tamil", nativeName: "தமிழ்", confidence: 0.95, isRomanized: true };
  }
  if (knHits > 0 && knHits >= hiHits && knHits >= mlHits) {
    return { code: "kn", name: "Kannada", nativeName: "ಕನ್ನಡ", confidence: 0.95, isRomanized: true };
  }
  if (mlHits > 0 && mlHits >= hiHits) {
    return { code: "ml", name: "Malayalam", nativeName: "മലയാളം", confidence: 0.95, isRomanized: true };
  }
  if (hiHits > 0) {
    return { code: "hi", name: "Hindi", nativeName: "हिन्दी", confidence: 0.95, isRomanized: true };
  }

  return { code: "en", name: "English", nativeName: "English", confidence: 0.95, isRomanized: false };
}

export interface LanguageIndicatorProps {
  text: string;
  selectedLanguage: LanguageHint;
  onSelectLanguage: (lang: LanguageHint) => void;
  className?: string;
}

export function LanguageIndicator({
  text,
  selectedLanguage,
  onSelectLanguage,
  className,
}: LanguageIndicatorProps) {
  const [isOpen, setIsOpen] = useState(false);
  const detected = useMemo(() => detectLanguageClient(text), [text]);

  const activeLang = INDIC_LANGUAGES.find((l) => l.code === selectedLanguage) ?? INDIC_LANGUAGES[0]!;
  const isAuto = selectedLanguage === "auto";

  return (
    <div className={cn("relative inline-block text-left", className)}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-micro font-medium transition-all duration-fast ease-pv",
          "hover:border-border-strong hover:bg-surface-2",
          isAuto ? "bg-surface text-ink-2" : "border-accent/40 bg-accent/5 text-accent",
        )}
        title="Multilingual speech generation: Click to override language"
        aria-expanded={isOpen}
      >
        <Globe className="size-3 text-ink-3" aria-hidden />
        <span>
          {isAuto ? (
            <>
              <span className="text-ink-3">Auto:</span>{" "}
              <strong className="font-semibold text-ink">{detected.name}</strong>
              <span className="font-mono text-[10px] text-ink-3">
                ({Math.round(detected.confidence * 100)}%)
              </span>
              {detected.isRomanized && (
                <span className="ml-0.5 rounded bg-surface-3 px-1 py-0.2 text-[9px] text-ink-3">
                  Romanized
                </span>
              )}
            </>
          ) : (
            <>
              <span className="text-accent font-semibold">{activeLang.name}</span>
              <span className="text-[10px] opacity-75">({activeLang.nativeName})</span>
            </>
          )}
        </span>
        <ChevronDown className="size-3 text-ink-3" aria-hidden />
      </button>

      {isOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setIsOpen(false)} aria-hidden />
          <div className="absolute bottom-full left-0 z-50 mb-1.5 w-48 rounded-md border border-border bg-surface p-1 shadow-lg backdrop-blur-md">
            <div className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wider text-ink-3">
              Speech Language
            </div>
            {INDIC_LANGUAGES.map((lang) => {
              const isSelected = selectedLanguage === lang.code;
              return (
                <button
                  key={lang.code}
                  type="button"
                  onClick={() => {
                    onSelectLanguage(lang.code);
                    setIsOpen(false);
                  }}
                  className={cn(
                    "flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-xs transition-colors duration-fast",
                    isSelected ? "bg-surface-2 text-ink font-medium" : "text-ink-2 hover:bg-surface-2 hover:text-ink",
                  )}
                >
                  <div className="flex flex-col">
                    <span>{lang.name}</span>
                    {lang.code !== "auto" && (
                      <span className="text-[10px] text-ink-3">{lang.nativeName}</span>
                    )}
                  </div>
                  {isSelected && <Check className="size-3.5 text-accent" />}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
