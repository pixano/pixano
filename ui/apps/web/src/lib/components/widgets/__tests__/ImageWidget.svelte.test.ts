/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, render, screen, within } from "@testing-library/svelte";
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
// is checked is what the person sees and presses: the entity button's words,
// and where a key typed in a form goes.
vi.mock("konva", async () => ({
  default: (await vi.importActual<{ default: unknown }>("konva/lib/index.js")).default,
}));

installSilentCanvas();

const REC = "rec-1";

const ENTITIES = [entityOf(REC, "ent-h1", { category: "tree" })];

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
  render(ImageWidget, {
    props: { widgetId: widget.id, options: widget.options, data: {} },
    context: new Map([["workspaceManager", opened.manager]]),
  });
  render(RightPanel, { props: { manager: opened.manager } });
  return opened;
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
