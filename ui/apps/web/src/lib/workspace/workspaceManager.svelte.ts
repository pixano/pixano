/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as api from "$lib/api";
import type { WidgetInstance, WidgetLayout, WorkspacePreset } from "$lib/extensions/types.js";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";

/**
 * Reactive workspace manager using Svelte 5 $state runes.
 * Manages the collection of widget instances and bridges
 * between the WidgetRegistry (blueprints) and GridStack (DOM).
 */
export class WorkspaceManager {
  widgets = $state<WidgetInstance[]>([]);
  editMode = $state(true);
  presetName = $state("Default");
  datasetId = $state<string | null>("NSn7gHtkh6366dWXz6kdwF");
  recordId = $state<string | null>("85dMNwowyc7ZXQrWNSyBmc");

  widgetCount = $derived(this.widgets.length);

  private registry: WidgetRegistry;
  private storageMap: Map<string, Record<string, unknown>> = new Map();

  constructor(registry: WidgetRegistry) {
    this.registry = registry;
  }

  /** Add a new widget instance for the given extension name */
  addWidget(extensionName: string, overrides?: Partial<WidgetInstance>): WidgetInstance | null {
    const config = this.registry.get(extensionName);
    if (!config) {
      console.warn(`Extension "${extensionName}" not found in registry`);
      return null;
    }

    const options = config.addOptions?.() ?? {};
    const storage = config.addStorage?.() ?? {};

    const widget: WidgetInstance = {
      id: crypto.randomUUID(),
      extensionName,
      title: overrides?.title ?? config.label,
      layout: overrides?.layout ?? { ...config.defaultLayout },
      options: { ...options, ...overrides?.options },
      data: overrides?.data,
    };

    this.storageMap.set(widget.id, storage);
    this.widgets.push(widget);
    return widget;
  }

  /** Remove a widget by ID */
  removeWidget(id: string): void {
    this.storageMap.delete(id);
    this.widgets = this.widgets.filter((w) => w.id !== id);
  }

  /** Update a widget's grid layout */
  updateLayout(id: string, layout: Partial<WidgetLayout>): void {
    const widget = this.widgets.find((w) => w.id === id);
    if (widget) {
      widget.layout = { ...widget.layout, ...layout };
    }
  }

  /** Get the mutable storage for a widget instance */
  getStorage(id: string): Record<string, unknown> | undefined {
    return this.storageMap.get(id);
  }

  /** Clear the workspace */
  clearWorkspace(): void {
    this.storageMap.clear();
    this.widgets = [];
  }

  /** Apply a workspace preset, replacing all current widgets */
  applyPreset(preset: WorkspacePreset): void {
    // Clear existing
    this.storageMap.clear();
    this.widgets = [];
    this.presetName = preset.name;

    // Add widgets from preset
    for (const template of preset.widgets) {
      this.addWidget(template.extensionName, template);
    }
  }

  async selectRecordInDataset(datasetId: string, recordId: string): Promise<void> {
    const dataset = await api.getDataset(datasetId);
    const views = dataset.info.views ?? {};

    // Keep only views we know how to render, preserving dataset order.
    const renderableBases = new Set(["Image", "PointCloud", "SequenceFrame", "Text"]);
    const viewEntries = Object.entries(views).filter(([, v]) => !!v.base && renderableBases.has(v.base));
    const n = viewEntries.length;
    if (n === 0) return;

    // Compute a grid layout that fits all widgets on screen.
    // GridStack uses 12 columns with square cells, so we target a total
    // number of cell-rows that matches the grid container's aspect ratio,
    // which keeps every widget visible without scrolling.
    const TOTAL_COLS = 12;
    const gridEl = typeof document !== "undefined" ? document.querySelector(".grid-stack") : null;
    const containerW = (gridEl as HTMLElement | null)?.clientWidth ?? 1600;
    const containerH = (gridEl as HTMLElement | null)?.clientHeight ?? 900;
    const totalRows = Math.max(2, Math.round((TOTAL_COLS * containerH) / containerW));

    const cols = Math.min(TOTAL_COLS, Math.ceil(Math.sqrt(n)));
    const rows = Math.ceil(n / cols);
    const w = Math.max(1, Math.floor(TOTAL_COLS / cols));
    const h = Math.max(1, Math.floor(totalRows / rows));

    for (let i = 0; i < n; i++) {
      const [viewName, viewDef] = viewEntries[i];
      const col = i % cols;
      const row = Math.floor(i / cols);
      const layout: WidgetLayout = { x: col * w, y: row * h, w, h };

      if (viewDef.base === "Image") {
        const imageUrl = await api
          .loadImageByLogicalName(datasetId, recordId, viewName)
          .then((image) => image?.src);
        this.addWidget("image", {
          extensionName: "image",
          title: viewName,
          layout,
          options: {},
          data: { imageUrl },
        });
      } else if (viewDef.base === "PointCloud") {
        const pointCloudUrl = await api
          .loadPointCloudByLogicalName(datasetId, recordId, viewName)
          .then((pointCloud) => pointCloud?.src);
        this.addWidget("point-cloud", {
          extensionName: "point-cloud",
          title: viewName,
          layout,
          options: {},
          data: { pointCloudUrl },
        });
      } else if (viewDef.base === "SequenceFrame") {
        this.addWidget("sequence-frame", {
          extensionName: "sequence-frame",
          title: viewName,
          layout,
          options: {},
        });
      } else if (viewDef.base === "Text") {
        this.addWidget("text", {
          extensionName: "text",
          title: viewName,
          layout,
          options: {},
        });
      }
    }
  }
}
