import type { Metadata } from "next";
import { CreateVoiceWizard } from "@/components/voice/CreateVoiceWizard";

export const metadata: Metadata = { title: "Create your voice" };

export default function CreateVoicePage() {
  return <CreateVoiceWizard />;
}
