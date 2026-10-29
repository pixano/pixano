/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { AnnotationKind, LocalAnnotation } from "./annotationCollection.svelte.js";
import { bboxSeedLoader } from "./kinds/2d/bbox/bboxSeedLoader.js";
import { classificationSeedLoader } from "./kinds/2d/classification/classificationSeedLoader.js";
import { keypointsSeedLoader } from "./kinds/2d/keypoints/keypointsSeedLoader.js";
import { maskSeedLoader } from "./kinds/2d/mask/maskSeedLoader.js";
import { multiPathSeedLoader } from "./kinds/2d/multi-path/multiPathSeedLoader.js";
import { bbox3dSeedLoader } from "./kinds/3d/bbox3d/bbox3dSeedLoader.js";
import type { EntityRow, ListAnnotationsParams } from "$lib/api/annotations.js";

/**
 * The data-layer slice seed loaders may touch (a structural subset of
 * `RecordReadGateway`, kept here so kind modules never depend on the
 * workspace layer).
 *
 * Deliberately kind-agnostic: a loader passes the `resource` its own payload
 * builder owns, so a new annotation kind adds nothing to this interface.
 */
export interface SeedListGateway {
  listAnnotations<TRow>(
    datasetId: string,
    resource: string,
    params: ListAnnotationsParams,
  ): Promise<TRow[]>;
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
 * `RecordLoader` runs every registered loader once per record (`loadEveryKind`)
 * and merges the results into the shared collection — extensions never fetch
 * annotations.
 *
 * `load` rejects when the kind's rows could not be read, and never resolves to
 * an empty list then: what a failed read means is the caller's to decide.
 */
export interface AnnotationSeedLoader {
  kind: AnnotationKind;
  load(ctx: SeedLoadContext): Promise<LocalAnnotation[]>;
}

/** Every seed loader; adding a kind means adding its import here. */
export const SEED_LOADERS: readonly AnnotationSeedLoader[] = [
  bboxSeedLoader,
  bbox3dSeedLoader,
  maskSeedLoader,
  keypointsSeedLoader,
  multiPathSeedLoader,
  classificationSeedLoader,
];

/**
 * What one kind's seed loader got: the annotations it built from the record's
 * rows, or the failure that kept it from reading them.
 *
 * "Read nothing" and "could not read" stay apart. The first says the record
 * holds no annotation of the kind; the second says nothing about what it
 * holds, and a reload that took one for the other took every annotation of
 * the kind off the screen after one failed request.
 */
export type KindLoad =
  | { kind: AnnotationKind; read: true; annotations: LocalAnnotation[] }
  | { kind: AnnotationKind; read: false; failure: unknown };

/**
 * Run every registered seed loader once against the record, each failure kept
 * to its own kind: a table that does not answer leaves the others read.
 */
export function loadEveryKind(ctx: SeedLoadContext): Promise<KindLoad[]> {
  return Promise.all(SEED_LOADERS.map((loader) => loadKind(loader, ctx)));
}

async function loadKind(loader: AnnotationSeedLoader, ctx: SeedLoadContext): Promise<KindLoad> {
  try {
    return { kind: loader.kind, read: true, annotations: await loader.load(ctx) };
  } catch (failure) {
    return { kind: loader.kind, read: false, failure };
  }
}
