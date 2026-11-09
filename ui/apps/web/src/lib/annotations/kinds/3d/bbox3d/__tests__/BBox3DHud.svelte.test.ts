/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { flushSync } from "svelte";
import { afterEach, describe, expect, it } from "vitest";

import BBox3DHud from "../BBox3DHud.svelte";
import { BBOX3D_RESOURCE } from "../bbox3dPayloadBuilder.js";
import { BBox3DSession, type PendingConfirm } from "../bbox3dSession.svelte.js";
import { realBoxEditor } from "./realBoxEditor.svelte.js";
import type { LocalBBox3DAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
import { REVIEW_STATUS } from "$lib/annotations/reviewStatus.js";
import type { EntityRow } from "$lib/api/annotations.js";
import { ENTITY_RESOURCE } from "$lib/api/resourceNames.js";
import {
  deferred,
  humanBox,
  modelBox,
  openManager,
  widgetSeam,
  type FakeBackend,
  type Row,
} from "$lib/workspace/__tests__/workspaceHarness.js";
import type { NextRecordToReview } from "$lib/workspace/reviewGateway.js";

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

/** The real box editors a test started, stopped after it. */
const editorTeardowns: (() => void)[] = [];

afterEach(() => {
  cleanup();
  for (const teardown of editorTeardowns.splice(0)) teardown();
  document.body.innerHTML = "";
});

/**
 * The HUD of the box `editingId`, or of a box not drawn yet.
 *
 * @param next What the server answers when "Save & next" asks for the next record.
 */
async function openHud(
  editingId?: string,
  next: NextRecordToReview | Promise<NextRecordToReview> = { recordId: null, remaining: 0 },
) {
  const { manager, backend } = await openManager(
    {
      [REC]: {
        [BBOX3D_RESOURCE]: [as3D(modelBox(REC, "m1")), as3D(humanBox(REC, "h1"))],
      },
    },
    { next },
  );
  const session = new BBox3DSession(widgetSeam(manager, "point-cloud-widget"));
  session.setResetEditor(() => {});
  render(BBox3DHud, { props: { session } });
  session.reportReady(COORDS, IDENTITY, editingId);
  flushSync();
  return { manager, backend, session };
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
    expect(deleteButton().disabled).toBe(false);

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

  it("rejects nothing while Save & next runs, says why, and stays open", async () => {
    const lookup = deferred<NextRecordToReview>();
    const { manager, backend, session } = await openHud("m1", lookup.promise);

    const moving = manager.review.saveAndNext();
    await waitFor(() => expect(backend.log).toContain("nextRecordToReview"));
    flushSync();
    expect(deleteButton().title).toBe("Not while Save & next is running");
    expect(deleteButton().disabled).toBe(true);
    await fireEvent.click(deleteButton());

    expect(session.confirm?.editingId).toBe("m1");
    expect(manager.annotations.find("m1")?.review?.status).toBe(REVIEW_STATUS.PENDING);
    expect(manager.pendingCount).toBe(0);
    lookup.resolve({ recordId: null, remaining: 0 });
    await moving;
    flushSync();

    expect(deleteButton().disabled).toBe(false);
  });
});

describe("BBox3DHud, a box changed under the HUD", () => {
  // A HUD reopened on a box whose move is queued holds no work of its own: it
  // shows the box as the record holds it. When that box is put back under it —
  // Discard — or taken away — a Reject — it must not go on showing, nor saving
  // again, the move the record no longer has. A HUD holding a move of its own
  // closes too when its box is taken away: the move has no box left. But the
  // box a save reads back, rounded to the float32 the dataset stores, is not a
  // change, and a gizmo drag under way is never dropped under the pointer by a
  // change of its box — only by Discard, which drops all work under way.

  /** A move float32 holds exactly: the box reads back as it was saved. */
  const ONE_UNIT = 1;
  /** A move float32 cannot hold: a box moved to x = 1.1 reads back at 1.100000023841858. */
  const A_TENTH = 0.1;
  /**
   * A box drawn away from m1, where float32 holds none of its centre's numbers:
   * it reads back at x = 40.099998474121094.
   */
  const DRAWN: PendingConfirm["coords"] = [40.1, 2.2, 3.3, 4, 5, 6];
  /** Where another reviewer leaves the box meanwhile: away from where this HUD moved it. */
  const MOVED_BY_ANOTHER: PendingConfirm["coords"] = [7, 2, 3, 4, 5, 6];

  /**
   * The HUD over the real box editor.
   *
   * @param box The box the record holds: the model's box m1 at `COORDS` unless told otherwise.
   */
  async function openWithEditor(box: Row = as3D(modelBox(REC, "m1"))) {
    const { manager, backend } = await openManager({
      [REC]: { [BBOX3D_RESOURCE]: [box] },
    });
    const seam = widgetSeam(manager, "point-cloud-widget");
    const session = new BBox3DSession(seam);
    const editor = realBoxEditor(session, seam.collection);
    editorTeardowns.push(editor.teardown);
    render(BBox3DHud, { props: { session } });
    return { manager, backend, session, editor };
  }

  type Scene = Awaited<ReturnType<typeof openWithEditor>>;

  /** What the editor stages once the box it opened is moved `distance` along X. */
  function movedAlongX(opened: PendingConfirm, distance: number): PendingConfirm {
    const coords = [...opened.coords] as PendingConfirm["coords"];
    coords[0] += distance;
    return { ...opened, coords };
  }

  /**
   * Move a box in the HUD and save it there, then open it again: its move is queued.
   *
   * @returns What the HUD saved.
   */
  function moveSaveAndReopen(scene: Scene, id = "m1", distance = ONE_UNIT): PendingConfirm {
    const moved = movedAlongX(scene.editor.open(id), distance);
    scene.session.reportReady(moved.coords, moved.rotation, id);
    scene.session.save();
    scene.editor.open(id);
    flushSync();
    return moved;
  }

  /**
   * Store the record's 3D boxes as the dataset does: their coordinates and
   * rotation in float32 columns (LanceDB `Vector(6)` and `Vector(9)`), so a box
   * reads back rounded. The rest — and the entity a new box names — is stored
   * as sent, which is what the server does with a person's box.
   */
  function storeAsFloat32(backend: FakeBackend): void {
    const toFloat32 = (values: unknown) => (values as number[]).map(Math.fround);
    const rows = backend.records[REC][BBOX3D_RESOURCE];
    backend.onWrite = (write) => {
      if (write.op === "create" && write.resource === ENTITY_RESOURCE) {
        backend.entities.push({ ...(write.body as EntityRow) });
      }
      if (write.op === "delete" || write.resource !== BBOX3D_RESOURCE) return;
      const { coords, rotation, ...rest } = write.body;
      const stored: Record<string, unknown> = {
        ...rest,
        coords: toFloat32(coords),
        rotation: toFloat32(rotation),
      };
      const row = rows.find((r) => r.id === (write.op === "create" ? write.body.id : write.id));
      if (row) Object.assign(row, stored);
      else if (write.op === "create") rows.push(stored as Row);
    };
  }

  const xOf = (scene: Scene, id: string) =>
    (scene.manager.annotations.find(id) as LocalBBox3DAnnotation | undefined)?.geometry.coords[0];

  const hudShown = () => screen.queryByText("Apply this 3D box?") !== null;

  it("closes when Discard puts the box back, and its Apply then writes nothing", async () => {
    const scene = await openWithEditor();
    moveSaveAndReopen(scene);
    expect(hudShown()).toBe(true);
    expect(scene.manager.unsavedCount).toBe(1);

    await scene.manager.discardChanges();
    flushSync();

    expect(scene.session.confirm).toBeNull();
    expect(hudShown()).toBe(false);
    expect(scene.editor.editor.drawPhase).toBe("idle");
    scene.session.save();
    expect(scene.manager.pendingCount).toBe(0);
    expect(scene.manager.annotations.find("m1")?.review?.status).toBe(REVIEW_STATUS.PENDING);
  });

  it("closes when a Reject deletes the box, and the delete stands", async () => {
    const scene = await openWithEditor();
    moveSaveAndReopen(scene);

    expect(scene.manager.review.reject("m1")).toBe(true);
    flushSync();

    expect(scene.session.confirm).toBeNull();
    scene.session.save();
    // The move queued for the box went with it: its delete is all that is left.
    expect(scene.manager.pendingMutations.map((m) => (m.op === "update" ? m.body : m.op))).toEqual([
      "delete",
    ]);
  });

  it("closes when a Reject from the Review tab deletes a box whose move it holds", async () => {
    const scene = await openWithEditor();
    const moved = movedAlongX(scene.editor.open("m1"), ONE_UNIT);
    scene.session.reportReady(moved.coords, moved.rotation, "m1");
    flushSync();
    expect(scene.manager.unsavedCount).toBe(1);

    expect(scene.manager.review.reject("m1")).toBe(true);
    flushSync();

    expect(scene.session.confirm).toBeNull();
    expect(hudShown()).toBe(false);
    expect(scene.editor.editor.drawPhase).toBe("idle");
    // The move went with its box: the delete is the one unsaved item left, and
    // no flag keeps "Save & next" on the record once it is saved.
    expect(scene.manager.pendingMutations.map((m) => m.op)).toEqual(["delete"]);
    expect(scene.manager.unsavedCount).toBe(1);
    await scene.manager.flushSave();
    expect(scene.manager.hasUnsavedWork).toBe(false);
  });

  it("stays open on a box a click only opened, through a Discard that leaves it as it is", async () => {
    const scene = await openWithEditor();
    scene.editor.open("m1");
    // Something to discard elsewhere on the record.
    scene.manager.review.accept("m1");

    await scene.manager.discardChanges();
    flushSync();

    expect(scene.session.confirm?.editingId).toBe("m1");
    expect(hudShown()).toBe(true);
  });

  it("keeps a move the HUD holds through a save's read-back", async () => {
    const scene = await openWithEditor();
    const moved = movedAlongX(scene.editor.open("m1"), ONE_UNIT);
    scene.session.reportReady(moved.coords, moved.rotation, "m1");
    // Something for the save to send, so that it reads the record back.
    scene.manager.review.accept("m1");

    await scene.manager.flushSave();
    flushSync();

    expect(scene.session.confirm?.coords).toEqual(moved.coords);
    expect(scene.manager.hasUnsavedWork).toBe(true);
  });

  it("stays open when a save reads back the box it shows, rounded as the dataset stores it", async () => {
    const scene = await openWithEditor(as3D(humanBox(REC, "h1")));
    storeAsFloat32(scene.backend);
    const moved = moveSaveAndReopen(scene, "h1", A_TENTH);

    await scene.manager.flushSave();
    flushSync();

    // The box read back is the one saved, float32's rounding away from it.
    expect(xOf(scene, "h1")).toBe(Math.fround(moved.coords[0]));
    expect(xOf(scene, "h1")).not.toBe(moved.coords[0]);
    expect(scene.session.confirm?.editingId).toBe("h1");
    expect(hudShown()).toBe(true);
    expect(scene.editor.editor.drawPhase).toBe("confirming");
    // It holds nothing of its own, and its Apply writes nothing.
    expect(scene.manager.hasUnsavedWork).toBe(false);
    scene.session.save();
    expect(scene.manager.pendingCount).toBe(0);
  });

  it("stays open on a box drawn, created and opened again, when a save reads it back rounded", async () => {
    const scene = await openWithEditor();
    storeAsFloat32(scene.backend);
    scene.session.reportReady([...DRAWN], [...IDENTITY]);
    scene.session.save();
    scene.manager.confirmPendingAnnotation({ mode: "new", entityFields: { category: "car" } });
    const drawnId = scene.manager.annotations.byKind("bbox3d").find((box) => box.id !== "m1")!.id;
    scene.editor.open(drawnId);
    flushSync();

    await scene.manager.flushSave();
    flushSync();

    expect(xOf(scene, drawnId)).toBe(Math.fround(DRAWN[0]));
    expect(xOf(scene, drawnId)).not.toBe(DRAWN[0]);
    expect(scene.session.confirm?.editingId).toBe(drawnId);
    expect(hudShown()).toBe(true);
    expect(scene.manager.hasUnsavedWork).toBe(false);
  });

  it("lets a ring drag under way end when a save reads its box back rounded", async () => {
    const scene = await openWithEditor(as3D(humanBox(REC, "h1")));
    storeAsFloat32(scene.backend);
    moveSaveAndReopen(scene, "h1", A_TENTH);
    const ring = scene.editor.grabRing();

    await scene.manager.flushSave();
    flushSync();

    expect(xOf(scene, "h1")).toBe(Math.fround(COORDS[0] + A_TENTH));
    expect(scene.session.confirm?.editingId).toBe("h1");
    expect(scene.editor.editor.drawPhase).toBe("rotating");
    ring.release();
    flushSync();
    expect(scene.editor.editor.drawPhase).toBe("confirming");
    expect(scene.session.confirm?.editingId).toBe("h1");
    // Pressed and let go where it was, the ring turned nothing: the box is the record's.
    expect(scene.manager.hasUnsavedWork).toBe(false);
  });

  it("lets a ring drag under way end when a save reads its box back as another hand moved it", async () => {
    const scene = await openWithEditor(as3D(humanBox(REC, "h1")));
    moveSaveAndReopen(scene, "h1");
    // The server stores this HUD's move; another reviewer's lands right after.
    const row = scene.backend.records[REC][BBOX3D_RESOURCE].find((r) => r.id === "h1")!;
    scene.backend.onWrite = (write) => {
      if (write.op === "update") Object.assign(row, write.body, { coords: [...MOVED_BY_ANOTHER] });
    };
    const ring = scene.editor.grabRing();

    await scene.manager.flushSave();
    flushSync();

    // The box changed under the HUD, which would drop the drag under the pointer if it closed.
    expect(xOf(scene, "h1")).toBe(MOVED_BY_ANOTHER[0]);
    expect(scene.session.confirm?.editingId).toBe("h1");
    expect(scene.editor.editor.drawPhase).toBe("rotating");
    ring.release();
    flushSync();

    // Judged once let go: the box the drag left is not the one the record now
    // holds, so it is the HUD's own work — unsaved, and Discard drops it.
    expect(scene.editor.editor.drawPhase).toBe("confirming");
    expect(scene.session.confirm?.editingId).toBe("h1");
    expect(scene.manager.hasUnsavedWork).toBe(true);
    await scene.manager.discardChanges();
    flushSync();
    expect(scene.session.confirm).toBeNull();
    expect(scene.manager.hasUnsavedWork).toBe(false);
  });

  it("drops a ring drag under way when Discard puts the box back: let go, it stages nothing", async () => {
    const scene = await openWithEditor();
    moveSaveAndReopen(scene);
    const ring = scene.editor.grabRing();
    ring.turn();
    // The move queued, and the drag under way.
    expect(scene.manager.unsavedCount).toBe(2);

    await scene.manager.discardChanges();
    flushSync();

    // The drag is work under way, which Discard drops, HUD and all.
    expect(scene.session.confirm).toBeNull();
    expect(hudShown()).toBe(false);
    expect(scene.editor.editor.drawPhase).toBe("idle");
    ring.release();
    flushSync();
    expect(scene.session.confirm).toBeNull();
    expect(scene.manager.hasUnsavedWork).toBe(false);
    expect(xOf(scene, "m1")).toBe(COORDS[0]);
  });
});
