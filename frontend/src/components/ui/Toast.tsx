"use client";

import * as RadixToast from "@radix-ui/react-toast";
import { X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

interface ToastItem {
  id: number;
  title: string;
  description?: string;
  tone?: "neutral" | "danger" | "success";
}

interface ToastApi {
  toast: (t: Omit<ToastItem, "id">) => void;
}

const ToastContext = createContext<ToastApi>({ toast: () => undefined });

export function useToast() {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const toast = useCallback((t: Omit<ToastItem, "id">) => {
    setItems((prev) => [...prev.slice(-3), { ...t, id: Date.now() + Math.random() }]);
  }, []);
  const api = useMemo(() => ({ toast }), [toast]);

  return (
    <ToastContext.Provider value={api}>
      <RadixToast.Provider swipeDirection="right" duration={4500}>
        {children}
        {items.map((t) => (
          <RadixToast.Root
            key={t.id}
            onOpenChange={(open) => {
              if (!open) setItems((prev) => prev.filter((i) => i.id !== t.id));
            }}
            className={cn(
              "flex items-start gap-3 rounded-md border border-border bg-surface p-3 pr-2 shadow-md",
              "data-[state=closed]:animate-out",
            )}
          >
            <span
              aria-hidden
              className={cn(
                "mt-1.5 size-1.5 shrink-0 rounded-full",
                t.tone === "danger" ? "bg-danger" : t.tone === "success" ? "bg-success" : "bg-ink-3",
              )}
            />
            <div className="flex min-w-0 flex-1 flex-col gap-0.5">
              <RadixToast.Title className="text-small font-medium text-ink">{t.title}</RadixToast.Title>
              {t.description && (
                <RadixToast.Description className="text-small text-ink-2">{t.description}</RadixToast.Description>
              )}
            </div>
            <RadixToast.Close
              aria-label="Dismiss"
              className="inline-flex size-8 items-center justify-center rounded-sm text-ink-3 hover:bg-surface-2 hover:text-ink"
            >
              <X className="size-4" aria-hidden />
            </RadixToast.Close>
          </RadixToast.Root>
        ))}
        <RadixToast.Viewport className="fixed bottom-4 right-4 z-[60] flex w-[calc(100vw-32px)] max-w-sm flex-col gap-2 outline-none max-[720px]:bottom-20" />
      </RadixToast.Provider>
    </ToastContext.Provider>
  );
}
