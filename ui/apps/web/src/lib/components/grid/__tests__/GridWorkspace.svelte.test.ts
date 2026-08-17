/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, render } from "@testing-library/svelte";
import { flushSync, tick } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import GridWorkspace from "../GridWorkspace.svelte";
import StubReactiveWidget from "./StubReactiveWidget.svelte";
import type { WidgetExtensionConfig } from "$lib/extensions/types.js";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import { DatasetInfo, type Dataset } from "$lib/types/dataset.js";
import { makeLayoutRepository } from "$lib/workspace/__tests__/fakeDatasetLayoutRepository.js";
import type { DatasetGateway } from "$lib/workspace/datasetGateway.js";
import { DATASET_LAYOUT_VERSION, type DatasetLayout } from "$lib/workspace/datasetLayout.js";
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

/**
 * Minimal record-loading setup so a test can drive the *real*
 * `restoreOpeningLayout` / `fitLayoutToViewport` instead of imitating what they
 * do to the manager. One dataset, two image views, one widget each.
 */
function makeRecordSetup(storedLayout?: DatasetLayout, viewCount = 2) {
  const views = Object.fromEntries(
    Array.from({ length: viewCount }, (_, i) => [`cam_${i + 1}`, { base: "Image" }]),
  );
  const info = new DatasetInfo({
    id: "ds-1",
    name: "Test Dataset",
    description: "",
    num_items: 1,
    size: "",
    preview: "",
    workspace: "image",
  });
  info.views = views;
  const dataset = { info, schema: { schemas: {} } } as unknown as Dataset;

  const gateway = {
    getDataset: () => Promise.resolve(dataset),
    listEntities: () => Promise.resolve([]),
    loadImageByLogicalName: (_d: string, _r: string, name: string) =>
      Promise.resolve({ id: `img-${name}`, src: "/i.png", width: 100, height: 50 }),
    loadPointCloudByLogicalName: () => Promise.resolve(null),
    listAnnotations: () => Promise.resolve([]),
    createEntity: () => Promise.resolve({}),
    deleteEntity: () => Promise.resolve(),
    createAnnotation: () => Promise.resolve({}),
    updateAnnotation: () => Promise.resolve({}),
    deleteAnnotation: () => Promise.resolve(),
  } as unknown as DatasetGateway;

  const seedingConfig = {
    ...stubConfig,
    // Mirrors the real image/point-cloud extensions, whose minimum is 3 cells.
    // A stub with minW/minH of 1 would never exercise GridStack clamping a
    // fitted cell back up, which is half of what these tests guard.
    defaultLayout: { x: 0, y: 0, w: 6, h: 6, minW: 3, minH: 3 },
    addRecordSeed: ({ viewName, viewDef }: { viewName: string; viewDef: { base: string } }) =>
      viewDef.base === "Image"
        ? Promise.resolve({ title: viewName, view: { logicalName: viewName } })
        : Promise.resolve(null),
  } as unknown as WidgetExtensionConfig;

  const seedingRegistry = {
    get: () => seedingConfig,
    getAll: () => [seedingConfig],
  } as unknown as WidgetRegistry;

  const layouts = makeLayoutRepository(storedLayout ? { "ds-1": storedLayout } : {});
  const manager = new WorkspaceManager(seedingRegistry, gateway, layouts);

  return { manager, registry: seedingRegistry, layouts };
}

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

  it("does not remember an arrangement the user never made", async () => {
    // Mounting writes each widget's resolved position back to the manager
    // (GridStack may clamp it). Persisting that would freeze an automatic
    // placement — computed for this record's widget count — as the dataset's
    // preferred arrangement, so only real gestures may reach the store.
    const manager = new WorkspaceManager(registry, {} as DatasetGateway);
    manager.addWidget("stub", { layout: { x: 0, y: 0, w: 6, h: 6 } });
    manager.addWidget("stub", { layout: { x: 0, y: 6, w: 6, h: 6 } });
    const save = vi.spyOn(manager, "saveDatasetLayout");

    render(GridWorkspace, { props: { manager, registry } });
    await tick();
    await Promise.resolve(); // let the deferred widget mounts run
    await tick();

    expect(save).not.toHaveBeenCalled();
  });

  it("remembers the arrangement only once the hide-driven compaction has landed", async () => {
    const manager = new WorkspaceManager(registry, {} as DatasetGateway);
    const top = manager.addWidget("stub", { layout: { x: 0, y: 0, w: 6, h: 6 } })!;
    const bottom = manager.addWidget("stub", { layout: { x: 0, y: 6, w: 6, h: 6 } })!;
    const layoutOf = (id: string) => manager.widgets.find((w) => w.id === id)!.layout;

    // What the manager would have stored at each save, so we can assert the
    // arrangement finally remembered is the one on screen — not the pre-compaction
    // snapshot taken when the visibility toggle itself saved.
    const persistedTops: Array<number | undefined> = [];
    const save = vi
      .spyOn(manager, "saveDatasetLayout")
      .mockImplementation(() => void persistedTops.push(layoutOf(bottom.id).y));

    render(GridWorkspace, { props: { manager, registry } });
    await tick();

    manager.toggleWidgetVisibility(top.id);
    flushSync();
    await tick();

    expect(save).toHaveBeenCalled();
    expect(persistedTops.at(-1)).toBe(0);
  });

  it("remembers a re-shown widget's settled spot, not its pre-hide one", async () => {
    // Regression: showing a widget used to persist the position it had before
    // being hidden — a slot compaction may since have given to a neighbour.
    // GridStack then re-placed it on screen without that landing in storage, so
    // the remembered arrangement disagreed with what the user saw.
    const manager = new WorkspaceManager(registry, {} as DatasetGateway);
    const top = manager.addWidget("stub", { layout: { x: 0, y: 0, w: 6, h: 6 } })!;
    manager.addWidget("stub", { layout: { x: 0, y: 6, w: 6, h: 6 } })!;
    const layoutOf = (id: string) => manager.widgets.find((w) => w.id === id)!.layout;

    // Snapshot what would have been written at each save, to compare the last
    // one against where the widget actually ends up.
    const persisted: Array<{ x: number; y: number }> = [];
    vi.spyOn(manager, "saveDatasetLayout").mockImplementation(() => {
      const { x, y } = layoutOf(top.id);
      persisted.push({ x, y });
    });

    const { container } = render(GridWorkspace, { props: { manager, registry } });
    await tick();

    manager.toggleWidgetVisibility(top.id); // hide → the other widget compacts up
    flushSync();
    await tick();

    manager.toggleWidgetVisibility(top.id); // show again
    flushSync();
    await tick();
    await Promise.resolve(); // deferred mount places it
    await Promise.resolve(); // our save microtask, queued behind it

    const element = container.querySelector<HTMLElement>(`[data-widget-id="${top.id}"]`)!;
    const onScreen = {
      x: parseInt(element.getAttribute("gs-x") ?? "-1"),
      y: parseInt(element.getAttribute("gs-y") ?? "-1"),
    };
    expect(persisted.at(-1)).toEqual(onScreen);
  });

  it("pushes programmatically restored layouts back into the grid", async () => {
    const manager = new WorkspaceManager(registry, {} as DatasetGateway);
    const widget = manager.addWidget("stub", { layout: { x: 0, y: 0, w: 6, h: 6 } })!;

    const { container } = render(GridWorkspace, { props: { manager, registry } });
    await tick();
    await Promise.resolve();
    await tick();

    // What "Reset layout" does: rewrite the layout, then bump the revision.
    manager.updateLayout(widget.id, { x: 6, y: 0, w: 6, h: 6 });
    manager.layoutRevision++;
    flushSync();
    await tick();

    const element = container.querySelector<HTMLElement>(`[data-widget-id="${widget.id}"]`)!;
    expect(element.getAttribute("gs-x")).toBe("6");
  });

  it("lets a programmatic arrangement hide a widget without compacting the rest", async () => {
    // Regression: "Reset layout" sets every position *and* hides a widget in one
    // go. The reconciliation effect used to treat that hide as the user's, run
    // the gap-fill, and overwrite the positions the restore had just chosen —
    // so the restore silently produced a compacted layout instead.
    const manager = new WorkspaceManager(registry, {} as DatasetGateway);
    const top = manager.addWidget("stub", { layout: { x: 0, y: 0, w: 6, h: 6 } })!;
    const bottom = manager.addWidget("stub", { layout: { x: 0, y: 6, w: 6, h: 6 } })!;
    const layoutOf = (id: string) => manager.widgets.find((w) => w.id === id)!.layout;

    render(GridWorkspace, { props: { manager, registry } });
    await tick();
    await Promise.resolve();
    await tick();

    // Exactly what restoreOpeningLayout/fitLayoutToViewport do: rewrite the
    // layouts, flip visibility, then bump the revision as one arrangement.
    manager.widgets.find((w) => w.id === top.id)!.hidden = true;
    manager.updateLayout(bottom.id, { x: 0, y: 6, w: 6, h: 6 });
    manager.layoutRevision++;
    flushSync();
    await tick();

    // Compaction would have pulled it to y=0; the chosen position must survive.
    expect(layoutOf(bottom.id).y).toBe(6);
  });

  it("restores the opening arrangement through the real manager call", async () => {
    // End-to-end over the seam the earlier test only imitated: a genuine
    // restoreOpeningLayout() must survive the reconciliation effect and land on
    // screen, hidden view included.
    // The opening arrangement deliberately leaves a gap *above* the visible
    // widget: the hidden one sits on top. Compaction would pull the visible one
    // up into that gap, so y=3 surviving is what proves the restore won.
    const { manager, registry: seedingRegistry } = makeRecordSetup({
      version: DATASET_LAYOUT_VERSION,
      views: {
        cam_1: { layout: { x: 0, y: 0, w: 12, h: 3 }, hidden: true },
        cam_2: { layout: { x: 0, y: 3, w: 12, h: 3 }, hidden: false },
      },
    });

    const { container } = render(GridWorkspace, {
      props: { manager, registry: seedingRegistry },
    });
    await manager.selectRecordInDataset("ds-1", "rec-1", { width: 1600, height: 900 });
    flushSync();
    await tick();
    await Promise.resolve();
    await tick();

    // The user reveals the hidden view and drags the other one elsewhere.
    manager.toggleWidgetVisibility(manager.widgets[0].id);
    flushSync();
    await tick();
    await Promise.resolve();
    await tick();
    manager.updateLayout(manager.widgets[1].id, { x: 6, y: 0, w: 6, h: 3 });

    manager.restoreOpeningLayout();
    flushSync();
    await tick();
    await Promise.resolve();
    await tick();

    // cam_1 hidden again, cam_2 back at y=3 — the gap above it left untouched.
    expect(mountedIds(container)).toEqual([manager.widgets[1].id]);
    const element = container.querySelector<HTMLElement>(
      `[data-widget-id="${manager.widgets[1].id}"]`,
    )!;
    expect(element.getAttribute("gs-x")).toBe("0");
    expect(element.getAttribute("gs-y")).toBe("3");
    expect(element.getAttribute("gs-w")).toBe("12");
  });

  it("fits every widget on screen through the real manager call", async () => {
    // Seven views — a 6-camera + lidar rig — is the first count the comfort
    // floor cannot fit, so it is what makes this assertion meaningful.
    const VIEWPORT = { width: 1600, height: 900 };
    const VISIBLE_ROWS = 6; // floor(12 * 900 / 1600)
    const { manager, registry: seedingRegistry } = makeRecordSetup(undefined, 7);

    const { container } = render(GridWorkspace, {
      props: { manager, registry: seedingRegistry },
    });
    await manager.selectRecordInDataset("ds-1", "rec-1", VIEWPORT);
    flushSync();
    await tick();
    await Promise.resolve();
    await tick();

    manager.toggleWidgetVisibility(manager.widgets[0].id);
    flushSync();
    await tick();

    manager.fitLayoutToViewport(VIEWPORT);
    flushSync();
    await tick();
    await Promise.resolve();
    await tick();

    expect(manager.widgets.every((w) => w.hidden === false)).toBe(true);

    // Asserted on the DOM, not on the manager: GridStack keeps the minH a node
    // was mounted with, so a fitted cell that the grid clamped back up would
    // still look correct in the manager while overflowing on screen.
    const elements = [...container.querySelectorAll<HTMLElement>("[data-widget-id]")];
    expect(elements).toHaveLength(7);
    for (const element of elements) {
      const y = parseInt(element.getAttribute("gs-y") ?? "0");
      const h = parseInt(element.getAttribute("gs-h") ?? "0");
      expect(y + h).toBeLessThanOrEqual(VISIBLE_ROWS);
    }
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
