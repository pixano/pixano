/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * What a menu or popover does with a key pressed while it has the focus.
 *
 * The workspace shortcuts listen on the window, so a key typed in a menu reaches them unless the
 * menu stops it: a typeahead letter would switch tools, Space would play the video, an arrow
 * would change frame, and Escape would cancel a drawing in progress.
 *
 * - "close": stop the key and close the menu (Escape on an open menu).
 * - "isolate": stop the key; the menu still handles it.
 * - "pass": let the key through (Tab moves the focus; Escape on a closed trigger is the
 *   workspace's).
 */
export type MenuKeyAction = "close" | "isolate" | "pass";

export function menuKeyAction(key: string, open: boolean): MenuKeyAction {
  if (key === "Tab") return "pass";
  if (key === "Escape") return open ? "close" : "pass";
  return "isolate";
}

/** Apply `menuKeyAction` to a keydown event; `close` closes the menu. */
export function handleMenuKeydown(event: KeyboardEvent, open: boolean, close: () => void): void {
  const action = menuKeyAction(event.key, open);
  if (action === "pass") return;
  event.stopPropagation();
  if (action === "close") {
    event.preventDefault();
    close();
  }
}
