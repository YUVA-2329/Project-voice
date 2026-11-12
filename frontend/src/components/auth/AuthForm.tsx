"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Wordmark } from "@/components/brand/Wordmark";
import { Button } from "@/components/ui/Button";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { Input } from "@/components/ui/Input";
import { isApiError } from "@/lib/api/client";
import { useLogin, useRegister } from "@/lib/api/hooks";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PASSWORD_MIN = 10;
const PASSWORD_MAX = 128;

function safeNext(raw: string | null): string {
  if (!raw) return "/app";
  // Only allow same-origin app paths.
  if (raw.startsWith("/app") && !raw.startsWith("//")) return raw;
  return "/app";
}

export function AuthForm({ kind }: { kind: "login" | "register" }) {
  const router = useRouter();
  const params = useSearchParams();
  const next = safeNext(params.get("next"));
  const login = useLogin();
  const register = useRegister();
  const mutation = kind === "login" ? login : register;

  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const emailError = !email ? "Enter your email." : !EMAIL_RE.test(email) ? "That does not look like an email address." : null;
  const nameError = kind === "register" && !displayName.trim() ? "Enter the name we should show." : null;
  const passwordError = !password
    ? "Enter your password."
    : kind === "register" && password.length < PASSWORD_MIN
      ? `Use at least ${PASSWORD_MIN} characters.`
      : password.length > PASSWORD_MAX
        ? `Use at most ${PASSWORD_MAX} characters.`
        : null;
  const valid = !emailError && !nameError && !passwordError;

  const serverFields = isApiError(mutation.error) ? mutation.error.fieldErrors() : {};
  const serverCode = isApiError(mutation.error) ? mutation.error.code : null;
  const showGeneralError = mutation.isError && Object.keys(serverFields).length === 0;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setTouched({ email: true, display_name: true, password: true });
    if (!valid) return;
    const normalisedEmail = email.trim().toLowerCase();
    const onSuccess = () => router.replace(next);
    if (kind === "login") {
      login.mutate({ email: normalisedEmail, password }, { onSuccess });
    } else {
      register.mutate({ email: normalisedEmail, password, display_name: displayName.trim() }, { onSuccess });
    }
  };

  const show = (field: string, local: string | null) => (touched[field] ? (serverFields[field] ?? local) : serverFields[field]);

  return (
    <main className="flex min-h-dvh flex-col bg-bg">
      <header className="flex h-14 items-center px-4 sm:px-6 lg:px-10">
        <Wordmark />
      </header>
      <section className="flex flex-1 items-center justify-center px-4 pb-24 pt-8">
        <form onSubmit={onSubmit} noValidate className="flex w-full max-w-sm flex-col gap-6">
          <div className="flex flex-col gap-2">
            <h1 className="display text-h1 text-ink">{kind === "login" ? "Welcome back." : "Create your account."}</h1>
            <p className="text-body text-ink-2">
              {kind === "login" ? "Sign in to use your voice." : "One account, all your voices."}
            </p>
          </div>

          <div className="flex flex-col gap-4">
            <Input
              label="Email"
              type="email"
              name="email"
              autoComplete="email"
              inputMode="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, email: true }))}
              error={show("email", emailError)}
              required
            />
            {kind === "register" && (
              <Input
                label="Display name"
                name="display_name"
                autoComplete="nickname"
                value={displayName}
                maxLength={60}
                onChange={(e) => setDisplayName(e.target.value)}
                onBlur={() => setTouched((t) => ({ ...t, display_name: true }))}
                error={show("display_name", nameError)}
                required
              />
            )}
            <Input
              label="Password"
              type="password"
              name="password"
              autoComplete={kind === "login" ? "current-password" : "new-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onBlur={() => setTouched((t) => ({ ...t, password: true }))}
              error={show("password", passwordError)}
              hint={kind === "register" ? `${PASSWORD_MIN}–${PASSWORD_MAX} characters.` : undefined}
              required
            />
          </div>

          {showGeneralError && <ErrorNote error={mutation.error} code={serverCode} />}

          <Button type="submit" variant="primary" size="lg" block loading={mutation.isPending}>
            {kind === "login" ? "Sign in" : "Create account"}
          </Button>

          <p className="text-small text-ink-2">
            {kind === "login" ? (
              <>
                New here?{" "}
                <Link href={`/register${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-medium text-ink underline-offset-4 hover:underline">
                  Create an account
                </Link>
              </>
            ) : (
              <>
                Already have an account?{" "}
                <Link href={`/login${params.get("next") ? `?next=${encodeURIComponent(next)}` : ""}`} className="font-medium text-ink underline-offset-4 hover:underline">
                  Sign in
                </Link>
              </>
            )}
          </p>
        </form>
      </section>
    </main>
  );
}
