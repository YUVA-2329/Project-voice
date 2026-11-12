"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useEffect, useMemo, useRef } from "react";
import { BAR_HEIGHTS } from "@/components/brand/BrandMark";
import { useMe } from "@/lib/api/hooks";
import { cn } from "@/lib/cn";

const EASE = [0.2, 0.7, 0.2, 1] as const;

// Timeline (seconds) — total ≤ 2.2 s.
const T = {
  bars: 0,
  wordmark: 0.4,
  headline: 0.6,
  wave: 1.0,
  tagline: 1.5,
  cta: 1.8,
};

/** Deterministic voice-like line so server and client render the same path. */
function buildWavePath(width = 1000, height = 64, points = 240): string {
  const mid = height / 2;
  let d = `M 0 ${mid}`;
  for (let i = 1; i <= points; i++) {
    const t = i / points;
    const x = t * width;
    // Envelope: quiet → speech → quiet, with a few syllable-like swells.
    const env = Math.sin(Math.PI * t) ** 1.4 * (0.55 + 0.45 * Math.sin(t * 23.0 + 0.7) * Math.sin(t * 7.3));
    const carrier = Math.sin(t * 160) * 0.65 + Math.sin(t * 93 + 1.3) * 0.35;
    const y = mid + carrier * env * (height / 2 - 2);
    d += ` L ${x.toFixed(2)} ${y.toFixed(2)}`;
  }
  return d;
}

const WAVE_PATH = buildWavePath();

export function Introduction() {
  const reduce = useReducedMotion() ?? false;
  const me = useMe({ redirect: false });
  const authed = me.isSuccess && Boolean(me.data);
  const ctaRef = useRef<HTMLAnchorElement>(null);

  // Keyboard users: the first Tab after the sequence lands on the primary CTA (with its ring).
  // Mouse users never see a ring appear on its own.
  useEffect(() => {
    const readyAt = performance.now() + (reduce ? 0 : (T.cta + 0.2) * 1000);
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || e.shiftKey) return;
      if (performance.now() < readyAt) return;
      if (document.activeElement !== document.body) return;
      const el = ctaRef.current;
      if (!el) return;
      e.preventDefault();
      el.focus({ preventScroll: true });
      window.removeEventListener("keydown", onKeyDown);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [reduce]);

  const fade = useMemo(
    () => (delay: number, rise = 0) =>
      reduce
        ? {}
        : {
            initial: { opacity: 0, y: rise },
            animate: { opacity: 1, y: 0 },
            transition: { delay, duration: rise ? 0.48 : 0.2, ease: EASE },
          },
    [reduce],
  );

  const createHref = authed ? "/app/voices/create" : "/register";

  return (
    <main className="relative flex min-h-dvh flex-col bg-bg text-ink">
      <header className="flex h-14 items-center justify-between px-4 sm:px-6 lg:px-10">
        <motion.div {...fade(T.wordmark)} className="flex items-center gap-2.5">
          <span className="text-[13px] font-medium uppercase tracking-[0.12em] text-ink">PROJECT VOICE</span>
        </motion.div>
        <motion.div {...fade(T.cta)}>
          {me.isPending ? null : authed ? (
            <Link
              href="/app"
              className="inline-flex h-10 items-center gap-1.5 rounded-sm px-3 text-small font-medium text-ink-2 hover:text-ink"
            >
              Open the app
              <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          ) : (
            <Link href="/login" className="inline-flex h-10 items-center rounded-sm px-3 text-small font-medium text-ink-2 hover:text-ink">
              Sign in
            </Link>
          )}
        </motion.div>
      </header>

      <section className="flex flex-1 flex-col justify-center px-4 pb-16 pt-8 sm:px-6 lg:px-10">
        <div className="mx-auto w-full max-w-[1040px]">
          {/* Brand mark: bars scale in from the centre, 400 ms, slight stagger. */}
          <div className="mb-10 flex h-12 items-center" aria-hidden>
            <svg width={48 * (27 / 32)} height={48} viewBox="0 0 27 32" className="overflow-visible">
              {BAR_HEIGHTS.map((h, i) => (
                <motion.rect
                  key={i}
                  x={i * 6}
                  y={(32 - h) / 2}
                  width={3}
                  height={h}
                  rx={1.5}
                  style={{ originY: "16px", originX: `${i * 6 + 1.5}px` }}
                  className={i === 2 ? "fill-accent" : "fill-ink"}
                  initial={reduce ? false : { scaleY: 0 }}
                  animate={{ scaleY: 1 }}
                  transition={reduce ? { duration: 0 } : { delay: T.bars + i * 0.04, duration: 0.4, ease: EASE }}
                />
              ))}
            </svg>
          </div>

          <motion.h1
            {...fade(T.headline, 12)}
            className="display text-ink text-[56px] leading-[1.02] sm:text-[64px] lg:text-[80px]"
          >
            YOUR VOICE.
            <br />
            YOUR <em className="italic">WORDS.</em>
          </motion.h1>

          {/* Thin waveform line draws across the width. */}
          <div className="my-10 h-12 w-full sm:my-12" aria-hidden>
            <svg viewBox="0 0 1000 64" preserveAspectRatio="none" className="h-full w-full overflow-visible">
              <motion.path
                d={WAVE_PATH}
                fill="none"
                className="stroke-ink-3"
                strokeWidth={1}
                vectorEffect="non-scaling-stroke"
                strokeLinecap="round"
                initial={reduce ? false : { pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 1 }}
                transition={reduce ? { duration: 0 } : { delay: T.wave, duration: 0.6, ease: EASE }}
              />
            </svg>
          </div>

          <motion.p {...fade(T.tagline)} className="max-w-xl text-h3 text-ink-2">
            Create your personal voice once. Use it whenever you need.
          </motion.p>

          <motion.div {...fade(T.cta)} className="mt-8 flex flex-wrap items-center gap-3">
            <Link
              ref={ctaRef}
              href={createHref}
              className={cn(
                "inline-flex h-12 items-center gap-2 rounded-sm bg-ink px-6 text-button font-medium text-ink-inverse",
                "transition-colors duration-fast ease-pv hover:bg-ink-2",
              )}
            >
              Create your voice
            </Link>
            <Link
              href="/app/voices"
              className="inline-flex h-12 items-center gap-1.5 rounded-sm px-4 text-button font-medium text-ink-2 transition-colors duration-fast ease-pv hover:text-ink"
            >
              Explore my voices
              <ArrowRight className="size-4" aria-hidden />
            </Link>
          </motion.div>
        </div>
      </section>

      <footer className="flex h-12 items-center px-4 sm:px-6 lg:px-10">
        <motion.p {...fade(T.cta)} className="font-mono text-micro text-ink-3">
          Your voice. Your words.
        </motion.p>
      </footer>
    </main>
  );
}
