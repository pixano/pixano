/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { AnnotationCollection, LocalAnnotation } from "$lib/annotations/annotationCollection.svelte.js";
import { deleteLocalAnnotation } from "$lib/annotations/payloadBuilders.js";
import type {
  PendingAnnotation,
  PendingEntityChoice,
  ResourceMutation,
} from "$lib/annotations/types.js";
import type { EntityRow } from "$lib/api/annotations.js";
import type { WidgetInstance, WidgetLayout, WorkspacePreset } from "$lib/extensions/types.js";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import type { FieldInfo } from "$lib/types/dataset.js";

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
 *    `dropMutationsForLocalAnnotation`
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

  /**
   * A box drawn but awaiting its entity choice in the Inspector. `null` when no
   * box is pending. Set by widgets via `beginPendingAnnotation`.
   */
  pendingAnnotation = $state<PendingAnnotation | null>(null);

  private registry: WidgetRegistry;
  private storageMap: Map<string, Record<string, unknown>> = new Map();

  private session: WorkspaceSession;
  private mutations: MutationQueue;
  private loader: RecordLoader;

  constructor(registry: WidgetRegistry, gateway: DatasetGateway = httpDatasetGateway) {
    this.registry = registry;
    this.session = new WorkspaceSession();

    // Annotations are record-scoped: the queue flips `persisted` directly on
    // the session's shared collection, no per-widget storage lookup needed.
    this.mutations = new MutationQueue(gateway, this.session, {
      findLocalAnnotation: (localAnnotationId) => this.session.annotations.find(localAnnotationId),
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

  get entities(): EntityRow[] {
    return this.session.entities;
  }

  get entitySchemaName(): string | null {
    return this.session.entitySchemaName;
  }

  /** Shared annotations of the loaded record (one collection per record). */
  get annotations(): AnnotationCollection {
    return this.session.annotations;
  }

  get entitySchemaFields(): Record<string, FieldInfo> | null {
    return this.session.entitySchemaFields;
  }

  // ─── Entity-driven annotation visibility ──────────────────────────────────
  // `null` = all entities visible (default). A set isolates the listed entities.
  // Display-only: renderers/derived lists consult `isEntityVisible`; the
  // annotation collection's lifecycle (find/drafts/save) is never filtered.

  get visibleEntityIds(): ReadonlySet<string> | null {
    return this.session.visibleEntityIds;
  }

  /** Whether an entity's persisted annotations should be shown right now. */
  isEntityVisible(entityId: string): boolean {
    const visible = this.session.visibleEntityIds;
    return visible === null || visible.has(entityId);
  }

  /** Isolate a single entity, or — if it is already the sole isolated one — show all. */
  toggleEntityVisible(entityId: string): void {
    const visible = this.session.visibleEntityIds;
    const isolated = visible !== null && visible.size === 1 && visible.has(entityId);
    this.session.visibleEntityIds = isolated ? null : new Set([entityId]);
    // Keep the shared selection coherent with what's now displayed: a selection
    // pointing at an annotation this filter just hid would otherwise leave the
    // delete button/key acting on something no widget shows.
    const selected = this.session.annotations.selected;
    if (selected && selected.persisted && !this.isEntityVisible(selected.entityId)) {
      this.session.annotations.select(null);
    }
  }

  /** Reveal every entity's annotations (the "Show all" control). */
  showAllEntities(): void {
    this.session.visibleEntityIds = null;
  }

  // ─── Pending annotation (entity assignment) ───────────────────────────────

  /**
   * Register a freshly drawn box that is awaiting its entity choice. Any box
   * already pending is cancelled first so only one form is ever shown.
   */
  beginPendingAnnotation(pending: PendingAnnotation): void {
    this.pendingAnnotation?.onCancel();
    this.pendingAnnotation = pending;
  }

  /** Confirm the pending box with the user's entity choice. */
  confirmPendingAnnotation(choice: PendingEntityChoice): void {
    const pending = this.pendingAnnotation;
    this.pendingAnnotation = null;
    pending?.onConfirm(choice);
  }

  /** Discard the pending box. */
  cancelPendingAnnotation(): void {
    const pending = this.pendingAnnotation;
    this.pendingAnnotation = null;
    pending?.onCancel();
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

  /**
   * Delete an annotation (any kind) from the shared record: queues the backend
   * delete for a persisted one, or drops its not-yet-flushed creates, then
   * removes it from the collection. The parent entity is pruned server-side
   * when this was its last annotation. One path for 2D tools and 3D widgets.
   */
  deleteAnnotation(annotation: LocalAnnotation, widgetId: string): void {
    deleteLocalAnnotation(annotation, this.session.annotations, this.mutations, widgetId);
  }

  /** Queue an update, or replace the body of a pending update for the same resource+id. */
  upsertUpdateMutation(mutation: Extract<ResourceMutation, { op: "update" }>): void {
    this.mutations.upsertUpdate(mutation);
  }

  /** Merge a patch into a still-pending create's body for the given local annotation. */
  patchPendingCreateMutation(
    localAnnotationId: string,
    resource: string,
    patch: Record<string, unknown>,
  ): void {
    this.mutations.patchPendingCreate(localAnnotationId, resource, patch);
  }

  /** Drop every queued mutation referencing the given local bbox id. */
  dropMutationsForLocalAnnotation(localAnnotationId: string): ResourceMutation[] {
    return this.mutations.dropForLocalAnnotation(localAnnotationId);
  }

  /** Flush every queued mutation to the backend. */
  async flushSave(): Promise<void> {
    await this.mutations.flush();
    // Entity creates/prunes happen backend-side; refresh the local entity list
    // so the panel and picker reflect them. Skip if the flush errored.
    if (!this.mutations.saveError) await this.loader.reloadEntities();
  }

  // ─── Record loader forwarder ──────────────────────────────────────────────

  /** Load a record's widgets via the registered extensions' `addRecordSeed` hooks. */
  selectRecordInDataset(datasetId: string, recordId: string, viewport?: Viewport): Promise<void> {
    // A box drawn on the previous record must not carry over to the next one.
    this.pendingAnnotation = null;
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
      throw new Error(`Extension "${extensionName}" not found in registry`);
    }

    const options = config.addOptions?.() ?? {};
    // Wrap in $state so property mutations (e.g. storage.mode = "draw-bbox3d")
    // are tracked by Svelte's reactivity system inside widget components.
    const storage = $state({ ...(config.addStorage?.() ?? {}), ...(seedStorage ?? {}) });

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

  /** Toggle the visibility of a widget in the workspace. */
  toggleWidgetVisibility(id: string): void {
    const widget = this.widgets.find((w) => w.id === id);
    if (widget) {
      widget.hidden = !widget.hidden;
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
    this.pendingAnnotation = null;
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
