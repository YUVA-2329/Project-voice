import type { Metadata } from "next";
import { VoiceLibrary } from "@/components/voice/VoiceLibrary";

export const metadata: Metadata = { title: "My voices" };

export default function VoicesPage() {
  return <VoiceLibrary />;
}
