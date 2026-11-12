"use client";

import * as RadixDialog from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { IconButton } from "./IconButton";

export const DialogRoot = RadixDialog.Root;
export const DialogTrigger = RadixDialog.Trigger;
export const DialogClose = RadixDialog.Close;

export function DialogContent({
  title,
  description,
  children,
  footer,
  className,
  hideTitle,
}: {
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  className?: string;
  hideTitle?: boolean;
}) {
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className="fixed inset-0 z-40 bg-ink/30 data-[state=open]:animate-in data-[state=closed]:animate-out" />
      <RadixDialog.Content
        className={cn(
          "fixed left-1/2 top-1/2 z-50 w-[calc(100vw-32px)] max-w-md -translate-x-1/2 -translate-y-1/2",
          "rounded-lg border border-border bg-surface p-6 shadow-md outline-none",
          className,
        )}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex flex-col gap-1">
            <RadixDialog.Title className={cn("text-h3 font-medium text-ink", hideTitle && "sr-only")}>
              {title}
            </RadixDialog.Title>
            {description ? (
              <RadixDialog.Description className="text-small text-ink-2">{description}</RadixDialog.Description>
            ) : (
              <RadixDialog.Description className="sr-only">{title}</RadixDialog.Description>
            )}
          </div>
          <RadixDialog.Close asChild>
            <IconButton label="Close" size="sm" className="-mr-2 -mt-2">
              <X className="size-4" aria-hidden />
            </IconButton>
          </RadixDialog.Close>
        </div>
        {children && <div className="mt-4">{children}</div>}
        {footer && <div className="mt-6 flex justify-end gap-2">{footer}</div>}
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}
