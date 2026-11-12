import Link from "next/link";
import { Wordmark } from "@/components/brand/Wordmark";

export default function NotFound() {
  return (
    <main className="flex min-h-dvh flex-col items-start justify-center gap-6 px-4 sm:px-6 lg:px-10">
      <Wordmark />
      <h1 className="display text-h1 text-ink">Nothing here.</h1>
      <p className="text-body text-ink-2">That page does not exist. Your voices are still where you left them.</p>
      <Link href="/app" className="text-button font-medium text-ink underline-offset-4 hover:underline">
        Open the app
      </Link>
    </main>
  );
}
