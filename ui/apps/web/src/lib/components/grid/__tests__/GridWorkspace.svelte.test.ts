/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, render } from "@testing-library/svelte";
import { flushSync, tick } from "svelte";
import { afterEach, describe, expect, it } from "vitest";

import GridWorkspace from "../GridWorkspace.svelte";
import type { WidgetExtensionConfig } from "$lib/extensions/types.js";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import type { DatasetGateway } from "$lib/workspace/datasetGateway.js";
import { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

// Exercises the GridWorkspace $effect glue (hide → compact, show → free spot)
// against a real reactive WorkspaceManager and a real headless GridStack. A stub
// config has no `component`, so WidgetFrame renders only the frame (no widget).

const stubConfig = {
  name: "stub",
  label: "Stub",
  icon: "square",
  defaultLayout: { x: 0, y: 0, w: 6, h: 6, minW: 1, minH: 1 },
  component: undefined,
} as unknown as WidgetExtensionConfig;

const registry = {
  get: () => stubConfig,
  getAll: () => [stubConfig],
} as unknown as WidgetRegistry;

function mountedIds(container: HTMLElement): string[] {
  return [...container.querySelectorAll<HTMLElement>("[data-widget-id]")]
    .map((el) => el.dataset.widgetId!)
    .sort();
}

afterEach(() => cleanup());

describe("GridWorkspace — hide/show reflow", () => {
  it("compacts the remaining widget on hide and repositions on show", async () => {
    const manager = new WorkspaceManager(registry, {} as DatasetGateway);
    // Two full-width widgets stacked vertically: top (y=0) and bottom (y=6).
    const top = manager.addWidget("stub", { layout: { x: 0, y: 0, w: 6, h: 6 } })!;
    const bottom = manager.addWidget("stub", { layout: { x: 0, y: 6, w: 6, h: 6 } })!;
    const layoutOf = (id: string) => manager.widgets.find((w) => w.id === id)!.layout;

    const { container } = render(GridWorkspace, { props: { manager, registry } });
    await tick();
    expect(mountedIds(container)).toEqual([top.id, bottom.id].sort());

    // Hide the top widget → the bottom one fills the gap (compacts to y=0),
    // without resizing, and the new position is persisted to the manager.
    manager.toggleWidgetVisibility(top.id);
    flushSync();
    await tick();
    expect(mountedIds(container)).toEqual([bottom.id]);
    expect(layoutOf(bottom.id)).toMatchObject({ y: 0, h: 6 });

    // Show the top widget again → the effect re-mounts it. (The exact free-spot
    // placement is unit-tested against a real grid in gridReflow.test.ts; here we
    // only verify the show path re-adds the widget through the component.)
    manager.toggleWidgetVisibility(top.id);
    flushSync();
    await tick();
    expect(mountedIds(container)).toEqual([top.id, bottom.id].sort());
  });

  it("does not compact when a widget is removed (not hidden)", async () => {
    const manager = new WorkspaceManager(registry, {} as DatasetGateway);
    const top = manager.addWidget("stub", { layout: { x: 0, y: 0, w: 6, h: 6 } })!;
    const bottom = manager.addWidget("stub", { layout: { x: 0, y: 6, w: 6, h: 6 } })!;
    const layoutOf = (id: string) => manager.widgets.find((w) => w.id === id)!.layout;

    const { container } = render(GridWorkspace, { props: { manager, registry } });
    await tick();

    // Remove (not hide) the top widget → the bottom one must stay put; a removal
    // is a record-switch/delete, not a hide, so no reflow.
    manager.removeWidget(top.id);
    flushSync();
    await tick();
    expect(mountedIds(container)).toEqual([bottom.id]);
    expect(layoutOf(bottom.id).y).toBe(6);
  });
});
