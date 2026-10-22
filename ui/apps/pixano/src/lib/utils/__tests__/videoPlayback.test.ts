/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { homeShortcutIsTaken, resolveNextPlaybackFrame } from "$lib/utils/videoPlayback";

describe("resolveNextPlaybackFrame", () => {
  it("advances by one frame before the end", () => {
    expect(resolveNextPlaybackFrame(3, 10, false)).toEqual({ action: "seek", frame: 4 });
    expect(resolveNextPlaybackFrame(9, 10, true)).toEqual({ action: "seek", frame: 10 });
  });

  it("stops on the last frame when not looping", () => {
    expect(resolveNextPlaybackFrame(10, 10, false)).toEqual({ action: "stop" });
  });

  it("wraps to frame 0 as a step of its own when looping", () => {
    expect(resolveNextPlaybackFrame(10, 10, true)).toEqual({ action: "seek", frame: 0 });
    // A two-frame clip then shows frame 0 for a full interval before frame 1.
    expect(resolveNextPlaybackFrame(0, 1, true)).toEqual({ action: "seek", frame: 1 });
  });
});

describe("homeShortcutIsTaken", () => {
  const element = (role: string | null) => ({
    closest: (selector: string) => (role && selector.includes(role) ? {} : null),
  });

  it("yields to a handler that already consumed the key", () => {
    expect(homeShortcutIsTaken({ defaultPrevented: true, target: null })).toBe(true);
  });

  it("yields to a slider thumb", () => {
    expect(
      homeShortcutIsTaken({ defaultPrevented: false, target: element("slider") as never }),
    ).toBe(true);
  });

  it("handles Home elsewhere", () => {
    expect(homeShortcutIsTaken({ defaultPrevented: false, target: element(null) as never })).toBe(
      false,
    );
    expect(homeShortcutIsTaken({ defaultPrevented: false, target: null })).toBe(false);
  });
});
