"use client";

import { PageHeader } from "@/components/ui/PageHeader";
import { ApiKeys } from "./ApiKeys";
import { AuditLog } from "./AuditLog";
import { Endpoints } from "./Endpoints";
import { HardwarePanel, ModelStatus, QueuePanel } from "./panels";

export function DeveloperView() {
  return (
    <div className="mx-auto w-full max-w-[1040px] px-4 py-10 sm:px-6 lg:px-10">
      <PageHeader
        title="Developer"
        description="Engines, hardware, queue and keys. Figures refresh every 5 seconds."
        eyebrow={<span className="font-mono normal-case tracking-normal">/api/v1</span>}
      />
      <ModelStatus />
      <div className="grid gap-x-10 md:grid-cols-2">
        <HardwarePanel />
        <QueuePanel />
      </div>
      <ApiKeys />
      <Endpoints />
      <AuditLog />
    </div>
  );
}
