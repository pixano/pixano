/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { DatasetInfo, DatasetSchema, Source } from "$lib/types/dataset";

import { reactiveStore } from "./reactiveStore.svelte";

// ─── Dataset Stores ─────────────────────────────────────────────────────────────

export const currentDatasetStore = reactiveStore<DatasetInfo | undefined>(undefined);
export const datasetSchema = reactiveStore<DatasetSchema | undefined>(undefined);
export const sourcesStore = reactiveStore<Source[]>([]);
export const datasetsStore = reactiveStore<DatasetInfo[]>([]);
export const datasetFilter = reactiveStore<string>("");
export const datasetItemIds = reactiveStore<Array<string>>([]);
export const datasetTotalItemsCount = reactiveStore<number>(0);
export const saveCurrentItemStore = reactiveStore<{ shouldSave: boolean; canSave: boolean }>({
  shouldSave: false,
  canSave: false,
});

// ─── Theme Store ────────────────────────────────────────────────────────────────

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

export const themeMode = reactiveStore<ThemeMode>(getInitialTheme());

// Apply initial theme eagerly at module level
applyTheme(getInitialTheme());

// Sync theme changes to DOM + localStorage via a detached root effect
$effect.root(() => {
  $effect(() => {
    applyTheme(themeMode.value);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, themeMode.value);
    }
  });
});

export function toggleTheme() {
  themeMode.value = themeMode.value === "dark" ? "light" : "dark";
}
