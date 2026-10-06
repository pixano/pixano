/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, describe, expect, it, vi } from "vitest";

import { NEW_UI_COOKIE_VALUE, switchToNewUi, UI_VERSION_COOKIE } from "../uiVersion";

describe("switchToNewUi", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("asks the server for the new UI and reloads the root page", () => {
    const fakeDocument = { cookie: "" };
    const fakeWindow = { location: { href: "/#/some/dataset" } };
    vi.stubGlobal("document", fakeDocument);
    vi.stubGlobal("window", fakeWindow);

    switchToNewUi();

    expect(fakeDocument.cookie).toMatch(
      new RegExp(`^${UI_VERSION_COOKIE}=${NEW_UI_COOKIE_VALUE};`),
    );
    expect(fakeDocument.cookie).toContain("path=/");
    expect(fakeWindow.location.href).toBe("/");
  });
});
