"use client";

import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { CopyButton, Panel } from "./panels";

interface Example {
  title: string;
  method: string;
  path: string;
  curl: (origin: string) => string;
}

const EXAMPLES: Example[] = [
  {
    title: "List your voices",
    method: "GET",
    path: "/api/v1/voices",
    curl: (o) => `curl -s ${o}/api/v1/voices \\\n  -H "Authorization: Bearer $PV_API_KEY"`,
  },
  {
    title: "Create a voice (multipart)",
    method: "POST",
    path: "/api/v1/voices",
    curl: (o) =>
      `curl -s ${o}/api/v1/voices \\\n  -H "Authorization: Bearer $PV_API_KEY" \\\n  -F "file=@sample.wav" \\\n  -F "name=My voice" \\\n  -F "language_hint=auto" \\\n  -F "consent_confirmed=true" \\\n  -F "consent_text_version=v1"`,
  },
  {
    title: "Generate speech",
    method: "POST",
    path: "/api/v1/generations",
    curl: (o) =>
      `curl -s ${o}/api/v1/generations \\\n  -H "Authorization: Bearer $PV_API_KEY" \\\n  -H "Content-Type: application/json" \\\n  -H "Idempotency-Key: $(uuidgen)" \\\n  -d '{"voice_id":"<voice_id>","text":"Hello from my own voice.","output_format":"wav"}'`,
  },
  {
    title: "Poll a generation",
    method: "GET",
    path: "/api/v1/generations/{id}",
    curl: (o) => `curl -s ${o}/api/v1/generations/<generation_id> \\\n  -H "Authorization: Bearer $PV_API_KEY"`,
  },
  {
    title: "Download the audio",
    method: "GET",
    path: "/api/v1/generations/{id}/audio?download=1",
    curl: (o) => `curl -s -o out.wav "${o}/api/v1/generations/<generation_id>/audio?download=1" \\\n  -H "Authorization: Bearer $PV_API_KEY"`,
  },
];

export function Endpoints() {
  const [origin, setOrigin] = useState("https://your-host");
  useEffect(() => setOrigin(window.location.origin), []);

  return (
    <Panel
      title="Endpoints"
      meta={
        <a href="/api/docs" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-ink-2 underline-offset-4 hover:text-ink hover:underline">
          /api/docs
          <ExternalLink className="size-3" aria-hidden />
        </a>
      }
    >
      <p className="text-small text-ink-2">
        Every route lives under <code className="font-mono text-ink">/api/v1</code>. Errors come back as{" "}
        <code className="font-mono text-ink">{`{"error":{"code","message","details"}}`}</code>; lists are paginated with{" "}
        <code className="font-mono text-ink">?limit=&amp;offset=</code>.
      </p>
      <ul className="flex flex-col gap-4">
        {EXAMPLES.map((ex) => (
          <li key={ex.title} className="flex flex-col gap-2">
            <div className="flex items-center justify-between gap-2">
              <p className="flex items-baseline gap-2 font-mono text-small">
                <span className="text-micro font-medium text-ink-3">{ex.method}</span>
                <span className="text-ink">{ex.path}</span>
                <span className="text-ink-3">— {ex.title}</span>
              </p>
              <CopyButton text={ex.curl(origin)} label={`Copy curl for ${ex.title}`} />
            </div>
            <pre className="overflow-x-auto rounded-sm border border-border bg-surface-2 p-3 font-mono text-micro leading-relaxed text-ink-2">
              {ex.curl(origin)}
            </pre>
          </li>
        ))}
      </ul>
    </Panel>
  );
}
