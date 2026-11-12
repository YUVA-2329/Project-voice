"use client";

import { Loader2 } from "lucide-react";
import type { Generation } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { generationStageText, progressFraction } from "@/lib/stages";
import { Tooltip } from "@/components/ui/Tooltip";

export interface RunButtonProps {
  onRun: () => void;
  /** Reason the button is disabled, shown as a tooltip and read by assistive tech. */
  disabledReason?: string | null;
  /** The in-flight generation (queued / processing) — drives the real progress readout. */
  running?: Pick<Generation, "status" | "progress"> | null;
  /** Request has been sent but no generation object has come back yet. */
  submitting?: boolean;
  className?: string;
}

/**
 * The single accent-filled button. While running it shows the real pipeline stage text and a
 * 1px bar whose width is `current / total` — never a fabricated percentage.
 */
export function RunButton({ onRun, disabledReason, running, submitting, className }: RunButtonProps) {
  const isRunning = Boolean(running) || Boolean(submitting);
  const disabled = Boolean(disabledReason) || isRunning;
  const stage = submitting && !running ? "Starting" : running ? generationStageText(running) : "";
  const fraction = running ? progressFraction(running.progress) : null;
  const showBar = isRunning && running?.status === "processing";

  const button = (
    <button
      type="button"
      onClick={onRun}
      disabled={disabled}
      aria-disabled={disabled || undefined}
      aria-describedby={disabledReason ? "run-reason" : undefined}
      aria-busy={isRunning || undefined}
      className={cn(
        "relative inline-flex h-12 min-w-36 items-center justify-center gap-2 overflow-hidden rounded-sm bg-accent px-6 text-button font-medium text-on-accent",
        "transition-[background-color,transform,box-shadow] duration-fast ease-pv",
        "hover:bg-accent-hover active:translate-y-px active:shadow-sm",
        "disabled:cursor-not-allowed",
        !isRunning && disabled && "opacity-50",
        className,
      )}
    >
      {isRunning ? (
        <>
          <Loader2 className="size-4 animate-spin" aria-hidden />
          <span className="tabular" aria-live="polite">
            {stage || "Processing"}
          </span>
          {showBar && (
            <span aria-hidden className="absolute inset-x-0 bottom-0 h-px bg-on-accent/30">
              <span
                className="block h-full bg-on-accent transition-[width] duration-base ease-pv"
                style={{ width: fraction == null ? "0%" : `${Math.round(fraction * 100)}%` }}
                data-testid="run-progress"
              />
            </span>
          )}
        </>
      ) : (
        "Run"
      )}
    </button>
  );

  return (
    <div className="inline-flex flex-col items-end gap-1">
      {disabledReason && !isRunning ? (
        <Tooltip content={disabledReason}>
          <span tabIndex={0} className="inline-flex rounded-sm">
            {button}
          </span>
        </Tooltip>
      ) : (
        button
      )}
      {disabledReason && !isRunning && (
        <span id="run-reason" className="sr-only">
          {disabledReason}
        </span>
      )}
    </div>
  );
}
