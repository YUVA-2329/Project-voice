"use client";

import { Check, Copy } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { IconButton } from "@/components/ui/IconButton";
import { Skeleton } from "@/components/ui/Skeleton";
import { isApiError } from "@/lib/api/client";
import { useHardware, useHealth, useMetrics, useModels } from "@/lib/api/hooks";
import { LANGUAGE_NAMES } from "@/lib/api/types";
import { cn } from "@/lib/cn";
import { formatMegabytes, formatRelative, formatRtf } from "@/lib/format";

export const DEV_POLL_MS = 5000;

export function Panel({ title, meta, children, className }: { title: string; meta?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn("flex flex-col gap-4 border-t border-border py-6", className)} aria-label={title}>
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="eyebrow">{title}</h2>
        {meta && <div className="font-mono text-micro text-ink-3">{meta}</div>}
      </div>
      {children}
    </section>
  );
}

export function KV({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1.5 font-mono text-small">
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-ink-3">{k}</dt>
          <dd className="tabular text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <IconButton
      label={done ? "Copied" : label}
      size="sm"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setDone(true);
          window.setTimeout(() => setDone(false), 1500);
        } catch {
          /* clipboard unavailable */
        }
      }}
    >
      {done ? <Check className="size-4 text-success" aria-hidden /> : <Copy className="size-4" aria-hidden />}
    </IconButton>
  );
}

// ---------------------------------------------------------------------------------------------

export function ModelStatus() {
  const q = useModels({ refetchInterval: DEV_POLL_MS });
  return (
    <Panel title="Models" meta={q.dataUpdatedAt ? `updated ${formatRelative(new Date(q.dataUpdatedAt).toISOString())}` : null}>
      {q.isPending && <Skeleton className="h-24 w-full" />}
      {q.isError && <ErrorNote error={q.error} />}
      {q.data && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse font-mono text-small">
            <thead>
              <tr className="text-left text-micro text-ink-3">
                <th className="pb-2 pr-4 font-medium">engine</th>
                <th className="pb-2 pr-4 font-medium">status</th>
                <th className="pb-2 pr-4 font-medium">languages</th>
                <th className="pb-2 pr-4 font-medium">device</th>
                <th className="pb-2 pr-4 font-medium">rtf</th>
                <th className="pb-2 pr-4 font-medium">infer</th>
                <th className="pb-2 font-medium">licence</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border border-t border-border">
              {q.data.map((m) => (
                <tr key={m.id} className="align-top">
                  <td className="py-2 pr-4">
                    <div className="text-ink">{m.id}</div>
                    <div className="text-micro text-ink-3">
                      {m.name} {m.version}
                    </div>
                  </td>
                  <td className="py-2 pr-4">
                    {m.available ? (
                      <Badge tone={m.loaded ? "success" : "neutral"} mono>
                        {m.loaded ? "loaded" : "available"}
                      </Badge>
                    ) : (
                      <div className="flex flex-col gap-1">
                        <Badge tone="warning" mono>
                          unavailable
                        </Badge>
                        {m.unavailable_reason && <span className="max-w-56 text-micro text-ink-3">{m.unavailable_reason}</span>}
                      </div>
                    )}
                  </td>
                  <td className="py-2 pr-4 text-ink-2">
                    {m.tts_languages.map((l) => LANGUAGE_NAMES[l]?.name ?? l).join(", ") || "—"}
                    {m.cross_lingual && <div className="text-micro text-ink-3">cross-lingual</div>}
                  </td>
                  <td className="py-2 pr-4 text-ink-2">{m.device ?? "—"}</td>
                  <td className="py-2 pr-4 tabular text-ink-2">{formatRtf(m.stats.avg_rtf)}</td>
                  <td className="py-2 pr-4 tabular text-ink-2">{m.stats.inferences}</td>
                  <td className="py-2 text-micro text-ink-3">
                    {m.licence}
                    <div>{m.weight_licence}</div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

export function HardwarePanel() {
  const q = useHardware({ refetchInterval: DEV_POLL_MS });
  const unavailable = q.isError && isApiError(q.error) && q.error.status === 503;
  return (
    <Panel title="Hardware">
      {q.isPending && <Skeleton className="h-24 w-full" />}
      {unavailable && (
        <div className="flex flex-col gap-1">
          <p className="text-small text-ink-2">The API image does not include the engine package, so hardware details are not reported here.</p>
          <p className="font-mono text-micro text-ink-3">{isApiError(q.error) ? q.error.code : "engine_unavailable"}</p>
        </div>
      )}
      {q.isError && !unavailable && <ErrorNote error={q.error} />}
      {q.data && (
        <KV
          rows={[
            ["device", q.data.device + (q.data.cuda_available ? " (cuda available)" : "")],
            ["gpu", q.data.gpu ? `${q.data.gpu.name} · ${formatMegabytes(q.data.gpu.vram_used_mb)} / ${formatMegabytes(q.data.gpu.vram_total_mb)}` : "none"],
            ["cpu", `${q.data.cpu_cores} cores`],
            ["ram", `${formatMegabytes(q.data.ram_used_mb)} / ${formatMegabytes(q.data.ram_total_mb)}`],
            ["disk free", formatMegabytes(q.data.disk_free_mb)],
            ["torch", q.data.torch_version ?? "—"],
            ["onnxruntime", q.data.onnxruntime_version ?? "—"],
          ]}
        />
      )}
    </Panel>
  );
}

export function QueuePanel() {
  const q = useMetrics({ refetchInterval: DEV_POLL_MS });
  const health = useHealth({ refetchInterval: DEV_POLL_MS });
  return (
    <Panel
      title="Queue"
      meta={
        health.data ? (
          <span className={health.data.status === "ok" ? "text-success" : "text-warning"}>
            api {health.data.status} · v{health.data.version}
          </span>
        ) : null
      }
    >
      {q.isPending && <Skeleton className="h-24 w-full" />}
      {q.isError && <ErrorNote error={q.error} />}
      {q.data && (
        <div className="flex flex-col gap-5">
          <KV
            rows={[
              ["voice queue", q.data.queues.voice],
              ["generation queue", q.data.queues.generation],
              ["voices", q.data.voices_total],
              ["24h generations", `${q.data.generations_24h.total} · ${q.data.generations_24h.completed} ok · ${q.data.generations_24h.failed} failed`],
              ["24h avg rtf", formatRtf(q.data.generations_24h.avg_rtf)],
            ]}
          />
          <div className="flex flex-col gap-1.5 border-t border-border pt-4 font-mono text-small">
            <span className="text-ink-3">workers</span>
            {q.data.workers.length === 0 && <span className="text-warning">no worker heartbeat</span>}
            {q.data.workers.map((w) => (
              <div key={w.name} className="flex flex-wrap items-baseline gap-x-3">
                <span className="text-ink">{w.name}</span>
                <span className="text-ink-3">{formatRelative(w.last_heartbeat)}</span>
                <span className="text-ink-2">{w.loaded_engine ?? "idle"}</span>
              </div>
            ))}
          </div>
        </div>
      )}
      {q.data && (
        <div className="pt-1">
          <Button size="sm" variant="ghost" onClick={() => void q.refetch()} loading={q.isFetching}>
            Refresh
          </Button>
        </div>
      )}
    </Panel>
  );
}
