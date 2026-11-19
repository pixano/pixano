/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { DatasetGateway, RecordReadGateway } from "./datasetGateway.js";
import { resolveRecordLayouts, toDatasetLayout } from "./datasetLayout.js";
import type { DatasetLayoutRepository } from "./datasetLayoutRepository.js";
import { measureGridViewport, type Viewport } from "./layoutPlanner.js";
import type { RecordWidgetSeed } from "./recordSeed.js";
import type { WorkspaceSession } from "./workspaceSession.svelte.js";
import {
  AnnotationCollection,
  type LocalAnnotation,
} from "$lib/annotations/annotationCollection.svelte.js";
import { loadEveryKind, type KindLoad, type ViewInfo } from "$lib/annotations/seedLoaders.js";
import type { EntityRow } from "$lib/api/annotations.js";
import type { WidgetInstance } from "$lib/extensions/types.js";
import type { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";

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
  /**
   * Source of the dataset's remembered widget arrangement. Read once per load
   * so a record opens laid out the way the user arranged an earlier one.
   */
  layoutRepository: DatasetLayoutRepository;
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
  private layoutRepository: DatasetLayoutRepository;
  // Incremented on every load() call. Each async continuation checks that it
  // still holds the current token before mutating workspace state, so a
  // rapid record-switch never lets a stale load overwrite the newer one.
  private loadToken = 0;
  /**
   * The views the current record opened with, kept so annotations can be
   * refetched without redoing the whole load: rebuilding widgets to undo an
   * edit would throw away the user's arrangement and tool state along with it.
   */
  private currentViews: Map<string, ViewInfo> = new Map();
  /**
   * The record `currentViews` were read for. From the start of a load until
   * its views are read, the session already names the new record while the
   * views are still the previous one's.
   */
  private viewsRecord: { datasetId: string; recordId: string } | null = null;
  /**
   * Incremented by every `reloadAnnotations` as it starts; `latestLanded` is
   * the number of the latest one whose rows were taken. Rows read before rows
   * already taken are older, and are dropped — whatever order the answers come
   * back in. A later read that never lands — called off, or failed for every
   * kind — does not stop an earlier one that still applies.
   */
  private reloadCount = 0;
  private latestLanded = 0;

  constructor(deps: RecordLoaderDeps) {
    this.workspace = deps.workspace;
    this.registry = deps.registry;
    this.gateway = deps.gateway;
    this.readGateway = deps.gateway;
    this.session = deps.session;
    this.layoutRepository = deps.layoutRepository;
  }

  /**
   * Refetch the current record's annotations and take them — the backend is
   * the last-saved state, so this is what "discard my edits" restores to, and
   * what a save reads back.
   *
   * Narrower than a full `load()` on purpose: the widgets, their arrangement
   * and their active tools are untouched, so undoing an edit does not feel like
   * reopening the record.
   *
   * The rows are merged with the work done while they were read
   * (`AnnotationCollection.takeRowsRead`): an annotation `holdsWork` names, and
   * every draft, stays as it is here; every other annotation becomes its row.
   * A kind whose rows could not be read keeps what it shows, and the failure
   * is reported: one table not answering does not empty that kind on screen.
   *
   * `stillWanted` is asked once the rows have arrived, before they are taken:
   * a caller whose reason to read may have lapsed during the fetch — a write
   * that landed meanwhile, which the rows may predate — calls it off.
   *
   * Nothing is read while the record is still loading: its rows would be
   * placed against the previous record's views, which places none of them.
   * Rows read before rows already taken are dropped (`latestLanded`).
   */
  async reloadAnnotations(
    opts: { stillWanted?: () => boolean; holdsWork?: (id: string) => boolean } = {},
  ): Promise<void> {
    const { stillWanted = () => true, holdsWork = () => false } = opts;
    const datasetId = this.session.datasetId;
    const recordId = this.session.recordId;
    if (!datasetId || !recordId) return;
    const views = this.viewsRecord;
    if (views?.datasetId !== datasetId || views.recordId !== recordId) return;
    // Observe (don't bump) the load token, as `reloadEntities` does: a record
    // switch mid-fetch must win over our stale result.
    const token = this.loadToken;
    const reload = ++this.reloadCount;
    try {
      const seedContext = {
        datasetId,
        recordId,
        gateway: this.readGateway,
        entitiesById: new Map(this.session.entities.map((e) => [e.id, e])),
        views: this.currentViews,
      };
      const loads = await loadEveryKind(seedContext);
      if (token !== this.loadToken || reload < this.latestLanded || !stillWanted()) return;
      reportUnread(loads, "refresh");
      const kindsRead = new Set(loads.filter((load) => load.read).map((load) => load.kind));
      // Read nothing at all: it failed, and must not drop an earlier read still on its way.
      if (kindsRead.size === 0) return;
      this.latestLanded = reload;
      this.session.annotations.takeRowsRead(annotationsRead(loads), holdsWork, kindsRead);
    } catch (err) {
      console.error("Failed to reload annotations:", err);
    }
  }

  /**
   * Refetch the current record's entities and refresh `session.entities`.
   * Called after a save so the entity list (right-panel list + picker) reflects
   * entities the flush created or the backend pruned, without a full reload,
   * and by Discard before it reads the annotations back, whose labels come
   * from this list.
   *
   * `stillWanted` is asked once the list has arrived, as for the annotations:
   * a read-back calls it off when a write has landed since it began — the list
   * may predate that write, and would take its entities off the panel and the
   * labels of the boxes moved onto them. Two lists read with no write between
   * them hold the same entities, so their order does not matter.
   */
  async reloadEntities(stillWanted: () => boolean = () => true): Promise<void> {
    const datasetId = this.session.datasetId;
    const recordId = this.session.recordId;
    if (!datasetId || !recordId) return;
    // Observe (don't bump) the load token: if a record switch starts while we're
    // fetching, discard our result so a stale list can't overwrite the newer
    // record's entities — same guard load() uses for its async writes.
    const token = this.loadToken;
    try {
      const entities = await this.readGateway.listEntities(datasetId, { recordId });
      if (token !== this.loadToken || !stillWanted()) return;
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
    // A newer load() was started while the views were resolving: the views it
    // reads are the ones a reload must use, not ours.
    if (token !== this.loadToken) return;
    this.currentViews = views;
    this.viewsRecord = { datasetId, recordId };
    const loads = await loadEveryKind(seedContext);

    // A newer load() was started while annotations were fetching.
    if (token !== this.loadToken) return;
    // A kind that could not be read seeds nothing rather than breaking the whole record.
    reportUnread(loads, "load");
    this.session.annotations = new AnnotationCollection(annotationsRead(loads));

    // Replay the arrangement the user built on an earlier record of this
    // dataset; views they never arranged fall back to automatic placement.
    const viewNames = claimed.map(({ viewName }) => viewName);
    const layouts = resolveRecordLayouts(
      viewNames,
      viewport,
      this.layoutRepository.load(datasetId),
    );

    // Remember the state the record opens in so the user can undo the moves
    // they make on it (`WorkspaceManager.restoreOpeningLayout`).
    this.session.openingLayout = toDatasetLayout(viewNames, layouts);

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
          // Keys this widget to its dataset view so a later arrangement of it
          // is remembered under a name the next record also has.
          viewName,
          layout: layouts[i].layout,
          hidden: layouts[i].hidden,
          options: seed.options,
          data: seed.data,
        },
        seed.storage as Record<string, unknown> | undefined,
      );
    }
  }
}

/** The annotations of every kind that was read. */
function annotationsRead(loads: readonly KindLoad[]): LocalAnnotation[] {
  return loads.flatMap((load) => (load.read ? load.annotations : []));
}

/** Say which kinds could not be read, on the loader's error channel. */
function reportUnread(loads: readonly KindLoad[], attempt: "load" | "refresh"): void {
  for (const load of loads) {
    if (load.read) continue;
    console.error(`Could not ${attempt} the ${load.kind} annotations:`, load.failure);
  }
}
