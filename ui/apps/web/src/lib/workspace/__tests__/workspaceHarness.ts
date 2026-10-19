/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Component } from "svelte";

import type { DatasetGateway } from "../datasetGateway.js";
import { WorkspaceManager } from "../workspaceManager.svelte.js";
import { makeLayoutRepository } from "./fakeDatasetLayoutRepository.js";
import type { BBoxGeometry } from "$lib/annotations/annotationCollection.svelte.js";
import { BBOX_RESOURCE } from "$lib/annotations/kinds/2d/bbox/bboxPayloadBuilder.js";
import { commitGeometryEdit } from "$lib/annotations/payloadBuilders.js";
import type { SeamContext } from "$lib/annotations/scene/sceneContext.js";
import type { EntityRow } from "$lib/api/annotations.js";
import { ApiError } from "$lib/api/apiClient.js";
import { ENTITY_RESOURCE } from "$lib/api/resourceNames.js";
import type { CalibratedImageResponse } from "$lib/api/restTypes.js";
import { buildSeam } from "$lib/components/widgets/sceneSeam.js";
import type { WidgetComponentProps, WidgetExtensionConfig } from "$lib/extensions/types.js";
import { WidgetRegistry } from "$lib/extensions/WidgetRegistry.js";
import { DatasetInfo, type Dataset } from "$lib/types/dataset";

/**
 * A recording stand-in for the backend that the workspace suites run the real
 * workspace against: the real manager, queue, loader, seed loaders and commit
 * helpers, with only the HTTP edge replaced. The rows it serves are the ones a
 * test states; what the server would store after a write is, when a test needs
 * it, written by that test in `onWrite`, or by `serveLikeTheApi`, which stores
 * each write as the server does.
 */

export const DATASET_ID = "ds-1";
/** The one image view every record of the fake dataset declares. */
export const VIEW_NAME = "cam";
const IMAGE_SIZE = 100;
/** The status the server refuses a request with. */
const HTTP_BAD_REQUEST = 400;
/** The status the server answers a write of a row that is not there with. */
const HTTP_NOT_FOUND = 404;
export const VIEWPORT = { width: 1600, height: 900 };

/** The image row id of a record's view — what its annotations' `view_id` points at. */
export const viewIdOf = (recordId: string) => `${recordId}-${VIEW_NAME}`;

/** One write the workspace sent, in the order it sent them. */
export type RecordedWrite =
  | { op: "create"; resource: string; body: Record<string, unknown> }
  | { op: "update"; resource: string; id: string; body: Record<string, unknown> }
  | { op: "delete"; resource: string; id: string };

export type Row = Record<string, unknown> & { id: string; record_id: string; entity_id: string };

export interface FakeBackend {
  /** Annotation rows per record, then per resource. */
  records: Record<string, Record<string, Row[]>>;
  entities: EntityRow[];
  writes: RecordedWrite[];
  /** Every gateway call, writes and reads alike, so a test can check their order. */
  log: string[];
  /** What the server stores on a write, when a test needs it to change the rows. */
  onWrite?: (write: RecordedWrite) => void;
  /** Make the next writes fail, as an unreachable backend would: nothing is stored. */
  failWrites?: Error;
  /**
   * Store the next writes, then fail them with this error: the answer was lost
   * on its way back, after the server had stored the write.
   */
  loseAnswers?: Error;
  /**
   * Hold every write until the test releases it — a save still in flight. Read
   * as each write starts, so a test can hold one write and let the others pass.
   */
  holdWrites?: Promise<void>;
}

const stubComponent = (() => null) as unknown as Component<WidgetComponentProps>;

function makeDataset(): Dataset {
  const info = new DatasetInfo({
    id: DATASET_ID,
    name: "Test Dataset",
    description: "",
    num_items: 1,
    size: "",
    preview: "",
    workspace: "image",
  });
  info.views = { [VIEW_NAME]: { base: "Image" } };
  return {
    id: DATASET_ID,
    path: "",
    previews_path: "",
    media_dir: "",
    thumbnail: "",
    schema: {} as never,
    featureValues: {},
    info,
  };
}

/** An image extension that claims the record's one view, as the real one does. */
function makeRegistry(): WidgetRegistry {
  const registry = new WidgetRegistry();
  const imageExt: WidgetExtensionConfig = {
    name: "image",
    label: "Image",
    icon: "image",
    priority: 100,
    defaultLayout: { x: 0, y: 0, w: 3, h: 3 },
    component: stubComponent,
    addStorage: () => ({ activeToolId: "select" }),
    addRecordSeed: async ({ datasetId, recordId, viewName, gateway }) => {
      const image = await gateway.loadImageByLogicalName(datasetId, recordId, viewName);
      if (!image) return null;
      return {
        title: viewName,
        options: { datasetId, recordId, viewId: image.id, viewName },
        data: {},
        view: { id: image.id, logicalName: viewName, width: IMAGE_SIZE, height: IMAGE_SIZE },
      };
    },
  };
  registry.register({ config: imageExt } as never);
  return registry;
}

/**
 * What crosses the wire: a plain copy. Bodies leave the queue as reactive
 * proxies, which `structuredClone` refuses — a JSON round trip is what HTTP does.
 */
function jsonCopy<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

async function recordWrite(backend: FakeBackend, write: RecordedWrite): Promise<void> {
  backend.log.push(`${write.op} ${write.resource}`);
  await backend.holdWrites;
  if (backend.failWrites) throw backend.failWrites;
  // What the server refuses (`onWrite` throws) is not among the writes it stored.
  backend.onWrite?.(write);
  backend.writes.push(write);
  if (backend.loseAnswers) throw backend.loseAnswers;
}

export function makeBackend(records: FakeBackend["records"], entities: EntityRow[] = []) {
  const backend: FakeBackend = {
    records,
    entities,
    writes: [],
    log: [],
  };
  const gateway: DatasetGateway = {
    getDataset: () => {
      backend.log.push("getDataset");
      return Promise.resolve(makeDataset());
    },
    listEntities: (_datasetId, { recordId }) => {
      backend.log.push("listEntities");
      return Promise.resolve(jsonCopy(backend.entities.filter((e) => e.record_id === recordId)));
    },
    loadImageByLogicalName: (_datasetId, recordId) =>
      Promise.resolve({
        id: viewIdOf(recordId),
        src: "",
        width: IMAGE_SIZE,
        height: IMAGE_SIZE,
      } as unknown as CalibratedImageResponse),
    listRecordImages: () => Promise.resolve([]),
    loadPointCloudByLogicalName: () => Promise.resolve(null),
    loadTextByLogicalName: () => Promise.resolve(null),
    listAnnotations: <TRow>(
      _datasetId: string,
      resource: string,
      params: { recordId?: string },
    ): Promise<TRow[]> => {
      backend.log.push(`list ${resource}`);
      // A copy, as a fresh HTTP response would be: the loader must not share
      // objects with the "server".
      return Promise.resolve(
        jsonCopy(backend.records[params.recordId ?? ""]?.[resource] ?? []) as TRow[],
      );
    },
    createEntity: async (_datasetId, body) => {
      await recordWrite(backend, { op: "create", resource: "entities", body: jsonCopy(body) });
      return {};
    },
    deleteEntity: async (_datasetId, id) => {
      await recordWrite(backend, { op: "delete", resource: "entities", id });
    },
    createAnnotation: async (_datasetId, resource, body) => {
      await recordWrite(backend, { op: "create", resource, body: jsonCopy(body) });
      return {};
    },
    updateAnnotation: async (_datasetId, resource, id, body) => {
      await recordWrite(backend, { op: "update", resource, id, body: jsonCopy(body) });
      return {};
    },
    deleteAnnotation: async (_datasetId, resource, id) => {
      await recordWrite(backend, { op: "delete", resource, id });
    },
  };
  return { backend, gateway };
}

/** The answer the server gives a write it refuses: a 400, with its reason. */
export function refusal(detail: string): ApiError {
  return new ApiError("Request refused", HTTP_BAD_REQUEST, detail);
}

/**
 * Make the fake backend store each write as the server does
 * (src/pixano/api/service.py), for tests about what the dataset ends up
 * holding. The annotation writes are the record's:
 *
 * - an entity create is stored once, whatever the retries (its id is the client's);
 * - an annotation create or update naming an entity that does not exist is
 *   refused ("Foreign key violation"), as the server's reference check does;
 * - an update stores the body as sent;
 * - an update of a row that is not there is refused with a 404;
 * - an annotation update or delete that lets go of an entity prunes it when no
 *   annotation names it any more (`?prune_orphan_entity=true`);
 * - a delete of what is not there is done: the HTTP layer reads its 404 so.
 */
export function serveLikeTheApi(backend: FakeBackend, recordId: string): void {
  const rowsOf = (resource: string) => ((backend.records[recordId] ??= {})[resource] ??= []);
  const entityExists = (id: unknown) => backend.entities.some((entity) => entity.id === id);
  const annotationsName = (entityId: string) =>
    Object.values(backend.records).some((resources) =>
      Object.values(resources).some((rows) => rows.some((row) => row.entity_id === entityId)),
    );
  const removeEntity = (entityId: string) => {
    backend.entities = backend.entities.filter((entity) => entity.id !== entityId);
  };
  const prune = (entityId: string) => {
    if (!annotationsName(entityId)) removeEntity(entityId);
  };
  const checkReference = (entityId: unknown) => {
    if (!entityExists(entityId)) {
      throw refusal(`Foreign key violation: entity_id=${String(entityId)}`);
    }
  };
  backend.onWrite = (write) => {
    if (write.resource === ENTITY_RESOURCE) {
      if (write.op === "create" && !entityExists(write.body.id)) {
        backend.entities.push({ ...(write.body as EntityRow) });
      }
      return;
    }
    const rows = rowsOf(write.resource);
    if (write.op === "create") {
      checkReference(write.body.entity_id);
      if (!rows.some((row) => row.id === write.body.id)) rows.push({ ...(write.body as Row) });
      return;
    }
    const row = rows.find((candidate) => candidate.id === write.id);
    if (write.op === "delete") {
      if (!row) return;
      rows.splice(rows.indexOf(row), 1);
      prune(row.entity_id);
      return;
    }
    if (!row) {
      throw new ApiError("Request refused", HTTP_NOT_FOUND, `Resource '${write.id}' not found`);
    }
    const previousEntity = row.entity_id;
    const edit = write.body;
    if (edit.entity_id !== undefined && edit.entity_id !== previousEntity) {
      checkReference(edit.entity_id);
    }
    Object.assign(row, edit);
    if (row.entity_id !== previousEntity) prune(previousEntity);
  };
}

/** A promise the test settles when it chooses — a request held on the wire. */
export function deferred<T = void>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => (resolve = r));
  return { promise, resolve };
}

/** The real manager over the fake backend, with the record already open. */
export async function openManager(
  records: FakeBackend["records"],
  opts: { recordId?: string; entities?: EntityRow[] } = {},
) {
  const { backend, gateway } = makeBackend(records, opts.entities);
  const manager = new WorkspaceManager(makeRegistry(), gateway, makeLayoutRepository());
  const recordId = opts.recordId ?? Object.keys(records)[0];
  await manager.openRecord(DATASET_ID, recordId, VIEWPORT);
  return { manager, backend, recordId };
}

/** The seam an image widget of this record builds — what its tools commit through. */
export function widgetSeam(manager: WorkspaceManager, widgetId = "image-widget"): SeamContext {
  const recordId = manager.recordId ?? "";
  return buildSeam(manager, {
    widgetId,
    buildContext: { datasetId: DATASET_ID, recordId, viewId: viewIdOf(recordId) },
    storage: { activeToolId: "select" },
  });
}

// ─── Rows ────────────────────────────────────────────────────────────────────

/** A box a person drew in the interface. */
export function humanBox(recordId: string, id: string): Row {
  return {
    id,
    record_id: recordId,
    entity_id: `ent-${id}`,
    view_id: viewIdOf(recordId),
    coords: [0.1, 0.1, 0.2, 0.2],
    format: "xywh",
    is_normalized: true,
    confidence: 1,
    source_type: "other",
    source_name: "Pixano",
    source_metadata: "{}",
  };
}

export function entityOf(recordId: string, id: string, fields: Record<string, unknown> = {}) {
  return { id, record_id: recordId, ...fields } as EntityRow;
}

// ─── Box suites ──────────────────────────────────────────────────────────────

/** The record the box suites open. */
export const REC = "rec-1";
/** Where `humanBox` puts a box — what the dataset holds. */
export const STORED: BBoxGeometry = [0.1, 0.1, 0.2, 0.2];
/** Where `drag` moves a box by default. */
export const MOVED: BBoxGeometry = [0.3, 0.3, 0.2, 0.2];

/** The real manager with record `REC` open on these boxes, and its image widget's seam. */
export async function openWithBoxes(...rows: Row[]) {
  const opened = await openManager({ [REC]: { [BBOX_RESOURCE]: rows } });
  return { ...opened, seam: widgetSeam(opened.manager) };
}

/** The geometry an annotation shows. */
export function geometryOf(manager: WorkspaceManager, id: string): unknown {
  return manager.annotations.find(id)?.geometry;
}

/** Drag a box to a new place, as the 2D editor does at the end of a gesture. */
export function drag(seam: SeamContext, id: string, geometry: BBoxGeometry = MOVED): void {
  commitGeometryEdit(seam, id, geometry);
}

/** The updates the workspace sent, in the order it sent them. */
export function updatesSent(backend: FakeBackend) {
  return backend.writes.filter((w) => w.op === "update");
}
