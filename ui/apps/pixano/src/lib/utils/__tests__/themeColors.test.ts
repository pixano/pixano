/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, describe, expect, it, vi } from "vitest";

import { readTokens, tokenColor } from "../themeColors";

describe("tokenColor", () => {
  it("writes a token's triplet as a color with commas, at an opacity", () => {
    expect(tokenColor("330 65% 50%")).toBe("hsla(330, 65%, 50%, 1)");
    expect(tokenColor(" 0 72% 51% ", 0.2)).toBe("hsla(0, 72%, 51%, 0.2)");
  });

  it("gives a value that is no triplet as it is", () => {
    expect(tokenColor("#dc2626", 0.5)).toBe("#dc2626");
  });
});

describe("readTokens", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads the tokens the page defines, an empty value for those it does not", () => {
    vi.stubGlobal("document", { documentElement: {} });
    vi.stubGlobal("getComputedStyle", () => ({
      getPropertyValue: (name: string) => (name === "--primary" ? " 330 65% 50% " : ""),
    }));

    expect(readTokens(["--primary", "--nowhere"])).toEqual(["330 65% 50%", ""]);
  });

  it("reads none outside a page", () => {
    expect(readTokens(["--primary"])).toEqual([""]);
  });
});
