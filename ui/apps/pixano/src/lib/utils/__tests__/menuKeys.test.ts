/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it, vi } from "vitest";

import { handleMenuKeydown, menuKeyAction } from "../menuKeys";

function keydown(key: string) {
  return {
    key,
    stopPropagation: vi.fn(),
    preventDefault: vi.fn(),
  } as unknown as KeyboardEvent & {
    stopPropagation: ReturnType<typeof vi.fn>;
    preventDefault: ReturnType<typeof vi.fn>;
  };
}

describe("menuKeyAction", () => {
  it("keeps letters, Space, Enter and arrows away from the workspace shortcuts", () => {
    for (const key of ["e", "B", " ", "Enter", "ArrowLeft", "ArrowRight", "ArrowDown", "Home"]) {
      expect(menuKeyAction(key, true)).toBe("isolate");
      expect(menuKeyAction(key, false)).toBe("isolate");
    }
  });

  it("closes an open menu on Escape, and lets Escape through when it is closed", () => {
    expect(menuKeyAction("Escape", true)).toBe("close");
    expect(menuKeyAction("Escape", false)).toBe("pass");
  });

  it("lets Tab move the focus", () => {
    expect(menuKeyAction("Tab", true)).toBe("pass");
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

  it("leaves a passed key alone", () => {
    const event = keydown("Tab");

    handleMenuKeydown(event, true, vi.fn());

    expect(event.stopPropagation).not.toHaveBeenCalled();
  });
});
