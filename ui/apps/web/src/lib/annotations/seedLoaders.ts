/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { BBox3DRow, BBoxRow, EntityRow } from "$lib/api/annotations.js";

import type { AnnotationKind, LocalAnnotation } from "./annotationCollection.svelte.js";
import { bboxSeedLoader } from "./kinds/2d/bbox/bboxSeedLoader.js";
import { bbox3dSeedLoader } from "./kinds/3d/bbox3d/bbox3dSeedLoader.js";

/**
 * The data-layer slice seed loaders may touch (a structural subset of
 * `RecordReadGateway`, kept here so kind modules never depend on the
 * workspace layer).
 */
export interface SeedListGateway {
  listBBoxes(
    datasetId: string,
    params: { recordId?: string; viewId?: string; limit?: number },
  ): Promise<BBoxRow[]>;
  listBBox3Ds(
    datasetId: string,
    params: { recordId?: string; viewId?: string; limit?: number },
  ): Promise<BBox3DRow[]>;
}

/** One displayed view of the loaded record, as claimed by an extension. */
export interface ViewInfo {
  /** Canonical view row id (e.g. the image row id). */
  id: string;
  /** Logical view name from the dataset schema (e.g. "CAM_FRONT"). */
  logicalName: string;
  /** Media dimensions, used to normalize pixel-space 2D coords; 0 if N/A. */
  width: number;
  height: number;
}

export interface SeedLoadContext {
  datasetId: string;
  recordId: string;
  gateway: SeedListGateway;
  /** Pre-fetched entity index for the record. */
  entitiesById: Map<string, EntityRow>;
  /**
   * Claimed views indexed by BOTH row id and logical name, so legacy rows
   * whose `view_id` held the camera name resolve to the same view.
   */
  views: Map<string, ViewInfo>;
}

/**
 * The missing half of the payload-builder symmetry: builders map local→REST,
 * seed loaders map REST→local. One per kind, next to the kind's builder.
 * `RecordLoader` runs every registered loader once per record and merges the
 * results into the shared collection — extensions never fetch annotations.
 */
export interface AnnotationSeedLoader {
  kind: AnnotationKind;
  load(ctx: SeedLoadContext): Promise<LocalAnnotation[]>;
}

/** Every seed loader; adding a kind means adding its import here. */
export const SEED_LOADERS: readonly AnnotationSeedLoader[] = [
  bboxSeedLoader,
  bbox3dSeedLoader,
];
