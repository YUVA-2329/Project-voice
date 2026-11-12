"use client";

import { useEffect, useState } from "react";
import { Composer } from "@/components/composer/Composer";
import { Badge } from "@/components/ui/Badge";
import { useSelectedVoice } from "@/components/voice/VoiceSelector";
import { useMe } from "@/lib/api/hooks";
import { LANGUAGE_NAMES } from "@/lib/api/types";
import { AdvancedControls, type AdvancedParams } from "./AdvancedControls";

export function AdvancedComposer() {
  const me = useMe();
  const { selected } = useSelectedVoice();
  const [params, setParams] = useState<AdvancedParams>({
    language: "auto",
    speed: 1,
    output_format: "wav",
    quality: "balanced",
    engine_id: undefined,
  });
  const [seeded, setSeeded] = useState(false);

  // Seed controls from the user's saved preferences once.
  useEffect(() => {
    if (seeded || !me.data) return;
    const p = me.data.preferences;
    setParams((prev) => ({
      ...prev,
      language: p.default_language,
      speed: p.speed,
      output_format: p.output_format,
      engine_id: p.default_engine ?? undefined,
    }));
    setSeeded(true);
  }, [me.data, seeded]);

  const langChip =
    params.language === "auto" ? "Auto" : (LANGUAGE_NAMES[params.language]?.name ?? params.language);

  return (
    <div className="mx-auto w-full max-w-[720px] px-4 py-10 sm:px-6 sm:py-14 lg:px-10">
      <Composer
        advanced
        params={params}
        chips={
          <Badge dot={false} className="h-6">
            {langChip}
            {params.speed !== 1 ? ` · ${params.speed.toFixed(2)}×` : ""}
            {` · ${params.output_format.toUpperCase()}`}
          </Badge>
        }
        controls={<AdvancedControls params={params} onChange={setParams} voice={selected} />}
      />
    </div>
  );
}
