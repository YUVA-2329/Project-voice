"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/Tooltip";
import { ToastProvider } from "@/components/ui/Toast";
import { ensureCsrf, isApiError } from "@/lib/api/client";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 5_000,
        refetchOnWindowFocus: false,
        retry: (count, error) => {
          if (isApiError(error) && error.status >= 400 && error.status < 500) return false;
          return count < 2;
        },
      },
    },
  });
}

export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(makeQueryClient);

  useEffect(() => {
    // Make sure the CSRF cookie exists before the first mutation.
    void ensureCsrf();
  }, []);

  return (
    <QueryClientProvider client={client}>
      <TooltipProvider delayDuration={200}>
        <ToastProvider>{children}</ToastProvider>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
