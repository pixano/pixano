/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { cleanup, render, screen } from "@testing-library/svelte";
import { flushSync } from "svelte";
import { afterEach, describe, expect, it } from "vitest";

import RightPanel from "../RightPanel.svelte";
import type { WidgetExtensionConfig } from "$lib/extensions/types.js";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import type { DatasetGateway } from "$lib/workspace/datasetGateway.js";
import { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

// The inspector tab owns every control that can move a widget: the two layout
// actions and the per-widget visibility toggles. They must agree on the
// workspace lock — a hide compacts the neighbours and the grid stores the
// result, so an ungated eye toggle would write the very arrangement the lock
// exists to protect.

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

function makeManagerWithWidgets() {
  const manager = new WorkspaceManager(registry, {} as DatasetGateway);
  manager.addWidget("stub", { title: "Front camera" });
  manager.addWidget("stub", { title: "Lidar" });
  return manager;
}

// jest-dom's `toBeDisabled` is not typed in this workspace (the same gap the
// LeftPanel suite hits with `toBeInTheDocument`), so assert on the DOM property.
const isDisabled = (element: HTMLElement) => (element as HTMLButtonElement).disabled;

/** The layout actions plus every per-widget visibility toggle. */
function widgetControls(): HTMLElement[] {
  return [
    screen.getByRole("button", { name: /reset layout/i }),
    screen.getByRole("button", { name: /fit layout/i }),
    ...screen.getAllByTitle(/show widget|hide widget|unlock the workspace/i),
  ];
}

afterEach(() => cleanup());

describe("RightPanel — workspace lock", () => {
  it("disables every control that can move a widget while locked", () => {
    const manager = makeManagerWithWidgets();
    manager.editMode = false;

    render(RightPanel, { props: { manager } });
    flushSync();

    for (const control of widgetControls()) {
      expect(isDisabled(control)).toBe(true);
    }
  });

  it("explains why the controls are inert", () => {
    const manager = makeManagerWithWidgets();
    manager.editMode = false;

    render(RightPanel, { props: { manager } });
    flushSync();

    expect(screen.getAllByTitle(/unlock the workspace/i).length).toBeGreaterThan(0);
  });

  it("re-enables the visibility toggles once unlocked", () => {
    const manager = makeManagerWithWidgets();
    manager.editMode = true;

    render(RightPanel, { props: { manager } });
    flushSync();

    for (const toggle of screen.getAllByTitle(/hide widget/i)) {
      expect(isDisabled(toggle)).toBe(false);
    }
    expect(isDisabled(screen.getByRole("button", { name: /fit layout/i }))).toBe(false);
  });

  it("keeps Reset disabled until a record has been opened", () => {
    // Widgets exist (added from the palette) but no record has loaded, so there
    // is no opening arrangement to go back to.
    const manager = makeManagerWithWidgets();

    render(RightPanel, { props: { manager } });
    flushSync();

    expect(manager.hasOpeningLayout).toBe(false);
    expect(isDisabled(screen.getByRole("button", { name: /reset layout/i }))).toBe(true);
  });

  it("offers no layout controls on an empty workspace", () => {
    const manager = new WorkspaceManager(registry, {} as DatasetGateway);

    render(RightPanel, { props: { manager } });
    flushSync();

    expect(screen.queryByRole("button", { name: /reset layout/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /fit layout/i })).toBeNull();
  });
});
