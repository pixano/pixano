/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { flushSync } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import RightPanel from "../../shell/RightPanel.svelte";
import ImageWidget from "../image/ImageWidget.svelte";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { installSilentCanvas } from "$lib/annotations/scene/__tests__/konvaInHappyDom.js";
import { entityOf, humanBox, openManager } from "$lib/workspace/__tests__/workspaceHarness.js";
import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

// The image widget as a person meets it: rendered on the real Konva, next to
// the right panel, over the real manager and queue — only HTTP is faked. What
// is checked is what the person sees and presses: the toolbar's count and
// Discard, the entity button's words, what the trash button lets go of, and
// where a key typed in a form goes.
vi.mock("konva", async () => ({
  default: (await vi.importActual<{ default: unknown }>("konva/lib/index.js")).default,
}));

installSilentCanvas();

const REC = "rec-1";

const ENTITIES = [entityOf(REC, "ent-h1", { category: "tree" })];

const DISCARD_TITLE = "Discard unsaved changes and restore this record's saved annotations";
const DELETE_TITLE = "Delete selected (Del)";
const REASSIGN_TITLE = "Change the entity this annotation belongs to (E)";
const REASSIGN_NOTHING_SELECTED_TITLE = "Select an annotation to change its entity";

afterEach(() => cleanup());

/** A record with a person's box, shown in an image widget beside the right panel. */
async function openImageWidget() {
  const opened = await openManager(
    { [REC]: { [BBOX_RESOURCE]: [humanBox(REC, "h1")] } },
    { entities: ENTITIES },
  );
  const widget = opened.manager.widgets[0];
  const { unmount } = render(ImageWidget, {
    props: { widgetId: widget.id, options: widget.options, data: {} },
    context: new Map([["workspaceManager", opened.manager]]),
  });
  render(RightPanel, { props: { manager: opened.manager } });
  return { ...opened, widgetId: widget.id, unmount };
}

function toolbar(): HTMLElement {
  return screen.getByRole("toolbar", { name: "Image annotation tools" });
}

/** What assistive tech reads after a button's name: the text its `aria-describedby` points at. */
function descriptionOf(element: HTMLElement): string | null {
  const id = element.getAttribute("aria-describedby");
  return id ? (document.getElementById(id)?.textContent ?? null) : null;
}

function select(manager: WorkspaceManager, id: string): void {
  manager.annotations.select(id);
  flushSync();
}

describe("ImageWidget toolbar", () => {
  it("names the entity button by what it does, and says what it waits for", async () => {
    const { manager } = await openImageWidget();
    const reassign = () =>
      within(toolbar()).getByRole<HTMLButtonElement>("button", { name: REASSIGN_TITLE });

    expect(reassign().disabled).toBe(true);
    expect(reassign().title).toBe(REASSIGN_NOTHING_SELECTED_TITLE);
    expect(descriptionOf(reassign())).toBe(REASSIGN_NOTHING_SELECTED_TITLE);

    select(manager, "h1");
    expect(reassign().disabled).toBe(false);
    expect(reassign().title).toBe(REASSIGN_TITLE);
    expect(descriptionOf(reassign())).toBeNull();
  });

  it("lets go of a resize or a drag under way before it deletes, as the Delete key does", async () => {
    const { manager, widgetId } = await openImageWidget();
    // What an editor of this widget raises while a box is resized or dragged.
    let dropped = 0;
    const gesture = manager.claimStagedWork(widgetId, () => {
      dropped += 1;
      gesture.set(false);
    });
    gesture.set(true);
    select(manager, "h1");

    await fireEvent.click(within(toolbar()).getByTitle(DELETE_TITLE));

    expect(dropped).toBe(1);
    expect(manager.annotations.find("h1")).toBeUndefined();
    expect(manager.unsavedCount).toBe(1);
  });

  it("leaves alone the points a draw tool holds: they are no gesture on the selection", async () => {
    const { manager, widgetId } = await openImageWidget();
    await fireEvent.click(within(toolbar()).getByTitle("Draw polygon (P)"));
    // What the polygon tool raises once a point is placed.
    let dropped = 0;
    manager.claimStagedWork(widgetId, () => (dropped += 1)).set(true);
    select(manager, "h1");

    await fireEvent.click(within(toolbar()).getByTitle(DELETE_TITLE));

    expect(dropped).toBe(0);
    expect(manager.annotations.find("h1")).toBeUndefined();
    // The delete, and the points still held.
    expect(manager.unsavedCount).toBe(2);
  });

  it("counts work a tool holds with nothing queued, offers Discard for it, and Discard drops it", async () => {
    const { manager, widgetId } = await openImageWidget();
    const discard = within(toolbar()).getByTitle<HTMLButtonElement>(DISCARD_TITLE);
    let dropped = 0;
    // What a tool of this widget raises while a shape is begun and not committed.
    const shapeBegun = manager.claimStagedWork(widgetId, () => {
      dropped += 1;
      shapeBegun.set(false);
    });

    shapeBegun.set(true);
    flushSync();
    expect(manager.pendingCount).toBe(0);
    // Unsaved: the toolbar says so.
    expect(within(toolbar()).getByText("1 unsaved")).toBeTruthy();
    expect(discard.disabled).toBe(false);
    await fireEvent.click(discard);

    await waitFor(() => expect(discard.disabled).toBe(true));
    expect(within(toolbar()).queryByText(/unsaved/)).toBeNull();
    expect(dropped).toBe(1);
  });

  it("lets go of the work its tools held once it closes", async () => {
    const { manager, widgetId, unmount } = await openImageWidget();
    // A holder of this widget that does not lower its own flag as it closes.
    manager.claimStagedWork(widgetId, () => {}).set(true);
    expect(manager.hasUnsavedWork).toBe(true);

    unmount();

    // Nothing can confirm that work any more: the record is all saved again.
    expect(manager.hasUnsavedWork).toBe(false);
  });

  it("keeps another widget's flag raised meanwhile when it lets go of its own as it closes", async () => {
    const { manager, widgetId } = await openImageWidget();
    const otherWidget = manager.claimStagedWork("point-cloud-widget", () => {});
    // The widget's release from an effect's teardown, as when it closes.
    const closing = $effect.root(() => {
      $effect(() => () => manager.releaseStagedWork(widgetId));
    });
    flushSync();

    // Raised just before this widget lets go, in the same turn: a teardown
    // reads reactive state as it was before that write.
    otherWidget.set(true);
    closing();

    expect(manager.hasUnsavedWork).toBe(true);
  });
});

describe("ImageWidget keyboard", () => {
  /** A key pressed with focus on `target`, travelling up to the window as a real one does. */
  function press(target: HTMLElement, key: string): KeyboardEvent {
    target.focus();
    const event = new KeyboardEvent("keydown", { key, bubbles: true, cancelable: true });
    target.dispatchEvent(event);
    flushSync();
    return event;
  }

  it("leaves the keys typed in the reassignment's Entity select to the select", async () => {
    const { manager } = await openImageWidget();
    select(manager, "h1");
    // Outside any form field, E starts a reassignment, and the right panel
    // shows its Entities tab, where the entity is chosen.
    press(document.body, "e");
    const reassignment = manager.pendingAnnotation;
    expect(reassignment).not.toBeNull();
    const entitySelect = screen.getByRole("combobox");

    // A select picks an option with the keys typed in it; the select tool used
    // to take the "e" for another reassignment, and Backspace for a delete.
    const typeahead = press(entitySelect, "e");
    press(entitySelect, "Backspace");

    expect(typeahead.defaultPrevented).toBe(false);
    expect(manager.pendingAnnotation).toBe(reassignment);
    expect(manager.annotations.find("h1")?.entityId).toBe("ent-h1");
    expect(manager.pendingCount).toBe(0);
  });
});
