/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi, type Mock } from "vitest";

import {
  BUTTON_TRIGGER_KEYS,
  handleMenuKeydown,
  menuKeyAction,
  SELECT_TRIGGER_KEYS,
} from "../menuKeys";

const key = (value: string, modifiers: { ctrlKey?: boolean; metaKey?: boolean } = {}) => ({
  key: value,
  ctrlKey: false,
  metaKey: false,
  ...modifiers,
});

// Replacing the event methods with mocks keeps them properties rather than
// methods, which is what lets the assertions reference them unbound.
type MockKeydownEvent = Omit<KeyboardEvent, "preventDefault" | "stopPropagation"> & {
  preventDefault: Mock;
  stopPropagation: Mock;
};

function keydown(value: string, modifiers: { ctrlKey?: boolean; metaKey?: boolean } = {}) {
  return {
    ...key(value, modifiers),
    stopPropagation: vi.fn(),
    preventDefault: vi.fn(),
  } as unknown as MockKeydownEvent;
}

describe("menuKeyAction", () => {
  it("keeps every key of an open menu away from the workspace shortcuts", () => {
    for (const value of ["e", "B", " ", "Enter", "ArrowLeft", "ArrowRight", "ArrowDown", "Home"]) {
      expect(menuKeyAction(key(value), true)).toBe("isolate");
    }
  });

  it("closes an open menu on Escape, and lets Escape through when it is closed", () => {
    expect(menuKeyAction(key("Escape"), true)).toBe("close");
    expect(menuKeyAction(key("Escape"), false, SELECT_TRIGGER_KEYS)).toBe("pass");
  });

  it("lets the save shortcut and Tab through, open or closed", () => {
    for (const open of [true, false]) {
      expect(menuKeyAction(key("s", { metaKey: true }), open, SELECT_TRIGGER_KEYS)).toBe("pass");
      expect(menuKeyAction(key("S", { ctrlKey: true }), open, SELECT_TRIGGER_KEYS)).toBe("pass");
      expect(menuKeyAction(key("Tab"), open, SELECT_TRIGGER_KEYS)).toBe("pass");
    }
  });

  it("keeps other modified keys inside an open menu", () => {
    expect(menuKeyAction(key("a", { metaKey: true }), true)).toBe("isolate");
    expect(menuKeyAction(key("ArrowRight", { ctrlKey: true }), true)).toBe("isolate");
  });

  it("keeps only the keys that open a closed trigger", () => {
    for (const value of SELECT_TRIGGER_KEYS) {
      expect(menuKeyAction(key(value), false, SELECT_TRIGGER_KEYS)).toBe("isolate");
    }
    for (const value of ["e", "b", "ArrowLeft", "ArrowRight", "d", "Alt", "Backspace"]) {
      expect(menuKeyAction(key(value), false, SELECT_TRIGGER_KEYS)).toBe("pass");
    }
    expect(menuKeyAction(key(" "), false, BUTTON_TRIGGER_KEYS)).toBe("isolate");
    expect(menuKeyAction(key("ArrowDown"), false, BUTTON_TRIGGER_KEYS)).toBe("pass");
  });
});

describe("handleMenuKeydown", () => {
  it("stops an isolated key without preventing the menu from handling it", () => {
    const event = keydown("e");
    const close = vi.fn();

    handleMenuKeydown(event, true, close);

    expect(event.stopPropagation).toHaveBeenCalled();
    expect(event.preventDefault).not.toHaveBeenCalled();
    expect(close).not.toHaveBeenCalled();
  });

  it("closes the menu on Escape without letting it cancel a drawing", () => {
    const event = keydown("Escape");
    const close = vi.fn();

    handleMenuKeydown(event, true, close);

    expect(event.stopPropagation).toHaveBeenCalled();
    expect(event.preventDefault).toHaveBeenCalled();
    expect(close).toHaveBeenCalled();
  });

  // Regression: the save shortcut was swallowed, so the browser offered to save the page.
  it("leaves the save shortcut to the workspace", () => {
    const event = keydown("s", { metaKey: true });

    handleMenuKeydown(event, false, vi.fn(), SELECT_TRIGGER_KEYS);

    expect(event.stopPropagation).not.toHaveBeenCalled();
    expect(event.preventDefault).not.toHaveBeenCalled();
  });

  it("leaves a tool shortcut alone on a closed trigger", () => {
    const event = keydown("b");

    handleMenuKeydown(event, false, vi.fn(), SELECT_TRIGGER_KEYS);

    expect(event.stopPropagation).not.toHaveBeenCalled();
  });
});
