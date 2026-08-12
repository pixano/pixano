/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { httpDatasetGateway, type DatasetGateway } from "./datasetGateway.js";
import { snapshotDatasetLayout } from "./datasetLayout.js";
import {
  localStorageDatasetLayoutRepository,
  type DatasetLayoutRepository,
} from "./datasetLayoutRepository.js";
import { planFittedLayouts, type Viewport } from "./layoutPlanner.js";
import { MutationQueue } from "./mutationQueue.svelte.js";
import { RecordLoader } from "./recordLoader.js";
import { WorkspaceSession } from "./workspaceSession.svelte.js";
import type {
  AnnotationCollection,
  LocalAnnotation,
} from "$lib/annotations/annotationCollection.svelte.js";
import { deleteLocalAnnotation } from "$lib/annotations/payloadBuilders.js";
import type { LiveAnnotationDraft } from "$lib/annotations/scene/sceneContext.js";
import type {
  PendingAnnotation,
  PendingEntityChoice,
  ResourceMutation,
} from "$lib/annotations/types.js";
import type { EntityRow } from "$lib/api/annotations.js";
import type { WidgetInstance, WidgetLayout, WorkspacePreset } from "$lib/extensions/types.js";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import type { FieldInfo } from "$lib/types/dataset.js";

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
   * Bumped whenever widget layouts are rewritten programmatically rather than
   * by a grid gesture. `GridWorkspace` watches this counter alone to push the
   * new positions into GridStack — watching the layouts themselves would make
   * it re-apply on every drag and fight the user's own gesture.
   */
  layoutRevision = $state(0);

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
  private layoutRepository: DatasetLayoutRepository;

  constructor(
    registry: WidgetRegistry,
    gateway: DatasetGateway = httpDatasetGateway,
    layoutRepository: DatasetLayoutRepository = localStorageDatasetLayoutRepository,
  ) {
    this.registry = registry;
    this.session = new WorkspaceSession();
    this.layoutRepository = layoutRepository;

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
      layoutRepository,
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

  /** In-progress geometry of the active editing gesture, or null (see `WorkspaceSession`). */
  get liveDraft(): LiveAnnotationDraft | null {
    return this.session.liveDraft;
  }

  setLiveDraft(draft: LiveAnnotationDraft | null): void {
    this.session.liveDraft = draft;
  }

  // ─── Entity-driven annotation visibility ──────────────────────────────────
  // `null` = all entities visible (default). A set isolates the listed entities;
  // an empty set therefore hides every one of them.
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
    this.dropSelectionIfHidden();
  }

  /** Reveal every entity's annotations. */
  showAllEntities(): void {
    this.session.visibleEntityIds = null;
  }

  /** Hide every entity's annotations (an empty filter matches no entity). */
  hideAllEntities(): void {
    this.session.visibleEntityIds = new Set();
    this.dropSelectionIfHidden();
  }

  /**
   * The "Show all" control: reveal every entity, or — when everything is
   * already shown — hide every one of them.
   */
  toggleAllEntitiesVisible(): void {
    if (this.session.visibleEntityIds === null) this.hideAllEntities();
    else this.showAllEntities();
  }

  /**
   * Keep the shared selection coherent with what's displayed: a selection
   * pointing at an annotation a visibility change just hid would otherwise
   * leave the delete button/key acting on something no widget shows.
   */
  private dropSelectionIfHidden(): void {
    const selected = this.session.annotations.selected;
    if (selected && selected.persisted && !this.isEntityVisible(selected.entityId)) {
      this.session.annotations.select(null);
    }
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
      hidden: overrides?.hidden,
      viewName: overrides?.viewName,
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

  /**
   * Toggle the visibility of a widget in the workspace.
   *
   * Persisting is left to the grid: hiding compacts the neighbours and showing
   * re-places the widget in whatever slot is now free, so the arrangement the
   * user ends up seeing is only settled once GridStack has reacted.
   */
  toggleWidgetVisibility(id: string): void {
    const widget = this.widgets.find((w) => w.id === id);
    if (widget) {
      widget.hidden = !widget.hidden;
    }
  }

  // ─── Per-dataset layout preference ────────────────────────────────────────
  // Arranging the widgets on one record states how the user wants *this
  // dataset* laid out, so the arrangement is remembered and replayed when they
  // open the dataset's other records.
  //
  // Saving is deliberately explicit rather than a side effect of
  // `updateLayout`: the grid also writes layouts back when it places widgets
  // programmatically (mount, clamping, gap compaction after a hide), and
  // persisting those would freeze an automatic placement — computed for one
  // record's widget count — as if the user had chosen it. Only the call sites
  // that know a gesture happened save.

  /**
   * Remember how the user arranged the current dataset. No-op when no dataset
   * is open or no widget is view-backed, so clearing the workspace or moving a
   * palette widget never erases a stored arrangement.
   */
  saveDatasetLayout(): void {
    const datasetId = this.session.datasetId;
    if (!datasetId) return;

    const layout = snapshotDatasetLayout(this.widgets);
    if (layout) this.layoutRepository.save(datasetId, layout);
  }

  /**
   * Whether there is an opening arrangement to go back to. False until a record
   * has loaded, so the UI can disable the action instead of offering a no-op.
   */
  get hasOpeningLayout(): boolean {
    return this.session.openingLayout !== null;
  }

  /**
   * Put every widget back where the current record opened it, undoing the moves
   * made since, and remember that as the dataset's arrangement so what is shown
   * and what is stored never disagree.
   *
   * No-op before a record has loaded.
   */
  restoreOpeningLayout(): void {
    const opening = this.session.openingLayout;
    if (!opening) return;

    for (const widget of this.widgets) {
      const stored = widget.viewName ? opening.views[widget.viewName] : undefined;
      if (!stored) continue;
      // Spread over the current layout so the extension's minW/minH survive.
      widget.layout = { ...widget.layout, ...stored.layout };
      widget.hidden = stored.hidden;
    }

    this.layoutRevision++;
    this.saveDatasetLayout();
  }

  /**
   * Re-tile every widget so the whole set is visible and fits the viewport,
   * revealing any that were hidden. The escape hatch for a workspace that has
   * been arranged into a corner — or whose stored arrangement was built for a
   * screen the user no longer has.
   *
   * The viewport is passed in (rather than measured here) so the manager stays
   * environment-agnostic and unit-testable; callers read it from the live grid.
   */
  fitLayoutToViewport(viewport: Viewport): void {
    if (this.widgets.length === 0) return;

    const layouts = planFittedLayouts(this.widgets.length, viewport);
    this.widgets.forEach((widget, index) => {
      // Spread over the current layout so the extension's minW/minH survive.
      widget.layout = { ...widget.layout, ...layouts[index] };
      widget.hidden = false;
    });

    this.layoutRevision++;
    this.saveDatasetLayout();
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
    // The widgets it described are gone, so the arrangement they opened in no
    // longer means anything; the next load writes the new record's.
    this.session.openingLayout = null;
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
