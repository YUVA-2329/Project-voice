import type { Metadata } from "next";
import { Composer } from "@/components/composer/Composer";

export const metadata: Metadata = { title: "Create" };

export default function AppHomePage() {
  return (
    <div className="mx-auto w-full max-w-[720px] px-4 py-10 sm:px-6 sm:py-14 lg:px-10">
      <Composer />
    </div>
  );
}
