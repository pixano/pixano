/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { flushSync } from "svelte";
import { afterEach, describe, expect, it } from "vitest";

import BBox3DHud from "../BBox3DHud.svelte";
import { BBOX3D_RESOURCE } from "../bbox3dPayloadBuilder.js";
import { BBox3DSession } from "../bbox3dSession.svelte.js";
import {
  humanBox,
  modelBox,
  openManager,
  widgetSeam,
  type Row,
} from "$lib/workspace/__tests__/workspaceHarness.js";

// The HUD a 3D box opens, rendered over its real session and the real
// workspace: its delete button must say what it does to the box it holds —
// Reject a model's box, which deletes it, Delete a person's.

const REC = "rec-1";
const COORDS: [number, number, number, number, number, number] = [1, 2, 3, 4, 5, 6];
const IDENTITY: [number, number, number, number, number, number, number, number, number] = [
  1, 0, 0, 0, 1, 0, 0, 0, 1,
];

/** A 3D box as the dataset holds it, on top of a 2D row's provenance and status. */
function as3D(row: Row): Row {
  return { ...row, view_id: "", coords: [...COORDS], format: "xyzwhd", rotation: [...IDENTITY] };
}

afterEach(() => cleanup());

/** The HUD of the box `editingId`, or of a box not drawn yet. */
async function openHud(editingId?: string) {
  const { manager } = await openManager({
    [REC]: {
      [BBOX3D_RESOURCE]: [as3D(modelBox(REC, "m1")), as3D(humanBox(REC, "h1"))],
    },
  });
  const session = new BBox3DSession(widgetSeam(manager, "point-cloud-widget"));
  session.setResetEditor(() => {});
  render(BBox3DHud, { props: { session } });
  session.reportReady(COORDS, IDENTITY, editingId);
  flushSync();
  return { manager, session };
}

/** The HUD's delete button, whichever word it shows. */
const deleteButton = () =>
  screen.getByRole<HTMLButtonElement>("button", { name: /^(Reject|Delete)$/ });

describe("BBox3DHud", () => {
  it("offers to reject a model's box, says rejecting deletes it, and deletes it", async () => {
    const { manager } = await openHud("m1");

    expect(deleteButton().textContent?.trim()).toBe("Reject");
    expect(deleteButton().title).toBe(
      "Reject this 3D box: a model proposed it; rejecting deletes it",
    );

    await fireEvent.click(deleteButton());

    expect(manager.annotations.find("m1")).toBeUndefined();
    expect(manager.pendingMutations.map((m) => m.op)).toEqual(["delete"]);
  });

  it("offers to delete a person's box, and deletes it", async () => {
    const { manager } = await openHud("h1");

    expect(deleteButton().textContent?.trim()).toBe("Delete");
    expect(deleteButton().title).toBe("Delete this 3D box");

    await fireEvent.click(deleteButton());

    expect(manager.annotations.find("h1")).toBeUndefined();
    expect(manager.pendingMutations.map((m) => m.op)).toEqual(["delete"]);
  });

  it("offers no delete for a box not drawn yet", async () => {
    await openHud();

    expect(screen.queryByRole("button", { name: /^(Reject|Delete)$/ })).toBeNull();
  });
});
