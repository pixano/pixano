<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import "gridstack/dist/gridstack.min.css";

  import { GridStack, type GridStackNode } from "gridstack";
  import { mount, onDestroy, onMount, unmount } from "svelte";

  import { fillGapAndSync, placeWidget } from "./gridReflow.js";
  import WidgetFrame from "./WidgetFrame.svelte";
  import type { WidgetInstance } from "$lib/extensions/types.js";
  import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  interface Props {
    manager: WorkspaceManager;
    registry: WidgetRegistry;
  }

  let { manager, registry }: Props = $props();

  let grid: GridStack;
  let mountedWidgets: Map<string, Record<string, unknown>> = new Map();
  let lastManipulationEvent = 0;

  function mountWidget(widget: WidgetInstance) {
    const config = registry.get(widget.extensionName);
    if (!config) return;

    const element = document.createElement("div");
    element.dataset.widgetId = widget.id;
    grid.el.appendChild(element);

    const component = mount(WidgetFrame, {
      target: element,
      context: new Map<string, unknown>([["workspaceManager", manager]]),
      props: {
        widget,
        config,
        onRemove: () => manager.removeWidget(widget.id),
      },
    });

    mountedWidgets.set(widget.id, component);

    // Honor the computed layout even when it is below the extension's default
    // minW/minH; otherwise GridStack silently enlarges the widget and breaks
    // the alignment of programmatically computed grids.
    const minW = Math.min(widget.layout.w, config.defaultLayout.minW ?? 2);
    const minH = Math.min(widget.layout.h, config.defaultLayout.minH ?? 2);

    // Keep the stored spot when free, else drop into the next free spot (used
    // when a re-shown widget's original slot was filled by a prior compaction).
    placeWidget(grid, element, widget.id, widget.layout, minW, minH, manager);
  }

  function unmountWidget(widgetId: string) {
    const component = mountedWidgets.get(widgetId);
    if (!component) return;

    unmount(component);
    mountedWidgets.delete(widgetId);

    const element = grid.getGridItems().find((i) => i.dataset.widgetId === widgetId);
    if (element) {
      grid.removeWidget(element, true);
    }
  }

  function parseLayoutFromElement(element: HTMLElement) {
    return {
      x: parseInt(element.getAttribute("gs-x") ?? "0"),
      y: parseInt(element.getAttribute("gs-y") ?? "0"),
      w: parseInt(element.getAttribute("gs-w") ?? "0"),
      h: parseInt(element.getAttribute("gs-h") ?? "0"),
    };
  }

  function onGridMoveOrResize() {
    lastManipulationEvent = Date.now();
  }

  function onGridItemsChange(_: Event, items: GridStackNode[]) {
    if (Date.now() - lastManipulationEvent > 10) return;

    for (const item of items) {
      const element = item.el;
      if (!element) continue;

      const widgetId = element.dataset.widgetId;
      if (!widgetId) continue;

      const layout = parseLayoutFromElement(element);
      manager.updateLayout(widgetId, layout);
    }
  }

  function onGridItemAdded(_: Event, items: GridStackNode[]) {
    for (const item of items) {
      const element = item.el;
      if (!element) continue;

      const child = element.firstElementChild;
      if (!child || !child.classList.contains("sidebar-draggable")) continue;

      const extensionName = child.getAttribute("data-extension-name");
      if (!extensionName) continue;

      const layout = parseLayoutFromElement(element);
      grid.removeWidget(element, false);

      const widget = manager.addWidget(extensionName, { layout });
      if (widget) {
        mountWidget(widget);
      }
    }
  }

  onMount(() => {
    grid = GridStack.init({
      cellHeight: "auto",
      acceptWidgets: true,
      handleClass: "grid-stack-handle",
      margin: 5,
      animate: false,
      float: true,
    });

    grid.on("added", onGridItemAdded);
    grid.on("dragstop resizestop", onGridMoveOrResize);
    grid.on("change", onGridItemsChange);

    // Mount initial widgets
    for (const widget of manager.widgets) {
      mountWidget(widget);
    }
  });

  // Sync editMode with GridStack static mode
  $effect(() => {
    if (grid) {
      grid.setStatic(!manager.editMode);
    }
  });

  // React to widget additions/removals/visibility changes from manager
  $effect(() => {
    if (!grid) return;

    const currentIds = new Set(mountedWidgets.keys());
    const managerIds = new Set(manager.widgets.map((w) => w.id));
    const visibleWidgets = manager.widgets.filter((w) => !w.hidden);
    const visibleIds = new Set(visibleWidgets.map((w) => w.id));

    // Remove widgets no longer visible. Distinguish a *hide* (widget still owned
    // by the manager, just toggled off) from a *removal* (record switch / delete):
    // only a hide should reflow the remaining widgets to fill the freed space.
    let didHide = false;
    for (const id of currentIds) {
      if (!visibleIds.has(id)) {
        unmountWidget(id);
        if (managerIds.has(id)) didHide = true;
      }
    }

    // Fill the hole left by a hidden widget without resizing anything, then
    // persist the shifted positions (compact() moves items programmatically, so
    // GridStack's user-drag persistence path never sees them).
    if (didHide) {
      fillGapAndSync(grid, manager);
    }

    // Add newly visible widgets. mountWidget places a re-shown widget in the next
    // free spot when its original position is now taken.
    for (const widget of visibleWidgets) {
      if (!currentIds.has(widget.id)) {
        mountWidget(widget);
      }
    }
  });

  onDestroy(() => {
    for (const component of mountedWidgets.values()) {
      unmount(component);
    }
    mountedWidgets.clear();

    if (grid) {
      // The grid element may already be detached when we tear down (a parent
      // removed first, or the test harness clearing the DOM); destroy() would
      // then throw on removeChild. The grid is going away regardless, so ignore it.
      try {
        grid.destroy();
      } catch {
        grid = undefined as unknown as GridStack;
      }
    }
  });
</script>

<div class="grid-stack h-full w-full"></div>
