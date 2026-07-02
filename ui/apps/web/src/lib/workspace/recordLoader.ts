/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { AnnotationCollection } from "$lib/annotations/annotationCollection.svelte.js";
import { SEED_LOADERS, type ViewInfo } from "$lib/annotations/seedLoaders.js";
import type { EntityRow } from "$lib/api/annotations.js";
import type { WidgetInstance } from "$lib/extensions/types.js";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";

import type { DatasetGateway, RecordReadGateway } from "./datasetGateway.js";
import { measureGridViewport, planViewportLayouts, type Viewport } from "./layoutPlanner.js";
import type { RecordWidgetSeed } from "./recordSeed.js";
import type { WorkspaceSession } from "./workspaceSession.svelte.js";

/**
 * Minimal write surface the loader needs. Defined as an interface so
 * tests (and any future alternative loader) can provide a stand-in
 * without coupling to the full `WorkspaceManager` class.
 */
export interface WidgetSink {
  addWidget(
    extensionName: string,
    overrides?: Partial<WidgetInstance>,
    seedStorage?: Record<string, unknown>,
  ): WidgetInstance | null;
}

export interface RecordLoaderDeps {
  workspace: WidgetSink;
  registry: WidgetRegistry;
  /**
   * The combined `DatasetGateway` is accepted so it can be passed through
   * to each extension's `addRecordSeed` via `SeedContext.gateway`. The
   * loader itself only ever calls `RecordReadGateway` methods on it.
   */
  gateway: DatasetGateway;
  session: WorkspaceSession;
}

/**
 * Materializes the widget set for a (dataset, record) selection by
 * delegating per-view materialization to each extension's `addRecordSeed`.
 */
export class RecordLoader {
  private workspace: WidgetSink;
  private registry: WidgetRegistry;
  private gateway: DatasetGateway;
  private readGateway: RecordReadGateway;
  private session: WorkspaceSession;
  // Incremented on every load() call. Each async continuation checks that it
  // still holds the current token before mutating workspace state, so a
  // rapid record-switch never lets a stale load overwrite the newer one.
  private loadToken = 0;

  constructor(deps: RecordLoaderDeps) {
    this.workspace = deps.workspace;
    this.registry = deps.registry;
    this.gateway = deps.gateway;
    this.readGateway = deps.gateway;
    this.session = deps.session;
  }

  /**
   * Refetch the current record's entities and refresh `session.entities`.
   * Called after a save so the entity list (right-panel list + picker) reflects
   * entities the flush created or the backend pruned, without a full reload.
   */
  async reloadEntities(): Promise<void> {
    const datasetId = this.session.datasetId;
    const recordId = this.session.recordId;
    if (!datasetId || !recordId) return;
    // Observe (don't bump) the load token: if a record switch starts while we're
    // fetching, discard our result so a stale list can't overwrite the newer
    // record's entities — same guard load() uses for its async writes.
    const token = this.loadToken;
    try {
      const entities = await this.readGateway.listEntities(datasetId, { recordId });
      if (token !== this.loadToken) return;
      this.session.entities = entities;
    } catch (err) {
      console.error("Failed to reload entities:", err);
    }
  }

  async load(
    datasetId: string,
    recordId: string,
    viewport: Viewport = measureGridViewport(),
  ): Promise<void> {
    const token = ++this.loadToken;

    // Track the active selection so queued mutations (`MutationQueue.flush`,
    // entity creation, etc.) hit the right dataset and so the UI reflects
    // it. Set *before* the awaits below so a mid-load `clearWorkspace`
    // still leaves a consistent session.
    this.session.datasetId = datasetId;
    this.session.recordId = recordId;
    this.session.entities = [];
    this.session.entitySchemaName = null;
    this.session.entitySchemaFields = null;
    this.session.annotations = new AnnotationCollection();
    this.session.visibleEntityIds = null;

    // Kick off both the dataset metadata fetch and the entities listing in
    // parallel — they don't depend on each other and the entities call is
    // record-scoped, not view-scoped.
    const [dataset, entityRows] = await Promise.all([
      this.readGateway.getDataset(datasetId),
      this.readGateway.listEntities(datasetId, { recordId }).catch((err: unknown) => {
        console.error("Failed to load entities:", err);
        return [] as EntityRow[];
      }),
    ]);

    // A newer load() was started while we were awaiting — discard our results.
    if (token !== this.loadToken) return;

    // Entities are record-scoped (a bbox points at an entity via
    // entity_id, and that entity row lives in the dataset's single
    // entities table), so we look them up once and hand each extension's
    // seed the same map.
    const entitiesById = new Map<string, EntityRow>();
    for (const entity of entityRows) entitiesById.set(entity.id, entity);

    // Expose entities and their schema (name + fields) to consumers (e.g. the
    // right panel's entity form, which generates inputs from the fields).
    this.session.entities = entityRows;
    this.session.entitySchemaName = dataset.schema.schemas?.["entities"]?.schema ?? null;
    this.session.entitySchemaFields = dataset.schema.schemas?.["entities"]?.fields ?? null;

    const candidates = Object.entries(dataset.info.views ?? {});
    const extensions = this.registry.getAll();

    type ResolvedSeed = {
      extensionName: string;
      viewName: string;
      seed: RecordWidgetSeed;
    };

    // For each view, ask every extension (in registry priority order)
    // whether it claims it; the first non-null seed wins. Views are
    // resolved in parallel: a record with N sensors costs roughly one
    // round-trip's worth of latency, not N. Inside one view the
    // extension scan is sequential, but extensions are few and the first
    // match returns immediately.
    const resolved = await Promise.all(
      candidates.map(async ([viewName, viewDef]): Promise<ResolvedSeed | null> => {
        for (const ext of extensions) {
          if (!ext.addRecordSeed) continue;
          const seed = await ext.addRecordSeed({
            datasetId,
            recordId,
            viewName,
            viewDef,
            entitiesById,
            gateway: this.gateway,
          });
          if (seed) {
            return { extensionName: ext.name, viewName, seed };
          }
        }
        return null;
      }),
    );

    const claimed = resolved.filter((s): s is ResolvedSeed => s !== null);

    if (claimed.length === 0) {
      throw new Error(`No renderable views for record "${recordId}" in dataset "${datasetId}".`);
    }

    // Index every claimed view by row id AND logical name (legacy rows used
    // the camera name as view_id), then run each kind's seed loader once for
    // the whole record. REST→local mapping lives in the kind modules — the
    // loader only orchestrates (docs/ARCHITECTURE_TOOLING.md, seed-loader registry).
    const views = new Map<string, ViewInfo>();
    for (const { seed } of claimed) {
      if (!seed.view) continue;
      if (seed.view.id) views.set(seed.view.id, seed.view);
      views.set(seed.view.logicalName, seed.view);
    }
    const seedContext = {
      datasetId,
      recordId,
      gateway: this.readGateway,
      entitiesById,
      views,
    };
    const loaded = await Promise.all(SEED_LOADERS.map((loader) => loader.load(seedContext)));

    // A newer load() was started while annotations were fetching.
    if (token !== this.loadToken) return;
    this.session.annotations = new AnnotationCollection(loaded.flat());

    const layouts = planViewportLayouts(claimed.length, viewport);

    // Materialize widgets in the dataset's declared view order so on-screen
    // placement matches the schema (e.g. cameras left-to-right, lidar
    // after); the parallel resolution above only races fetches, not
    // ordering.
    for (let i = 0; i < claimed.length; i++) {
      const { extensionName, viewName, seed } = claimed[i];
      this.workspace.addWidget(
        extensionName,
        {
          extensionName,
          title: seed.title ?? viewName,
          layout: layouts[i],
          options: seed.options,
          data: seed.data,
        },
        seed.storage as Record<string, unknown> | undefined,
      );
    }
  }
}
