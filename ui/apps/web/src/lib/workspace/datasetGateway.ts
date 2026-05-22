/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as api from "$lib/api";
import type {
  BBox3DRow,
  BBoxRow,
  EntityRow,
} from "$lib/api/annotations.js";
import type { ImageResponse, PointCloudResponse } from "$lib/api/restTypes.js";
import type { Dataset } from "$lib/types/dataset";

/**
 * Explicit contract for the data-layer dependencies the workspace needs.
 *
 * Split along its actual seam:
 *
 *  - `RecordReadGateway` — read-only methods used by `RecordLoader` and
 *    each extension's `addRecordSeed`.
 *  - `MutationGateway` — write methods used by `MutationQueue.flush()`.
 *
 * Each consumer accepts only the slice it needs. The combined
 * `DatasetGateway` is the wiring type accepted by `WorkspaceManager` and
 * passed through `SeedContext.gateway` so a single instance can serve
 * both sub-services and every extension.
 */

export interface RecordReadGateway {
  getDataset(datasetId: string): Promise<Dataset>;

  listEntities(
    datasetId: string,
    params: { recordId?: string; limit?: number },
  ): Promise<EntityRow[]>;

  loadImageByLogicalName(
    datasetId: string,
    recordId: string,
    logicalName: string,
  ): Promise<ImageResponse | null>;

  listBBoxes(
    datasetId: string,
    params: { recordId?: string; viewId?: string; limit?: number },
  ): Promise<BBoxRow[]>;

  loadPointCloudByLogicalName(
    datasetId: string,
    recordId: string,
    logicalName: string,
  ): Promise<PointCloudResponse | null>;

  listBBox3Ds(
    datasetId: string,
    params: { recordId?: string; viewId?: string; limit?: number },
  ): Promise<BBox3DRow[]>;
}

export interface MutationGateway {
  createEntity(
    datasetId: string,
    body: Record<string, unknown>,
  ): Promise<Record<string, unknown>>;

  createBBox(
    datasetId: string,
    body: Record<string, unknown>,
  ): Promise<Record<string, unknown>>;

  updateBBox(
    datasetId: string,
    id: string,
    body: Record<string, unknown>,
  ): Promise<Record<string, unknown>>;

  deleteBBox(datasetId: string, id: string): Promise<void>;

  deleteEntity(datasetId: string, id: string): Promise<void>;
}

/** Combined read+write gateway used by the workspace facade. */
export type DatasetGateway = RecordReadGateway & MutationGateway;

/**
 * Production gateway: thin pass-through to the live HTTP `$lib/api` module.
 * This is the *only* place in the workspace layer that imports `$lib/api`
 * directly — everything else goes through the gateway interfaces.
 */
export const httpDatasetGateway: DatasetGateway = {
  getDataset: (datasetId) => api.getDataset(datasetId),
  listEntities: (datasetId, params) => api.listEntities(datasetId, params),
  loadImageByLogicalName: (datasetId, recordId, logicalName) =>
    api.loadImageByLogicalName(datasetId, recordId, logicalName),
  listBBoxes: (datasetId, params) => api.listBBoxes(datasetId, params),
  loadPointCloudByLogicalName: (datasetId, recordId, logicalName) =>
    api.loadPointCloudByLogicalName(datasetId, recordId, logicalName),
  listBBox3Ds: (datasetId, params) => api.listBBox3Ds(datasetId, params),

  createEntity: (datasetId, body) => api.createEntity(datasetId, body),
  createBBox: (datasetId, body) => api.createBBox(datasetId, body),
  updateBBox: (datasetId, id, body) => api.updateBBox(datasetId, id, body),
  deleteBBox: (datasetId, id) => api.deleteBBox(datasetId, id),
  deleteEntity: (datasetId, id) => api.deleteEntity(datasetId, id),
};
