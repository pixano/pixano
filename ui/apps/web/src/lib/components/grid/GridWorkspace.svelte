<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import "gridstack/dist/gridstack.min.css";

  import { GridStack, type GridStackNode } from "gridstack";
  import { mount, onDestroy, onMount, unmount, untrack } from "svelte";

  import { DEFAULT_MIN_CELL, GESTURE_CHANGE_WINDOW_MS } from "./gridConstants.js";
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
  // Value is the mounted Svelte component, or null while its deferred mount is
  // still pending (see mountWidget).
  let mountedWidgets: Map<string, Record<string, unknown> | null> = new Map();
  let lastManipulationEvent = 0;
  // The widget ids the manager held at the previous reconciliation (hidden
  // widgets included — hiding keeps a widget owned), so a mount can be told
  // apart: a known id coming back is the user re-showing a widget (an
  // arrangement change worth remembering), an unknown one is a record load or
  // a palette add.
  let knownWidgetIds: Set<string> = new Set();
  // Last programmatic arrangement pushed into the grid. Lets the reconciliation
  // effect tell "the manager just rearranged everything" from "the user hid one
  // widget", which need opposite handling of the freed space.
  let appliedRevision = 0;

  /**
   * The size constraints to hand GridStack for a widget.
   *
   * Capped by the widget's own size so a computed layout below the extension's
   * declared minimum is honoured rather than silently inflated — which is what
   * "Fit layout" produces when a record has more views than the viewport can
   * show comfortably, and what breaks the alignment of a whole tiled grid.
   */
  function minCellFor(widget: WidgetInstance) {
    const config = registry.get(widget.extensionName);
    return {
      minW: Math.min(widget.layout.w, config?.defaultLayout.minW ?? DEFAULT_MIN_CELL),
      minH: Math.min(widget.layout.h, config?.defaultLayout.minH ?? DEFAULT_MIN_CELL),
    };
  }

  function mountWidget(widget: WidgetInstance) {
    const config = registry.get(widget.extensionName);
    if (!config) return;

    const element = document.createElement("div");
    element.dataset.widgetId = widget.id;
    grid.el.appendChild(element);

    // Reserve the slot before the deferred mount so the reconciliation effect
    // stays idempotent and unmountWidget can cancel a not-yet-run mount.
    mountedWidgets.set(widget.id, null);

    // Mount in a microtask, outside any reactive context. A component root
    // created inside a re-running $effect is "detached" by Svelte on the next
    // re-run while staying reachable from this component's effect tree; when
    // such a half-detached root is later scheduled together with the app root
    // in one flush, Svelte's scheduler permanently stops updating it (the
    // widget freezes: toolbar, gizmos and resize go dead while the canvas
    // keeps rendering). Deferring makes each widget an independent root from
    // birth, which that scheduler conflict cannot reach.
    queueMicrotask(() => {
      // Unmounted (or workspace destroyed) before the mount could run. The
      // element check covers an unmount + remount of the same id in between:
      // only the latest attempt's element is still in the grid.
      if (!mountedWidgets.has(widget.id) || !element.isConnected) return;

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
      const { minW, minH } = minCellFor(widget);

      // Keep the stored spot when free, else drop into the next free spot (used
      // when a re-shown widget's original slot was filled by a prior compaction).
      // Registered only after the mount: GridStack resolves the drag handle
      // (.grid-stack-handle, the frame's title bar) from the item's content when
      // it wires dragging — registering an empty element would make the whole
      // widget draggable from anywhere, including the 3D canvas.
      placeWidget(grid, element, widget.id, widget.layout, minW, minH, manager);
    });
  }

  function unmountWidget(widgetId: string) {
    if (!mountedWidgets.has(widgetId)) return;

    // A null entry means the deferred mount hasn't run yet; deleting the entry
    // cancels it (the microtask bails when the id is gone from the map).
    const component = mountedWidgets.get(widgetId);
    mountedWidgets.delete(widgetId);
    if (component) void unmount(component);

    const element = grid.getGridItems().find((i) => i.dataset.widgetId === widgetId);
    if (element) {
      grid.removeWidget(element, true);
    } else {
      // The deferred mount hadn't registered the element with GridStack yet;
      // it is still a plain child of the grid container.
      grid.el.querySelector(`[data-widget-id="${CSS.escape(widgetId)}"]`)?.remove();
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
    if (Date.now() - lastManipulationEvent > GESTURE_CHANGE_WINDOW_MS) return;

    for (const item of items) {
      const element = item.el;
      if (!element) continue;

      const widgetId = element.dataset.widgetId;
      if (!widgetId) continue;

      const layout = parseLayoutFromElement(element);
      manager.updateLayout(widgetId, layout);
    }

    // The guard above means we only get here for a drag/resize the user just
    // finished, which is exactly when the arrangement is worth remembering for
    // the dataset's other records.
    manager.saveDatasetLayout();
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

    // A programmatic arrangement ("Reset layout" / "Fit layout") has already
    // decided where every widget goes, including the ones it hides. The gap-fill
    // below exists for a *user* hide and would reshuffle those chosen positions,
    // so it is skipped here; the revision effect applies them instead.
    const authoritative = manager.layoutRevision !== appliedRevision;

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
    if (didHide && !authoritative) {
      fillGapAndSync(grid, manager);
      // Compaction moved the remaining widgets, so the arrangement the user
      // now sees differs from the one stored when they clicked "hide".
      manager.saveDatasetLayout();
    }

    // Add newly visible widgets. mountWidget places a re-shown widget in the next
    // free spot when its original position is now taken.
    let didShow = false;
    for (const widget of visibleWidgets) {
      if (!currentIds.has(widget.id)) {
        if (knownWidgetIds.has(widget.id)) didShow = true;
        mountWidget(widget);
      }
    }

    // A re-shown widget only has its final position once its deferred mount has
    // run and GridStack has resolved a free slot for it, so persist behind those
    // microtasks — ours is queued last and therefore runs after them. Widgets a
    // record load brought in are unknown ids and never reach this.
    if (didShow) queueMicrotask(() => manager.saveDatasetLayout());

    knownWidgetIds = new Set(managerIds);
  });

  // Push layouts the manager rewrote programmatically ("Reset layout" / "Fit
  // layout") into GridStack. It deliberately depends on the revision counter
  // alone: reading the widget layouts here would re-run this on every drag and
  // fight the gesture. Widgets this arrangement re-shows are not on the grid yet
  // — their deferred mount places them from the same (already updated) layout.
  //
  // ORDER MATTERS: this effect must stay declared after the reconciliation
  // effect above. Effects run in declaration order, so the reconciliation pass
  // still sees `layoutRevision !== appliedRevision` and skips its gap-fill;
  // declared the other way round, `appliedRevision` would already be caught up
  // and a restore that hides a widget would get compacted like a user hide.
  $effect(() => {
    const revision = manager.layoutRevision;

    untrack(() => {
      if (grid) {
        for (const element of grid.getGridItems()) {
          const widget = manager.widgets.find((w) => w.id === element.dataset.widgetId);
          // The constraints go with the size: a node keeps the minH it was
          // mounted with, which would clamp a smaller fitted cell straight back
          // up and push the grid past the fold again.
          if (widget) grid.update(element, { ...widget.layout, ...minCellFor(widget) });
        }
      }
      // Marks this arrangement as applied, so the next reconciliation treats a
      // hide as the user's again rather than as part of it.
      appliedRevision = revision;
    });
  });

  onDestroy(() => {
    for (const component of mountedWidgets.values()) {
      if (component) void unmount(component);
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
