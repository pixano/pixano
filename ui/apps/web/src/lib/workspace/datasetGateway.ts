/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as api from "$lib/api";
import type { EntityRow, ListAnnotationsParams } from "$lib/api/annotations.js";
import type {
  CalibratedImageResponse,
  PointCloudResponse,
  TextResponse,
} from "$lib/api/restTypes.js";
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
  ): Promise<CalibratedImageResponse | null>;

  loadPointCloudByLogicalName(
    datasetId: string,
    recordId: string,
    logicalName: string,
  ): Promise<PointCloudResponse | null>;

  /**
   * A media read, not an annotation one — hence a name of its own rather than
   * the kind-agnostic `listAnnotations`. Reading a record's media is the
   * widget's business; reading its annotations is the seed loaders'.
   */
  loadTextByLogicalName(
    datasetId: string,
    recordId: string,
    logicalName: string,
  ): Promise<TextResponse | null>;

  /**
   * Read one annotation resource's rows for a record. Kind-agnostic: the caller
   * (a seed loader) supplies the resource name its payload builder owns, so
   * adding an annotation kind never widens this interface. Media reads stay
   * named per medium above — those are genuinely different endpoints.
   */
  listAnnotations<TRow>(
    datasetId: string,
    resource: string,
    params: ListAnnotationsParams,
  ): Promise<TRow[]>;
}

export interface MutationGateway {
  createEntity(datasetId: string, body: Record<string, unknown>): Promise<Record<string, unknown>>;

  deleteEntity(datasetId: string, id: string): Promise<void>;

  createAnnotation(
    datasetId: string,
    resource: string,
    body: Record<string, unknown>,
  ): Promise<Record<string, unknown>>;

  updateAnnotation(
    datasetId: string,
    resource: string,
    id: string,
    body: Record<string, unknown>,
  ): Promise<Record<string, unknown>>;

  deleteAnnotation(datasetId: string, resource: string, id: string): Promise<void>;
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
  loadPointCloudByLogicalName: (datasetId, recordId, logicalName) =>
    api.loadPointCloudByLogicalName(datasetId, recordId, logicalName),
  loadTextByLogicalName: (datasetId, recordId, logicalName) =>
    api.loadTextByLogicalName(datasetId, recordId, logicalName),
  listAnnotations: (datasetId, resource, params) =>
    api.listAnnotations(datasetId, resource, params),

  createEntity: (datasetId, body) => api.createEntity(datasetId, body),
  deleteEntity: (datasetId, id) => api.deleteEntity(datasetId, id),
  createAnnotation: (datasetId, resource, body) => api.createAnnotation(datasetId, resource, body),
  updateAnnotation: (datasetId, resource, id, body) =>
    api.updateAnnotation(datasetId, resource, id, body),
  deleteAnnotation: (datasetId, resource, id) => api.deleteAnnotation(datasetId, resource, id),
};
