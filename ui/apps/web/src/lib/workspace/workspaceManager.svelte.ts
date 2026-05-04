/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ImageWidgetStorage, ResourceMutation } from "$lib/annotations/types.js";
import type { WidgetInstance, WidgetLayout, WorkspacePreset } from "$lib/extensions/types.js";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";

import { httpDatasetGateway, type DatasetGateway } from "./datasetGateway.js";
import type { Viewport } from "./layoutPlanner.js";
import { MutationQueue } from "./mutationQueue.svelte.js";
import { RecordLoader } from "./recordLoader.js";
import { WorkspaceSession } from "./workspaceSession.svelte.js";

/**
 * Reactive workspace facade. Owns:
 *
 *   - widget instances + their per-instance storage,
 *   - edit-mode and preset UI state,
 *   - the wiring that composes the sub-services
 *     (`WorkspaceSession`, `MutationQueue`, `RecordLoader`).
 *
 * Everything else delegates:
 *
 *  - `datasetId`, `recordId`         → `WorkspaceSession`
 *  - `pendingMutations`, `saving`,   → `MutationQueue`
 *    `saveError`, `pendingCount`,
 *    `queueMutation`, `flushSave`,
 *    `dropMutationsForLocalBBox`
 *  - `selectRecordInDataset`         → `RecordLoader`
 *
 * The single public surface keeps consumers (LeftPanel, Toolbar,
 * StatusBar, ImageWidget, GridWorkspace, RightPanel) reaching through
 * `manager.X` regardless of where the implementation lives.
 */
export class WorkspaceManager {
  widgets = $state<WidgetInstance[]>([]);
  editMode = $state(true);
  presetName = $state("Default");
  widgetCount = $derived(this.widgets.length);

  private registry: WidgetRegistry;
  private storageMap: Map<string, Record<string, unknown>> = new Map();

  private session: WorkspaceSession;
  private mutations: MutationQueue;
  private loader: RecordLoader;

  constructor(registry: WidgetRegistry, gateway: DatasetGateway = httpDatasetGateway) {
    this.registry = registry;
    this.session = new WorkspaceSession();

    // Locator closure keeps `ImageWidgetStorage`-shape knowledge confined
    // to this wiring; `MutationQueue` itself stays widget-storage-agnostic.
    this.mutations = new MutationQueue(gateway, this.session, {
      findLocalBBox: (widgetId, localBBoxId) => {
        const storage = this.storageMap.get(widgetId) as
          | ImageWidgetStorage
          | undefined;
        return storage?.bboxes.find((b) => b.id === localBBoxId);
      },
    });

    this.loader = new RecordLoader({
      workspace: this,
      registry,
      gateway,
      session: this.session,
    });
  }

  // ─── Session forwarders ───────────────────────────────────────────────────
  // Reading a `$state` through a getter triggers Svelte 5 reactivity at
  // the consumer's read site, so templates like `manager.datasetId` track
  // updates as if the field lived on this class.

  get datasetId(): string | null {
    return this.session.datasetId;
  }

  get recordId(): string | null {
    return this.session.recordId;
  }

  // ─── Mutation queue forwarders ────────────────────────────────────────────

  get pendingMutations(): ResourceMutation[] {
    return this.mutations.pending;
  }

  get pendingCount(): number {
    return this.mutations.count;
  }

  get saving(): boolean {
    return this.mutations.saving;
  }

  get saveError(): string | null {
    return this.mutations.saveError;
  }

  /** Queue a resource mutation for the next `flushSave`. */
  queueMutation(mutation: ResourceMutation): void {
    this.mutations.queue(mutation);
  }

  /** Drop every queued mutation referencing the given local bbox id. */
  dropMutationsForLocalBBox(localBBoxId: string): ResourceMutation[] {
    return this.mutations.dropForLocalBBox(localBBoxId);
  }

  /** Flush every queued mutation to the backend. */
  flushSave(): Promise<void> {
    return this.mutations.flush();
  }

  // ─── Record loader forwarder ──────────────────────────────────────────────

  /** Load a record's widgets via the registered extensions' `addRecordSeed` hooks. */
  selectRecordInDataset(
    datasetId: string,
    recordId: string,
    viewport?: Viewport,
  ): Promise<void> {
    return this.loader.load(datasetId, recordId, viewport);
  }

  // ─── Widget lifecycle ─────────────────────────────────────────────────────

  /**
   * Add a new widget instance for the given extension name.
   *
   * `seedStorage` is merged into the storage object built by the
   * extension's `addStorage()` factory, so the widget is created already
   * populated with its starting state (e.g. pre-fetched bboxes from
   * `RecordLoader`).
   */
  addWidget(
    extensionName: string,
    overrides?: Partial<WidgetInstance>,
    seedStorage?: Record<string, unknown>,
  ): WidgetInstance | null {
    const config = this.registry.get(extensionName);
    if (!config) {
      console.warn(`Extension "${extensionName}" not found in registry`);
      return null;
    }

    const options = config.addOptions?.() ?? {};
    const storage = { ...(config.addStorage?.() ?? {}), ...(seedStorage ?? {}) };

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

  /** Remove a widget by ID. */
  removeWidget(id: string): void {
    this.storageMap.delete(id);
    this.widgets = this.widgets.filter((w) => w.id !== id);
  }

  /** Update a widget's grid layout. */
  updateLayout(id: string, layout: Partial<WidgetLayout>): void {
    const widget = this.widgets.find((w) => w.id === id);
    if (widget) {
      widget.layout = { ...widget.layout, ...layout };
    }
  }

  /** Get the mutable storage for a widget instance. */
  getStorage(id: string): Record<string, unknown> | undefined {
    return this.storageMap.get(id);
  }

  /**
   * Clear the visual workspace. The active `datasetId`/`recordId`
   * selection is intentionally preserved so a subsequent `flushSave`
   * still targets whatever record the user last opened.
   */
  clearWorkspace(): void {
    this.storageMap.clear();
    this.widgets = [];
    this.mutations.reset();
  }

  /** Apply a workspace preset, replacing all current widgets. */
  applyPreset(preset: WorkspacePreset): void {
    this.storageMap.clear();
    this.widgets = [];
    this.presetName = preset.name;

    for (const template of preset.widgets) {
      this.addWidget(template.extensionName, template);
    }
  }
}
