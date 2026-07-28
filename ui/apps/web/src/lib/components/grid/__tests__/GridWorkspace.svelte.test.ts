/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, render } from "@testing-library/svelte";
import { flushSync, tick } from "svelte";
import { afterEach, describe, expect, it } from "vitest";

import GridWorkspace from "../GridWorkspace.svelte";
import StubReactiveWidget from "./StubReactiveWidget.svelte";
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

  it("keeps earlier-mounted widgets reactive after the mount effect re-runs", async () => {
    // Guards the deferred-mount lifecycle (mount lands after a microtask, and
    // widgets keep reacting across reconciliation re-runs + cross-root
    // flushes). Context: mounting widget roots inside the reconciliation
    // $effect let a later re-run detach them (Svelte nulls their parent while
    // they stay reachable from this tree), after which a flush queueing both
    // the app root and a detached widget root froze the widget for good, with
    // no error thrown. That scheduler poisoning needs a tree topology jsdom
    // doesn't reproduce, so this test can't fail for it — the freeze itself
    // was verified fixed in the browser.
    const reactiveConfig = {
      ...stubConfig,
      component: StubReactiveWidget,
    } as WidgetExtensionConfig;
    const reactiveRegistry = {
      get: () => reactiveConfig,
      getAll: () => [reactiveConfig],
    } as unknown as WidgetRegistry;

    const manager = new WorkspaceManager(reactiveRegistry, {} as DatasetGateway);

    const { container } = render(GridWorkspace, {
      props: { manager, registry: reactiveRegistry },
    });
    await tick();

    // Widget added after initial render: mounted by the reconciliation
    // $effect. A further re-run of that effect is what used to detach it.
    manager.addWidget("stub", { layout: { x: 0, y: 0, w: 6, h: 6 } });
    flushSync();
    await tick();
    await Promise.resolve(); // let the deferred widget mount run
    await tick();
    expect(container.querySelectorAll("[data-testid='preset-name']")).toHaveLength(1);

    // Further batches: each add re-runs the $effect (used to detach the
    // previously mounted widget roots while they stayed reachable from this
    // tree).
    for (let i = 1; i <= 3; i++) {
      manager.addWidget("stub", { layout: { x: 0, y: 6 * i, w: 6, h: 6 } });
      flushSync();
      await tick();
      await Promise.resolve();
      await tick();
    }

    // One flush dirtying both the workspace tree (editMode) and the widget
    // roots (presetName) — the poisoning pattern — followed by a second write:
    // the widgets must still re-render it.
    manager.editMode = false;
    manager.presetName = "First";
    await tick();
    manager.presetName = "Second";
    await tick();

    const labels = [...container.querySelectorAll("[data-testid='preset-name']")];
    expect(labels).toHaveLength(4);
    for (const label of labels) {
      expect(label.textContent).toBe("Second");
    }
  });

  it("cancels a deferred mount when the widget is removed before it runs", async () => {
    // Removal in the same synchronous batch as the add: the widget's Svelte
    // component must never mount, and the placeholder element (not yet
    // registered with GridStack at that point) must be removed from the DOM.
    const reactiveConfig = {
      ...stubConfig,
      component: StubReactiveWidget,
    } as WidgetExtensionConfig;
    const reactiveRegistry = {
      get: () => reactiveConfig,
      getAll: () => [reactiveConfig],
    } as unknown as WidgetRegistry;

    const manager = new WorkspaceManager(reactiveRegistry, {} as DatasetGateway);
    const { container } = render(GridWorkspace, {
      props: { manager, registry: reactiveRegistry },
    });
    await tick();

    const widget = manager.addWidget("stub", { layout: { x: 0, y: 0, w: 6, h: 6 } })!;
    flushSync(); // reconciliation effect appends the element and defers the mount
    manager.removeWidget(widget.id);
    flushSync(); // unmount runs before the deferred mount's microtask

    await tick();
    await Promise.resolve();
    await tick();

    expect(container.querySelectorAll("[data-widget-id]")).toHaveLength(0);
    expect(container.querySelectorAll("[data-testid='preset-name']")).toHaveLength(0);
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
