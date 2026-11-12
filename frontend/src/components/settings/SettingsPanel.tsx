"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { DialogContent, DialogRoot } from "@/components/ui/Dialog";
import { ErrorNote } from "@/components/ui/ErrorNote";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Select } from "@/components/ui/Select";
import { Slider } from "@/components/ui/Slider";
import { useToast } from "@/components/ui/Toast";
import { useLanguageOptions } from "@/components/voice/VoiceNameField";
import { useDeleteMe, useLogout, useMe, useUpdateMe } from "@/lib/api/hooks";
import type { Mode, OutputFormat, Theme, User, UserPreferences } from "@/lib/api/types";
import { useAppStore } from "@/lib/store";
import { applyTheme } from "@/lib/theme";

export function SettingsPanel() {
  const me = useMe();
  if (!me.data) return null;
  return <SettingsForm user={me.data} />;
}

function Section({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <section className="grid gap-6 border-t border-border py-8 md:grid-cols-[220px_1fr]">
      <div className="flex flex-col gap-1">
        <h2 className="text-h3 font-medium text-ink">{title}</h2>
        {description && <p className="text-small text-ink-3">{description}</p>}
      </div>
      <div className="flex max-w-md flex-col gap-5">{children}</div>
    </section>
  );
}

function SettingsForm({ user }: { user: User }) {
  const update = useUpdateMe();
  const logout = useLogout();
  const remove = useDeleteMe();
  const { toast } = useToast();
  const setMode = useAppStore((s) => s.setMode);
  const { options: languageOptions } = useLanguageOptions();

  const [displayName, setDisplayName] = useState(user.display_name);
  const [speed, setSpeed] = useState(user.preferences.speed);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [password, setPassword] = useState("");

  useEffect(() => setDisplayName(user.display_name), [user.display_name]);
  useEffect(() => setSpeed(user.preferences.speed), [user.preferences.speed]);

  const savePrefs = (patch: Partial<UserPreferences>) => {
    update.mutate(
      { preferences: patch },
      {
        onError: (e) => toast({ title: "Could not save", description: e instanceof Error ? e.message : undefined, tone: "danger" }),
      },
    );
  };

  const saveName = () => {
    const next = displayName.trim();
    if (!next || next === user.display_name) return;
    update.mutate({ display_name: next }, { onSuccess: () => toast({ title: "Name updated" }) });
  };

  const signOut = () => {
    logout.mutate(undefined, {
      onSettled: () => {
        useAppStore.getState().setSelectedVoiceId(null);
        window.location.assign("/");
      },
    });
  };

  return (
    <div className="mx-auto w-full max-w-[1040px] px-4 py-10 sm:px-6 lg:px-10">
      <PageHeader title="Settings" description="Your account and how the app behaves." />

      <Section title="Profile" description="How we address you.">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            saveName();
          }}
          className="flex flex-col gap-4"
        >
          <Input label="Display name" value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={60} />
          <Input label="Email" value={user.email} readOnly disabled mono hint="Email cannot be changed here." />
          <div>
            <Button type="submit" variant="primary" disabled={!displayName.trim() || displayName.trim() === user.display_name} loading={update.isPending && update.variables?.display_name != null}>
              Save name
            </Button>
          </div>
        </form>
      </Section>

      <Section title="Preferences" description="Defaults for every generation. Saved as you change them.">
        <Select
          label="Default language"
          value={user.preferences.default_language}
          onValueChange={(v) => savePrefs({ default_language: v })}
          options={languageOptions}
        />
        <Select<OutputFormat>
          label="Output format"
          value={user.preferences.output_format}
          onValueChange={(v) => savePrefs({ output_format: v })}
          options={[
            { value: "wav", label: "WAV", description: "Lossless, largest files." },
            { value: "flac", label: "FLAC", description: "Lossless, compressed." },
            { value: "mp3", label: "MP3", description: "Smallest, lossy." },
          ]}
        />
        <Slider
          label="Speed"
          min={0.5}
          max={2}
          step={0.05}
          value={speed}
          onValueChange={setSpeed}
          format={(v) => `${v.toFixed(2)}×`}
        />
        {Math.abs(speed - user.preferences.speed) > 0.001 && (
          <div className="-mt-2 flex items-center gap-2">
            <Button size="sm" variant="primary" onClick={() => savePrefs({ speed: Number(speed.toFixed(2)) })} loading={update.isPending && update.variables?.preferences?.speed != null}>
              Save speed
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setSpeed(user.preferences.speed)}>
              Reset
            </Button>
          </div>
        )}
        <Select<Theme>
          label="Theme"
          value={user.preferences.theme}
          onValueChange={(v) => {
            applyTheme(v);
            savePrefs({ theme: v });
          }}
          options={[
            { value: "system", label: "System" },
            { value: "light", label: "Light" },
            { value: "dark", label: "Dark" },
          ]}
        />
        <Select<Mode>
          label="Composer mode"
          value={user.preferences.mode}
          onValueChange={(v) => {
            setMode(v);
            savePrefs({ mode: v });
          }}
          options={[
            { value: "simple", label: "Simple", description: "Choose a voice, write, run." },
            { value: "advanced", label: "Advanced", description: "Language, speed, format, quality and engine controls." },
          ]}
        />
        {update.isError && <ErrorNote error={update.error} />}
      </Section>

      <Section title="Session">
        <div>
          <Button onClick={signOut} loading={logout.isPending}>
            Sign out
          </Button>
        </div>
      </Section>

      <Section title="Danger zone" description="Deleting your account removes your voices, generations and files. This cannot be undone.">
        <div>
          <Button variant="danger" onClick={() => setDeleteOpen(true)}>
            Delete account
          </Button>
        </div>
      </Section>

      <DialogRoot open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent
          title="Delete your account?"
          description="Every voice, generation and file is removed permanently. Enter your password to confirm."
          footer={
            <>
              <Button onClick={() => setDeleteOpen(false)}>Cancel</Button>
              <Button
                variant="danger"
                disabled={!password}
                loading={remove.isPending}
                onClick={() =>
                  remove.mutate(password, {
                    onSuccess: () => {
                      useAppStore.getState().setSelectedVoiceId(null);
                      window.location.assign("/");
                    },
                  })
                }
              >
                Delete everything
              </Button>
            </>
          }
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (password) remove.mutate(password);
            }}
            className="flex flex-col gap-3"
          >
            <Input label="Password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            {remove.isError && <ErrorNote error={remove.error} />}
          </form>
        </DialogContent>
      </DialogRoot>
    </div>
  );
}
