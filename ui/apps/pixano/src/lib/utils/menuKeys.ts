/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * What a menu or popover does with a key pressed while it, or its trigger, has the focus.
 *
 * The workspace shortcuts listen on the window, so a key typed in an open menu reaches them unless
 * the menu stops it: a typeahead letter would switch tools, Space would play the video, an arrow
 * would change frame, and Escape would cancel a drawing in progress.
 *
 * - "close": stop the key and close the menu (Escape on an open menu).
 * - "isolate": stop the key; the menu or its trigger still handles it.
 * - "pass": let the key through. The save shortcut always passes. Tab moves the focus. A closed
 *   trigger keeps only the keys that open it, so the shortcuts keep working while it has the
 *   focus, which it keeps after a choice.
 */
export type MenuKeyAction = "close" | "isolate" | "pass";

export type MenuKey = Pick<KeyboardEvent, "key" | "ctrlKey" | "metaKey">;

/** Keys that open a closed Select from its trigger. */
export const SELECT_TRIGGER_KEYS: readonly string[] = ["Enter", " ", "ArrowUp", "ArrowDown"];
/** Keys that open a closed popover from its trigger button. */
export const BUTTON_TRIGGER_KEYS: readonly string[] = ["Enter", " "];

export function menuKeyAction(
  event: MenuKey,
  open: boolean,
  triggerKeys: readonly string[] = [],
): MenuKeyAction {
  if (event.key === "Tab") return "pass";
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") return "pass";
  if (event.key === "Escape") return open ? "close" : "pass";
  if (open) return "isolate";
  return triggerKeys.includes(event.key) ? "isolate" : "pass";
}

/** Apply `menuKeyAction` to a keydown event; `close` closes the menu. */
export function handleMenuKeydown(
  event: KeyboardEvent,
  open: boolean,
  close: () => void,
  triggerKeys: readonly string[] = [],
): void {
  const action = menuKeyAction(event, open, triggerKeys);
  if (action === "pass") return;
  event.stopPropagation();
  if (action === "close") {
    event.preventDefault();
    close();
  }
}
