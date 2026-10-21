/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/svelte";
import { flushSync, type Component } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import PointCloudWidget from "../point-cloud/PointCloudWidget.svelte";
import { PointCloudExtension } from "$lib/extensions/builtin/PointCloudExtension.js";
import type { WidgetComponentProps, WidgetExtensionConfig } from "$lib/extensions/types.js";
import { WidgetExtension } from "$lib/extensions/WidgetExtension.js";
import { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import { makeLayoutRepository } from "$lib/workspace/__tests__/fakeDatasetLayoutRepository.js";
import { DATASET_ID, makeBackend, VIEWPORT } from "$lib/workspace/__tests__/workspaceHarness.js";
import { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

// The point-cloud widget around its 3D canvas. The canvas needs WebGL, which
// the test DOM has not, so Threlte's canvas renders nothing; the toolbar and
// the widget's lifecycle are the real ones, over the real manager.
vi.mock("@threlte/core", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  Canvas: () => {},
}));

afterEach(() => cleanup());

const REC = "rec-1";

const DISCARD_TITLE = "Discard unsaved changes and restore this record's saved annotations";

/** Claims the fake dataset's one view, so the record opens; draws nothing. */
const VIEW_CLAIMER: WidgetExtensionConfig = {
  name: "view-claimer",
  label: "View",
  icon: "image",
  priority: 0,
  defaultLayout: { x: 0, y: 0, w: 3, h: 3 },
  component: (() => null) as unknown as Component<WidgetComponentProps>,
  addRecordSeed: ({ viewName }) =>
    Promise.resolve({
      title: viewName,
      options: {},
      data: {},
      view: { id: viewName, logicalName: viewName, width: 1, height: 1 },
    }),
};

/** An open record, with a point-cloud widget added to it and rendered. */
async function renderWidget() {
  const registry = new WidgetRegistry();
  registry.register(WidgetExtension.create(VIEW_CLAIMER));
  registry.register(PointCloudExtension);
  const { gateway } = makeBackend({ [REC]: {} });
  const manager = new WorkspaceManager(registry, gateway, makeLayoutRepository());
  await manager.openRecord(DATASET_ID, REC, VIEWPORT);
  const widget = manager.addWidget(PointCloudExtension.config.name);
  if (!widget) throw new Error("no point-cloud widget");
  const { unmount } = render(PointCloudWidget, {
    props: { widgetId: widget.id, options: {}, data: {} },
    context: new Map([["workspaceManager", manager]]),
  });
  return { manager, widgetId: widget.id, unmount };
}

describe("PointCloudWidget", () => {
  it("counts the record's unsaved work per annotation, as the image toolbar does", async () => {
    const { manager } = await renderWidget();

    // A new box: its entity and itself, two writes for one annotation.
    for (const resource of ["entities", "bbox3ds"]) {
      manager.queueMutation({
        op: "create",
        resource,
        body: {},
        widgetId: "another-widget",
        localAnnotationId: "box-1",
      });
    }
    flushSync();

    const toolbar = screen.getByRole("toolbar", { name: "Point cloud tools" });
    expect(within(toolbar).getByText("1 unsaved")).toBeTruthy();
  });

  it("lets go of an edit its tools held staged once it closes", async () => {
    const { manager, widgetId, unmount } = await renderWidget();
    // What a tool of the widget raises while it holds work not confirmed yet.
    manager.claimStagedWork(widgetId, () => {}).set(true);
    expect(await manager.flushSave()).toBe(false);

    unmount();

    // The record is all saved again: nothing can confirm that edit any more.
    expect(await manager.flushSave()).toBe(true);
  });

  it("counts an edit its tools hold staged, nothing queued, offers Discard for it, and Discard drops it", async () => {
    const { manager, widgetId } = await renderWidget();
    const discard = within(screen.getByRole("toolbar", { name: "Point cloud tools" })).getByTitle(
      DISCARD_TITLE,
    );
    expect(discard).toHaveProperty("disabled", true);
    let dropped = 0;
    const held = manager.claimStagedWork(widgetId, () => {
      dropped += 1;
      held.set(false);
    });

    held.set(true);
    flushSync();
    expect(manager.pendingCount).toBe(0);
    // Unsaved: the toolbar says so.
    expect(
      within(screen.getByRole("toolbar", { name: "Point cloud tools" })).getByText("1 unsaved"),
    ).toBeTruthy();
    expect(discard).toHaveProperty("disabled", false);
    await fireEvent.click(discard);

    await waitFor(() => expect(discard).toHaveProperty("disabled", true));
    expect(dropped).toBe(1);
  });
});
