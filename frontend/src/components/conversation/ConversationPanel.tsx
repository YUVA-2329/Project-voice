"use client";

import { Mic, MicOff, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { LiveLevels } from "@/components/audio/LiveLevels";
import { Badge, type BadgeTone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { PageHeader } from "@/components/ui/PageHeader";
import { Select, type SelectOption } from "@/components/ui/Select";
import { VoiceSelector, useSelectedVoice } from "@/components/voice/VoiceSelector";
import { useConversationEngines, useMe } from "@/lib/api/hooks";
import type { ConversationState } from "@/lib/api/types";
import { useConversation, type SocketStatus } from "@/lib/conversation/useConversation";
import { cn } from "@/lib/cn";

const STATE_LABEL: Record<ConversationState, string> = {
  idle: "Idle",
  listening: "Listening",
  thinking: "Thinking",
  speaking: "Speaking",
};

const SOCKET_LABEL: Record<SocketStatus, { label: string; tone: BadgeTone }> = {
  disconnected: { label: "Not connected", tone: "neutral" },
  connecting: { label: "Connecting", tone: "processing" },
  connected: { label: "Connected", tone: "success" },
  reconnecting: { label: "Reconnecting", tone: "warning" },
  closed: { label: "Closed", tone: "neutral" },
};

const ENGINE_LABEL: Record<string, { label: string; description: string }> = {
  mirror: { label: "Mirror", description: "Speaks your own words back in your voice." },
  llm: { label: "Assistant", description: "Replies with a language model, in your voice." },
};

export function ConversationPanel() {
  const me = useMe();
  const { selected, readyVoices } = useSelectedVoice();
  const engines = useConversationEngines();
  const [engine, setEngine] = useState<string>("mirror");

  useEffect(() => {
    if (!engines.data) return;
    const current = engines.data.find((e) => e.id === engine);
    if (!current?.available) {
      const first = engines.data.find((e) => e.available);
      if (first) setEngine(first.id);
    }
  }, [engines.data, engine]);

  const conv = useConversation({ voiceId: selected?.id ?? null, engine, language: me.data?.preferences.default_language });
  const active = conv.socket !== "disconnected" && conv.socket !== "closed";
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [conv.turns.length, conv.live.transcript, conv.live.response]);

  const engineOptions: SelectOption<string>[] = (engines.data ?? []).map((e) => ({
    value: e.id,
    label: e.available ? (ENGINE_LABEL[e.id]?.label ?? e.id) : `${ENGINE_LABEL[e.id]?.label ?? e.id} — unavailable`,
    description: e.available ? ENGINE_LABEL[e.id]?.description : (e.reason ?? "Not configured on this server."),
    disabled: !e.available,
  }));
  const noEngine = engines.isSuccess && !engines.data.some((e) => e.available);
  const sock = SOCKET_LABEL[conv.socket];

  return (
    <div className="mx-auto w-full max-w-[720px] px-4 py-10 sm:px-6 sm:py-14 lg:px-10">
      <PageHeader
        title="Conversation"
        description="Turn-based conversation — speak, pause, and your voice replies."
      />

      <div className="flex flex-col gap-8">
        <div className="grid gap-6 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <p className="eyebrow">Voice</p>
            <VoiceSelector />
          </div>
          <div className="flex flex-col gap-1.5">
            <Select<string>
              label="Response engine"
              value={engine}
              onValueChange={setEngine}
              options={engineOptions.length ? engineOptions : [{ value: "mirror", label: "Mirror" }]}
              disabled={active || engines.isPending}
            />
            {engines.isError && <ErrorNote error={engines.error} />}
            {noEngine && <p className="text-micro text-ink-3">No response engine is available on this server.</p>}
          </div>
        </div>

        <div className="flex flex-col gap-4 rounded-md border border-border bg-surface p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <LiveLevels
                analyser={conv.state === "speaking" ? conv.outAnalyser : conv.micAnalyser}
                active={active && (conv.state === "listening" || conv.state === "speaking")}
                size={32}
              />
              <div className="flex flex-col">
                <p className="text-body font-medium text-ink" role="status" aria-live="polite">
                  {active ? STATE_LABEL[conv.state] : "Ready"}
                  {conv.state === "listening" && active && <span aria-hidden className="ml-2 inline-block size-2 rounded-full bg-accent align-middle" />}
                </p>
                <p className="text-micro text-ink-3">
                  {!active && "Press start, then speak. Pause when you are done and the reply follows."}
                  {active && conv.state === "listening" && "Speak now. A pause ends your turn."}
                  {active && conv.state === "thinking" && "Transcribing and preparing the reply."}
                  {active && conv.state === "speaking" && "Speak over it to interrupt."}
                </p>
              </div>
            </div>
            <Badge tone={sock.tone} mono>
              {sock.label}
              {conv.socket === "reconnecting" && conv.reconnectAttempt > 0 ? ` (${conv.reconnectAttempt})` : ""}
            </Badge>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {!active ? (
              <Button
                variant="primary"
                size="lg"
                onClick={() => void conv.start()}
                disabled={!selected || noEngine || readyVoices.length === 0}
                leading={<Mic className="size-4" aria-hidden />}
              >
                Start
              </Button>
            ) : (
              <>
                <Button variant="primary" size="lg" onClick={conv.stop} leading={<MicOff className="size-4" aria-hidden />}>
                  Stop
                </Button>
                <Button size="lg" onClick={conv.endTurn} disabled={conv.state !== "listening"}>
                  End turn
                </Button>
                <Button size="lg" variant="ghost" onClick={conv.interrupt} disabled={conv.state !== "speaking"} leading={<Square className="size-3.5" aria-hidden />}>
                  Interrupt
                </Button>
              </>
            )}
            {!selected && readyVoices.length > 0 && <span className="text-small text-ink-3">Choose a voice to begin.</span>}
          </div>

          {conv.error && <ErrorNote message={conv.error.message} code={conv.error.code} />}
        </div>

        <div ref={scrollRef} className="flex max-h-[50vh] flex-col gap-5 overflow-y-auto" aria-live="polite" aria-label="Conversation transcript">
          {conv.turns.length === 0 && !conv.live.transcript && !conv.live.response && (
            <p className="text-small text-ink-3">Your words and the replies will appear here.</p>
          )}
          {conv.turns.map((t) => (
            <TurnView key={t.id} transcript={t.transcript} response={t.response} />
          ))}
          {(conv.live.transcript || conv.live.response) && (
            <TurnView transcript={conv.live.transcript} response={conv.live.response} live />
          )}
        </div>
      </div>
    </div>
  );
}

function TurnView({ transcript, response, live }: { transcript: string; response: string; live?: boolean }) {
  return (
    <div className={cn("flex flex-col gap-3", live && "animate-in")}>
      {transcript && (
        <div className="flex flex-col gap-1">
          <span className="eyebrow">You</span>
          <p className="text-body text-ink-2">{transcript}</p>
        </div>
      )}
      {response && (
        <div className="flex flex-col gap-1">
          <span className="eyebrow">Your voice</span>
          <p className="text-body text-ink">{response}</p>
        </div>
      )}
    </div>
  );
}
