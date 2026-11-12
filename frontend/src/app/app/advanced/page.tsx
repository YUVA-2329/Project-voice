import type { Metadata } from "next";
import { AdvancedComposer } from "@/components/advanced/AdvancedComposer";

export const metadata: Metadata = { title: "Advanced" };

export default function AdvancedPage() {
  return <AdvancedComposer />;
}
