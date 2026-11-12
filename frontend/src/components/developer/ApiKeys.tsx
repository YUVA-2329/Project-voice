"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { DialogContent, DialogRoot } from "@/components/ui/Dialog";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { Input } from "@/components/ui/Input";
import { Skeleton } from "@/components/ui/Skeleton";
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "@/lib/api/hooks";
import { formatDateTime, formatRelative } from "@/lib/format";
import { CopyButton, Panel } from "./panels";

export function ApiKeys() {
  const q = useApiKeys();
  const create = useCreateApiKey();
  const revoke = useRevokeApiKey();
  const [name, setName] = useState("");
  const [secret, setSecret] = useState<{ name: string; secret: string } | null>(null);
  const [revokeId, setRevokeId] = useState<string | null>(null);

  const active = (q.data ?? []).filter((k) => !k.revoked_at);
  const revoked = (q.data ?? []).filter((k) => k.revoked_at);

  return (
    <Panel title="API keys" meta={`Authorization: Bearer pv_live_…`}>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const n = name.trim();
          if (!n) return;
          create.mutate(n, {
            onSuccess: (res) => {
              setSecret({ name: res.api_key.name, secret: res.secret });
              setName("");
            },
          });
        }}
      >
        <div className="w-full max-w-xs">
          <Input label="New key name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. laptop script" maxLength={60} mono />
        </div>
        <Button type="submit" variant="primary" disabled={!name.trim()} loading={create.isPending}>
          Create key
        </Button>
      </form>
      {create.isError && <ErrorNote error={create.error} />}

      {secret && (
        <div className="flex flex-col gap-2 rounded-md border border-border-strong bg-surface p-4" role="status">
          <p className="text-small text-ink">
            Key <span className="font-medium">{secret.name}</span> created. Copy it now — it is shown only once.
          </p>
          <div className="flex items-center gap-2">
            <code className="flex-1 overflow-x-auto rounded-sm bg-surface-2 px-3 py-2 font-mono text-small text-ink">{secret.secret}</code>
            <CopyButton text={secret.secret} label="Copy secret" />
          </div>
          <div>
            <Button size="sm" variant="ghost" onClick={() => setSecret(null)}>
              Done
            </Button>
          </div>
        </div>
      )}

      {q.isPending && <Skeleton className="h-16 w-full" />}
      {q.isError && <ErrorNote error={q.error} />}
      {q.data && q.data.length === 0 && <p className="text-small text-ink-3">No keys yet.</p>}
      {active.length > 0 && (
        <ul className="divide-y divide-border border-y border-border font-mono text-small">
          {active.map((k) => (
            <li key={k.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <div className="flex min-w-0 flex-col">
                <span className="text-ink">{k.name}</span>
                <span className="text-micro text-ink-3">
                  {k.prefix}… · created {formatDateTime(k.created_at)} · last used {k.last_used_at ? formatRelative(k.last_used_at) : "never"}
                </span>
              </div>
              <Button size="sm" variant="danger" onClick={() => setRevokeId(k.id)}>
                Revoke
              </Button>
            </li>
          ))}
        </ul>
      )}
      {revoked.length > 0 && (
        <details className="font-mono text-small text-ink-3">
          <summary className="cursor-pointer">
            {revoked.length} revoked {revoked.length === 1 ? "key" : "keys"}
          </summary>
          <ul className="mt-2 flex flex-col gap-1">
            {revoked.map((k) => (
              <li key={k.id} className="flex items-center gap-2">
                <Badge tone="neutral" mono>
                  revoked
                </Badge>
                {k.name} · {k.prefix}… · {formatDateTime(k.revoked_at)}
              </li>
            ))}
          </ul>
        </details>
      )}

      <DialogRoot open={Boolean(revokeId)} onOpenChange={(o) => !o && setRevokeId(null)}>
        <DialogContent
          title="Revoke this key?"
          description="Requests using it will fail immediately."
          footer={
            <>
              <Button onClick={() => setRevokeId(null)}>Cancel</Button>
              <Button
                variant="danger"
                loading={revoke.isPending}
                onClick={() => revokeId && revoke.mutate(revokeId, { onSuccess: () => setRevokeId(null) })}
              >
                Revoke
              </Button>
            </>
          }
        >
          {revoke.isError && <ErrorNote error={revoke.error} />}
        </DialogContent>
      </DialogRoot>
    </Panel>
  );
}
