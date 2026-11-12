"use client";

import * as RadixTooltip from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";

export const TooltipProvider = RadixTooltip.Provider;

export function Tooltip({
  content,
  children,
  side = "top",
  open,
}: {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom" | "left" | "right";
  open?: boolean;
}) {
  if (!content) return <>{children}</>;
  return (
    <RadixTooltip.Root delayDuration={200} open={open}>
      <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
      <RadixTooltip.Portal>
        <RadixTooltip.Content
          side={side}
          sideOffset={6}
          className="z-50 max-w-64 rounded-sm border border-border bg-surface px-2.5 py-1.5 text-small text-ink-2 shadow-md"
        >
          {content}
        </RadixTooltip.Content>
      </RadixTooltip.Portal>
    </RadixTooltip.Root>
  );
}
