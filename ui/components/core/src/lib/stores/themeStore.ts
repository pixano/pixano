/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { writable } from "svelte/store";

export type ThemeMode = "light" | "dark";

const STORAGE_KEY = "pixano-theme";

function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") return "dark";
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return "dark";
}

function applyTheme(mode: ThemeMode) {
  if (typeof document === "undefined") return;
  document.documentElement.classList.toggle("dark", mode === "dark");
}

export const themeMode = writable<ThemeMode>(getInitialTheme());

export function initTheme() {
  const initial = getInitialTheme();
  themeMode.set(initial);
  applyTheme(initial);

  themeMode.subscribe((mode) => {
    applyTheme(mode);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, mode);
    }
  });
}

export function toggleTheme() {
  themeMode.update((current) => (current === "dark" ? "light" : "dark"));
}
