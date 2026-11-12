"use client";

import * as RadixTabs from "@radix-ui/react-tabs";
import { cn } from "@/lib/cn";

export const TabsRoot = RadixTabs.Root;
export const TabsContent = RadixTabs.Content;

export function TabsList({ className, ...rest }: RadixTabs.TabsListProps) {
  return (
    <RadixTabs.List
      className={cn("flex items-end gap-4 border-b border-border", className)}
      {...rest}
    />
  );
}

export function TabsTrigger({ className, ...rest }: RadixTabs.TabsTriggerProps) {
  return (
    <RadixTabs.Trigger
      className={cn(
        "-mb-px h-10 border-b-2 border-transparent px-1 text-small font-medium text-ink-3 transition-colors duration-fast ease-pv",
        "hover:text-ink data-[state=active]:border-ink data-[state=active]:text-ink",
        className,
      )}
      {...rest}
    />
  );
}
