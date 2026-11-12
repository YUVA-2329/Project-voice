import type { Metadata } from "next";
import { HistoryList } from "@/components/history/HistoryList";

export const metadata: Metadata = { title: "History" };

export default function HistoryPage() {
  return <HistoryList />;
}
