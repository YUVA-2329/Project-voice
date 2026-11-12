"use client";

import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { Skeleton } from "@/components/ui/Skeleton";
import { useAudit } from "@/lib/api/hooks";
import { formatDateTime } from "@/lib/format";
import { Panel } from "./panels";

export function AuditLog() {
  const q = useAudit();
  const items = q.data?.pages.flatMap((p) => p.items) ?? [];
  const total = q.data?.pages[0]?.total ?? 0;

  return (
    <Panel title="Audit" meta={total ? `${total} events` : null}>
      {q.isPending && <Skeleton className="h-24 w-full" />}
      {q.isError && <ErrorNote error={q.error} />}
      {q.isSuccess && items.length === 0 && <p className="text-small text-ink-3">No events recorded yet.</p>}
      {items.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse font-mono text-small">
            <thead>
              <tr className="text-left text-micro text-ink-3">
                <th className="pb-2 pr-4 font-medium">time</th>
                <th className="pb-2 pr-4 font-medium">action</th>
                <th className="pb-2 pr-4 font-medium">resource</th>
                <th className="pb-2 font-medium">ip</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border border-t border-border">
              {items.map((e) => (
                <tr key={e.id}>
                  <td className="whitespace-nowrap py-2 pr-4 tabular text-ink-3">{formatDateTime(e.created_at)}</td>
                  <td className="py-2 pr-4 text-ink">{e.action}</td>
                  <td className="py-2 pr-4 text-ink-2">
                    {e.resource_type ? (
                      <>
                        {e.resource_type}
                        {e.resource_id && <span className="text-ink-3"> {e.resource_id.slice(0, 8)}…</span>}
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="py-2 text-ink-3">{e.ip ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {q.hasNextPage && (
        <div>
          <Button size="sm" onClick={() => q.fetchNextPage()} loading={q.isFetchingNextPage}>
            Load more
          </Button>
        </div>
      )}
    </Panel>
  );
}
