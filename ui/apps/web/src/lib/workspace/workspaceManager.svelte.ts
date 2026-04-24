/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { sortMutations } from "$lib/annotations/buildPayloads.js";
import type {
  CoordsNorm,
  ImageWidgetStorage,
  LocalBBox,
  ResourceMutation,
} from "$lib/annotations/types.js";
import * as api from "$lib/api";
import type { BBoxRow, EntityRow } from "$lib/api/annotations.js";
import { ApiError } from "$lib/api/apiClient.js";
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
  pendingMutations = $state<ResourceMutation[]>([]);
  saving = $state(false);
  saveError = $state<string | null>(null);

  widgetCount = $derived(this.widgets.length);
  pendingCount = $derived(this.pendingMutations.length);

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
    this.pendingMutations = [];
    this.saveError = null;
  }

  /**
   * Queue a resource mutation to be flushed later via `flushSave`.
   * Mirrors pixano's saveData/saveTo pattern.
   */
  queueMutation(mutation: ResourceMutation): void {
    this.pendingMutations.push(mutation);
  }

  /**
   * Drop every queued mutation that references the given local bbox id. Used
   * when a bbox is deleted locally before it has been persisted, so we don't
   * POST-then-DELETE it for nothing.
   */
  dropMutationsForLocalBBox(localBBoxId: string): ResourceMutation[] {
    const dropped: ResourceMutation[] = [];
    this.pendingMutations = this.pendingMutations.filter((m) => {
      if (m.localBBoxId === localBBoxId) {
        dropped.push(m);
        return false;
      }
      return true;
    });
    return dropped;
  }

  /**
   * Flush every queued mutation to the backend. Entities are created before
   * the bboxes that reference them; deletes run last. On success, local
   * LocalBBox entries are marked as `persisted: true`.
   */
  async flushSave(): Promise<void> {
    if (this.saving) return;
    if (!this.datasetId) {
      this.saveError = "No dataset selected.";
      return;
    }
    if (this.pendingMutations.length === 0) return;

    this.saving = true;
    this.saveError = null;

    const ordered = sortMutations(this.pendingMutations);

    try {
      for (const mutation of ordered) {
        await this.runMutation(this.datasetId, mutation);
        if (
          mutation.op === "create" &&
          mutation.resource === "bboxes" &&
          mutation.widgetId &&
          mutation.localBBoxId
        ) {
          const storage = this.storageMap.get(mutation.widgetId) as
            | ImageWidgetStorage
            | undefined;
          const bbox = storage?.bboxes.find((b) => b.id === mutation.localBBoxId);
          if (bbox) bbox.persisted = true;
        }
      }
      this.pendingMutations = [];
    } catch (err) {
      if (err instanceof ApiError) {
        // Surface the backend's `detail` so the user can see why the request
        // was rejected (e.g. "Invalid data: <field> extra inputs are not
        // permitted" or "Foreign key violation: record_id=... not found").
        console.error("flushSave - failing mutation body:", err.body);
        this.saveError = `${err.message}: ${err.body}`;
      } else {
        this.saveError = err instanceof Error ? err.message : String(err);
      }
    } finally {
      this.saving = false;
    }
  }

  private async runMutation(datasetId: string, mutation: ResourceMutation): Promise<void> {
    if (mutation.op === "create" && mutation.resource === "entities") {
      console.debug("flushSave -> POST entities", mutation.body);
      await api.createEntity(datasetId, mutation.body);
      return;
    }
    if (mutation.op === "create" && mutation.resource === "bboxes") {
      console.debug("flushSave -> POST bboxes", mutation.body);
      await api.createBBox(datasetId, mutation.body);
      return;
    }
    if (mutation.op === "update" && mutation.resource === "bboxes") {
      await api.updateBBox(datasetId, mutation.id, mutation.body);
      return;
    }
    if (mutation.op === "delete" && mutation.resource === "bboxes") {
      await api.deleteBBox(datasetId, mutation.id);
      return;
    }
    if (mutation.op === "delete" && mutation.resource === "entities") {
      await api.deleteEntity(datasetId, mutation.id);
      return;
    }
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
    // GridStack uses 12 columns with cellHeight: "auto" (square cells), so the
    // number of visible rows ≈ floor(containerH / (containerW / 12)).
    //
    // Widget extensions enforce a minimum size (image/point-cloud need w,h ≥ 3).
    // If we hand GridStack a smaller cell, it silently inflates the widget and
    // breaks the alignment of the grid, so we clamp w and h to that minimum and
    // restrict cols to divisors of 12 (≤ 4) so each row fills the full width.
    const TOTAL_COLS = 12;
    const MIN_CELL = 3;
    const MAX_COLS = Math.floor(TOTAL_COLS / MIN_CELL); // = 4

    const gridEl = typeof document !== "undefined" ? document.querySelector(".grid-stack") : null;
    const containerW = Math.max(1, (gridEl as HTMLElement | null)?.clientWidth ?? 1600);
    const containerH = Math.max(1, (gridEl as HTMLElement | null)?.clientHeight ?? 900);
    const visibleRows = Math.max(MIN_CELL, Math.floor((TOTAL_COLS * containerH) / containerW));

    const cols = Math.max(1, Math.min(MAX_COLS, Math.ceil(Math.sqrt(n))));
    const rows = Math.ceil(n / cols);
    const w = Math.max(MIN_CELL, Math.floor(TOTAL_COLS / cols));
    const h = Math.max(MIN_CELL, Math.floor(visibleRows / rows));

    // Entities are record-scoped (a bbox points at an entity via entity_id,
    // and that entity row lives in the dataset's single entities table), so
    // we fetch them once here and hand each image widget the relevant
    // subset when we seed its bboxes. Falling back to an empty map keeps
    // the widget usable if the endpoint errors.
    const entitiesById = new Map<string, EntityRow>();
    const entityRows = await api
      .listEntities(datasetId, { recordId })
      .catch((err) => {
        console.error("listEntities failed", err);
        return [] as EntityRow[];
      });
    for (const entity of entityRows) entitiesById.set(entity.id, entity);

    for (let i = 0; i < n; i++) {
      const [viewName, viewDef] = viewEntries[i];
      const col = i % cols;
      const row = Math.floor(i / cols);
      const layout: WidgetLayout = { x: col * w, y: row * h, w, h };

      if (viewDef.base === "Image") {
        const image = await api.loadImageByLogicalName(datasetId, recordId, viewName);

        // Pre-fetch any bboxes already stored for this (record, view) pair so
        // we can hand them to the widget at mount time. If the fetch fails we
        // log and fall back to an empty list — the user can still draw new
        // boxes.
        const existingBBoxes = image?.id
          ? await api
              .listBBoxes(datasetId, { recordId, viewId: image.id })
              .catch((err) => {
                console.error("listBBoxes failed", err);
                return [] as BBoxRow[];
              })
          : [];

        const widget = this.addWidget("image", {
          extensionName: "image",
          title: viewName,
          layout,
          options: {
            datasetId,
            recordId,
            viewId: image?.id ?? "",
            viewName,
            imageWidth: image?.width ?? 0,
            imageHeight: image?.height ?? 0,
          },
          data: { imageUrl: image?.src },
        });

        if (widget && existingBBoxes.length > 0) {
          const storage = this.storageMap.get(widget.id) as ImageWidgetStorage | undefined;
          if (storage) {
            storage.bboxes = existingBBoxes
              .filter((b) => Array.isArray(b.coords) && b.coords.length === 4 && b.is_normalized)
              .map<LocalBBox>((b) => ({
                id: b.id,
                entityId: b.entity_id,
                coordsNorm: [...b.coords] as CoordsNorm,
                persisted: true,
                entity: entitiesById.get(b.entity_id),
              }));
          }
        }
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
