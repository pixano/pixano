/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  markInterpolatedEditing,
  toggleInterpolatedEditingId,
  withoutInterpolatedEditingId,
} from "$lib/stores/interpolatedEditing";

describe("interpolatedEditing", () => {
  it("anchors one ghost at a time", () => {
    const one = toggleInterpolatedEditingId(new Set(), "a::1");
    expect([...one]).toEqual(["a::1"]);

    const other = toggleInterpolatedEditingId(one, "b::2");
    expect([...other]).toEqual(["b::2"]);

    expect(toggleInterpolatedEditingId(other, "b::2").size).toBe(0);
  });

  it("removes an id without touching the set when it is absent", () => {
    const ids = new Set(["a::1"]);

    expect(withoutInterpolatedEditingId(ids, "zz")).toBe(ids);

    const without = withoutInterpolatedEditingId(ids, "a::1");
    expect(without.has("a::1")).toBe(false);
    expect(ids.has("a::1")).toBe(true);
  });

  it("marks only ghosts whose id is being edited", () => {
    const ghost = { id: "a::1", ui: { startRef: {}, displayControl: { editing: false } } };
    const stored = { id: "a::1", ui: { displayControl: { editing: false } } };
    const other = { id: "b::1", ui: { startRef: {}, displayControl: { editing: false } } };

    const results = markInterpolatedEditing([ghost, stored, other], new Set(["a::1"]));

    expect(results).toEqual([ghost, stored, other]);
    expect(ghost.ui.displayControl.editing).toBe(true);
    expect(stored.ui.displayControl.editing).toBe(false);
    expect(other.ui.displayControl.editing).toBe(false);
  });

  it("leaves results untouched when nothing is being edited", () => {
    const ghost = { id: "a::1", ui: { startRef: {}, displayControl: { editing: false } } };

    markInterpolatedEditing([ghost], new Set());

    expect(ghost.ui.displayControl.editing).toBe(false);
  });
});
