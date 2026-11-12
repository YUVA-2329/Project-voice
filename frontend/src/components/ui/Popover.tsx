"use client";

import * as RadixPopover from "@radix-ui/react-popover";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export const PopoverRoot = RadixPopover.Root;
export const PopoverTrigger = RadixPopover.Trigger;
export const PopoverClose = RadixPopover.Close;

export function PopoverContent({
  children,
  className,
  align = "start",
  sideOffset = 6,
}: {
  children: ReactNode;
  className?: string;
  align?: "start" | "center" | "end";
  sideOffset?: number;
}) {
  return (
    <RadixPopover.Portal>
      <RadixPopover.Content
        align={align}
        sideOffset={sideOffset}
        className={cn(
          "z-50 min-w-56 rounded-md border border-border bg-surface p-1 shadow-md outline-none",
          "data-[state=open]:animate-in data-[state=closed]:animate-out",
          className,
        )}
      >
        {children}
      </RadixPopover.Content>
    </RadixPopover.Portal>
  );
}
