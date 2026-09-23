/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export interface GuardedNavigation {
  from: string;
  to: string;
  fromRecord: string | null;
  toRecord: string | null;
  type: string;
  delta?: number;
  willUnload: boolean;
}

/** One confirmation covers one destination, never a window of unguarded navigation. */
export function createNavigationGuard(onChange?: (pending: GuardedNavigation | null) => void) {
  let pending: GuardedNavigation | null = null;
  let bypass: GuardedNavigation | null = null;

  function clear() {
    pending = null;
    bypass = null;
    onChange?.(null);
  }

  return {
    get pending() {
      return pending;
    },
    intercept(
      navigation: GuardedNavigation,
      state: { isDirty: boolean; isSaving: boolean },
    ): "allow" | "block" | "unload" {
      if (bypass?.from === navigation.from && bypass.to === navigation.to && !state.isSaving) {
        bypass = null;
        return "allow";
      }
      if (!state.isDirty && !state.isSaving) return "allow";
      if (!navigation.fromRecord) return "allow";
      if (!navigation.willUnload && navigation.fromRecord === navigation.toRecord) return "allow";
      if (navigation.willUnload) return "unload";
      if (!pending) {
        pending = navigation;
        onChange?.(pending);
      }
      return "block";
    },
    authorizeDiscard() {
      bypass = pending;
      return pending;
    },
    rearm() {
      bypass = null;
    },
    clear,
  };
}

export function isNavigationCancellation(error: unknown): boolean {
  return (
    error instanceof Error &&
    /navigation (cancelled|canceled|(?:was )?aborted)/i.test(error.message)
  );
}

export async function saveBeforeNavigation(
  guard: ReturnType<typeof createNavigationGuard>,
  save: () => Promise<{ ok: boolean }>,
  isDirty: () => boolean,
  replay: (navigation: GuardedNavigation) => Promise<void>,
): Promise<void> {
  const intent = guard.pending;
  if (!intent) return;
  const result = await save();
  if (result.ok && !isDirty() && guard.pending === intent) {
    try {
      await replay(intent);
    } catch (error) {
      // A newer browser Back/Forward action can supersede the replay after saving.
      // Once clean, there is no unsaved decision left for the old dialog to own.
      if (isNavigationCancellation(error) && !isDirty() && guard.pending === intent) guard.clear();
      throw error;
    }
    if (guard.pending === intent) guard.clear();
  }
}

export async function replayNavigation(
  navigation: GuardedNavigation,
  actions: {
    restoreHistory: () => Promise<void>;
    historyGo: (delta: number) => Promise<void>;
    goto: (url: string) => Promise<void>;
  },
): Promise<void> {
  if (navigation.type === "popstate" && navigation.delta !== undefined) {
    await actions.restoreHistory();
    await actions.historyGo(navigation.delta);
  } else {
    await actions.goto(navigation.to);
  }
}
