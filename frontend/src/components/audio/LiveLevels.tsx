"use client";

import { useEffect, useState } from "react";
import { BrandMark } from "@/components/brand/BrandMark";
import { levelsFromAnalyser } from "@/lib/audio";

const IDLE = [0, 0, 0, 0, 0];

/**
 * The brand bars driven by an AnalyserNode (recording / playback). Decorative; the caller
 * announces state textually. When `analyser` is null the static mark is shown.
 */
export function LiveLevels({
  analyser,
  active,
  size = 32,
  className,
  onLevel,
}: {
  analyser: AnalyserNode | null;
  active: boolean;
  size?: number;
  className?: string;
  /** Optional overall level (0–1) callback, e.g. for a textual level readout. */
  onLevel?: (level: number) => void;
}) {
  const [levels, setLevels] = useState<number[]>(IDLE);

  useEffect(() => {
    if (!analyser || !active) {
      setLevels(IDLE);
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scratch = new Uint8Array(analyser.frequencyBinCount) as Uint8Array<ArrayBuffer>;
    let raf = 0;
    let last = 0;
    const tick = (t: number) => {
      // ~30 fps is plenty for a meter; reduced motion gets 4 fps.
      const interval = reduce ? 250 : 33;
      if (t - last >= interval) {
        last = t;
        const next = levelsFromAnalyser(analyser, scratch);
        setLevels(next);
        onLevel?.(Math.max(...next));
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [analyser, active, onLevel]);

  return <BrandMark size={size} animated={active} levels={active ? levels : null} className={className} />;
}
