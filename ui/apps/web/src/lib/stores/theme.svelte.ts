/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

const VALID_MODES = ["light", "dark"] as const;
export type ThemeMode = (typeof VALID_MODES)[number];

// NOTE: This key is also used as a literal string in app.html.
// If you rename it here, update app.html too.
export const STORAGE_KEY = "pixano-theme";

function isValidThemeMode(value: string | null): value is ThemeMode {
  return (VALID_MODES as readonly string[]).includes(value as string);
}

function getSystemTheme(): ThemeMode {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

class ThemeStore {
  mode = $state<ThemeMode>("dark");

  constructor() {
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem(STORAGE_KEY);
        this.mode = isValidThemeMode(stored) ? stored : getSystemTheme();
      } catch (_) {
        // localStorage blocked — fall back to system preference
        this.mode = getSystemTheme();
      }
    }
  }

  toggle() {
    this.mode = this.mode === "dark" ? "light" : "dark";
  }
}

export const themeStore = new ThemeStore();
