/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Which box the action chip follows as the pointer moves. The chip appears after a short
 * pause on a box, moves to another box after a slightly longer one, and lingers when the
 * pointer leaves a box, so the pointer can travel onto it. While the pointer is on the
 * chip, or its menu is open (frozen), the chip stays where it is.
 */

export type HoverIntentTimers = {
  set: (callback: () => void, delayMs: number) => unknown;
  clear: (handle: unknown) => void;
};

export type HoverIntentDelays = { show: number; switch: number; close: number };

export const CHIP_HOVER_DELAYS: HoverIntentDelays = { show: 100, switch: 150, close: 300 };

const browserTimers: HoverIntentTimers = {
  set: (callback, delayMs) => setTimeout(callback, delayMs),
  clear: (handle) => clearTimeout(handle as ReturnType<typeof setTimeout>),
};

export type ChipHoverIntent = {
  /** The pointer is over the box with this key, or over no box (null). */
  pointerOn(key: string | null): void;
  enterChip(): void;
  leaveChip(): void;
  freeze(): void;
  unfreeze(): void;
  /** Forget everything and drop the chip now. */
  reset(): void;
  readonly key: string | null;
};

export function createChipHoverIntent(
  onChange: (key: string | null) => void,
  timers: HoverIntentTimers = browserTimers,
  delays: HoverIntentDelays = CHIP_HOVER_DELAYS,
): ChipHoverIntent {
  let committed: string | null = null;
  let pointerKey: string | null = null;
  let onChip = false;
  let frozen = false;
  let pending: unknown = null;
  let pendingKey: string | null = null;

  const cancel = () => {
    if (pending === null) return;
    timers.clear(pending);
    pending = null;
  };

  const commit = (key: string | null) => {
    cancel();
    if (key === committed) return;
    committed = key;
    onChange(key);
  };

  const schedule = () => {
    if (frozen || onChip || pointerKey === committed) {
      cancel();
      return;
    }
    // Already heading for this key: let the running delay finish.
    if (pending !== null && pendingKey === pointerKey) return;
    cancel();
    const target = pointerKey;
    const delay = target === null ? delays.close : committed === null ? delays.show : delays.switch;
    pendingKey = target;
    pending = timers.set(() => {
      pending = null;
      commit(target);
    }, delay);
  };

  return {
    pointerOn(key) {
      pointerKey = key;
      schedule();
    },
    enterChip() {
      onChip = true;
      cancel();
    },
    leaveChip() {
      onChip = false;
      schedule();
    },
    freeze() {
      frozen = true;
      cancel();
    },
    unfreeze() {
      frozen = false;
      schedule();
    },
    reset() {
      cancel();
      pointerKey = null;
      onChip = false;
      frozen = false;
      commit(null);
    },
    get key() {
      return committed;
    },
  };
}
