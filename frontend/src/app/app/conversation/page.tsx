import type { Metadata } from "next";
import { ConversationPanel } from "@/components/conversation/ConversationPanel";

export const metadata: Metadata = { title: "Conversation" };

export default function ConversationPage() {
  return <ConversationPanel />;
}
