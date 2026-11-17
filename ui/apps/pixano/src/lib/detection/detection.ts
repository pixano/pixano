/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Detection in the image workspace: by class name, or "find more like these" from boxes already
 * on the image (the exemplars), with proposals rejected earlier sent back as negative exemplars.
 *
 * Everything here is pure. Boxes sent to and received from the model are pixel `[x1, y1, x2, y2]`
 * in the image's stored size (`width`, `height` of the view), the convention the smart
 * segmentation tool uses too; boxes stored in the dataset are normalised `xywh`.
 */

import type { Annotation, BBox, Entity } from "$lib/types/dataset";
import { BaseSchema } from "$lib/types/dataset";
import type { DetectionTaskInput, DetectionTaskOutput } from "$lib/types/inference";
import { isPendingReview } from "$lib/utils/reviewStatus";

/** A pixel box `[x1, y1, x2, y2]`. */
export type PixelBox = [number, number, number, number];

export interface DetectionImage {
  viewId: string;
  viewName: string;
  width: number;
  height: number;
}

export interface DetectionParams {
  /** The class to detect, also given to every proposal. Empty: no text. */
  className: string;
  boxThreshold: number;
  /** With exemplars, whether the class name is sent as text too (otherwise the prompt is visual). */
  classAsText: boolean;
}

export const DEFAULT_DETECTION_PARAMS: DetectionParams = {
  className: "",
  boxThreshold: 0.4,
  classAsText: true,
};

/** A proposal overlapping an existing box this much is the same object: SAM 3 finds its exemplars again. */
export const DUPLICATE_IOU = 0.5;

/**
 * A proposal this much inside another box, or holding another box this much, is the same object
 * too: SAM 3 returns parts of an object (a screw's head) and groups of objects as detections of
 * their own, which overlap little with the object's box by IoU.
 */
export const NESTED_FRACTION = 0.8;

export interface DetectionProposal {
  box: PixelBox;
  score: number;
}

/** A box of the dataset, in pixels; `null` for a degenerate one. */
export function bboxToPixelBox(bbox: BBox, width: number, height: number): PixelBox | null {
  const [a, b, c, d] = bbox.data.coords;
  if ([a, b, c, d].some((value) => typeof value !== "number" || !Number.isFinite(value)))
    return null;
  const sx = bbox.data.is_normalized ? width : 1;
  const sy = bbox.data.is_normalized ? height : 1;
  const xyxy: PixelBox =
    bbox.data.format === "xyxy"
      ? [a * sx, b * sy, c * sx, d * sy]
      : [a * sx, b * sy, (a + c) * sx, (b + d) * sy];
  const box = xyxy.map((value) => Math.round(value)) as PixelBox;
  return box[2] > box[0] && box[3] > box[1] ? box : null;
}

/** A pixel box as the dataset stores one: normalised `[x, y, width, height]`. */
export function pixelBoxToNormalizedXywh(box: PixelBox, width: number, height: number): number[] {
  const [x1, y1, x2, y2] = box;
  return [x1 / width, y1 / height, (x2 - x1) / width, (y2 - y1) / height];
}

function area(box: PixelBox): number {
  return (box[2] - box[0]) * (box[3] - box[1]);
}

function intersectionArea(left: PixelBox, right: PixelBox): number {
  const ix = Math.max(0, Math.min(left[2], right[2]) - Math.max(left[0], right[0]));
  const iy = Math.max(0, Math.min(left[3], right[3]) - Math.max(left[1], right[1]));
  return ix * iy;
}

/** How much of the smaller box lies inside the larger one: 1 when one holds the other. */
export function boxNesting(left: PixelBox, right: PixelBox): number {
  const smaller = Math.min(area(left), area(right));
  return smaller > 0 ? intersectionArea(left, right) / smaller : 0;
}

/** Whether two boxes are the same object: overlapping (`DUPLICATE_IOU`) or nested (`NESTED_FRACTION`). */
export function isSameObject(left: PixelBox, right: PixelBox): boolean {
  return boxIou(left, right) >= DUPLICATE_IOU || boxNesting(left, right) >= NESTED_FRACTION;
}

export function boxIou(left: PixelBox, right: PixelBox): number {
  const intersection = intersectionArea(left, right);
  const union = area(left) + area(right) - intersection;
  return union > 0 ? intersection / union : 0;
}

function sameClass(left: unknown, right: string): boolean {
  return typeof left === "string" && left.trim().toLowerCase() === right.trim().toLowerCase();
}

/** The boxes drawn on this view, whoever drew them. */
export function bboxesOfView(annotations: readonly Annotation[], viewName: string): BBox[] {
  return annotations.filter(
    (annotation): annotation is BBox =>
      annotation.table_info.base_schema === BaseSchema.BBox &&
      annotation.data.view_name === viewName,
  );
}

export interface ExemplarsInput {
  annotations: readonly Annotation[];
  entities: readonly Entity[];
  image: DetectionImage;
  /** The entity field holding the class; `null` when the dataset has none. */
  labelField: string | null;
  className: string;
}

/**
 * The exemplars: the boxes of this view whose object is of the class asked for. Without a label
 * field every box of the view is one. A proposal still to review is not: it is the model's guess,
 * not an example; once accepted, it becomes one.
 */
export function collectExemplars(input: ExemplarsInput): PixelBox[] {
  const { image, labelField, className } = input;
  if (labelField && !className.trim()) return [];
  const entityById = new Map(input.entities.map((entity) => [entity.id, entity]));
  const boxes: PixelBox[] = [];
  for (const bbox of bboxesOfView(input.annotations, image.viewName)) {
    if (isPendingReview(bbox)) continue;
    if (labelField) {
      const entity = entityById.get(bbox.data.entity_id);
      if (!entity || !sameClass(entity.data[labelField], className)) continue;
    }
    const box = bboxToPixelBox(bbox, image.width, image.height);
    if (box) boxes.push(box);
  }
  return boxes;
}

/** A proposal this session added to the view, remembered to recognise it once rejected. */
export interface SessionProposal {
  bboxId: string;
  viewName: string;
  box: PixelBox;
}

/**
 * The negatives: proposals this session added that are no longer on the image. Rejecting a
 * proposal deletes it (as does deleting it from the inspector), so a proposal gone is one a person
 * did not want. An accepted or edited proposal is still there and never counts.
 */
export function collectNegatives(
  proposals: readonly SessionProposal[],
  annotations: readonly Annotation[],
  viewName: string,
): PixelBox[] {
  const present = new Set(annotations.map((annotation) => annotation.id));
  return proposals
    .filter((proposal) => proposal.viewName === viewName && !present.has(proposal.bboxId))
    .map((proposal) => proposal.box);
}

export interface DetectionRequestInput {
  model: string;
  providerName: string;
  datasetId: string;
  image: DetectionImage;
  params: DetectionParams;
  exemplars: readonly PixelBox[];
  negatives: readonly PixelBox[];
  /** What the model reads (`supportsExemplars`, `supportsNegativeExemplars`). */
  readsExemplars: boolean;
  readsNegatives: boolean;
}

/**
 * The request, or `null` when there is nothing to ask: no class name and no exemplar the model
 * reads. Exemplars go only to a model that reads them, negatives only alongside exemplars.
 */
export function buildDetectionRequest(input: DetectionRequestInput): DetectionTaskInput | null {
  const className = input.params.className.trim();
  const exemplars = input.readsExemplars ? input.exemplars : [];
  const withExemplars = exemplars.length > 0;
  const negatives = withExemplars && input.readsNegatives ? input.negatives : [];
  const sendText = className.length > 0 && (!withExemplars || input.params.classAsText);
  if (!sendText && !withExemplars) return null;
  return {
    model: input.model,
    provider_name: input.providerName,
    dataset_id: input.datasetId,
    view_id: input.image.viewId,
    classes: sendText ? [className] : null,
    box_threshold: input.params.boxThreshold,
    exemplar_boxes: withExemplars ? exemplars.map((box) => [...box]) : null,
    negative_exemplar_boxes: negatives.length > 0 ? negatives.map((box) => [...box]) : null,
  };
}

export interface FilteredProposals {
  proposals: DetectionProposal[];
  /** Detections dropped as boxes the image already has, or parts or groups of them. */
  duplicates: number;
}

/**
 * The detections worth proposing: clamped to the image, non-degenerate, and not the same object
 * (`isSameObject`: overlapping or nested) as a box already on the view, nor as one another.
 * Highest score first.
 */
export function filterProposals(
  output: DetectionTaskOutput,
  existing: readonly PixelBox[],
  image: Pick<DetectionImage, "width" | "height">,
): FilteredProposals {
  const candidates = output.boxes
    .map((box, index) => ({ box, score: output.scores[index] ?? 0 }))
    .sort((left, right) => right.score - left.score);
  const kept: DetectionProposal[] = [];
  let duplicates = 0;
  for (const candidate of candidates) {
    const [x1, y1, x2, y2] = candidate.box;
    const box: PixelBox = [
      Math.max(0, Math.round(x1)),
      Math.max(0, Math.round(y1)),
      Math.min(image.width, Math.round(x2)),
      Math.min(image.height, Math.round(y2)),
    ];
    if (box[2] <= box[0] || box[3] <= box[1]) continue;
    const same = (other: PixelBox) => isSameObject(box, other);
    if (existing.some(same) || kept.some((proposal) => same(proposal.box))) {
      duplicates += 1;
      continue;
    }
    kept.push({ box, score: candidate.score });
  }
  return { proposals: kept, duplicates };
}
