"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { Mode } from "./api/types";

export interface AppState {
  selectedVoiceId: string | null;
  mode: Mode;
  setSelectedVoiceId: (id: string | null) => void;
  setMode: (mode: Mode) => void;
}

export const STORE_KEY = "pv-app";

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      selectedVoiceId: null,
      mode: "simple",
      setSelectedVoiceId: (id) => set({ selectedVoiceId: id }),
      setMode: (mode) => set({ mode }),
    }),
    {
      name: STORE_KEY,
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ selectedVoiceId: s.selectedVoiceId, mode: s.mode }),
    },
  ),
);
