/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** The rows that persist kept tracking-by-detection tracks (see `trackingByDetection`). */

import { nanoid } from "nanoid";

import { buildModelSourceFields } from "$lib/segmentation/maskNormalization";
import {
  applyKeyframeStride,
  splitTrackIntoSegments,
  type DetectionTrackFrame,
  type TrackingByDetectionRows,
  type TrackingByDetectionRowsInput,
} from "$lib/tracking/trackingByDetection";
import {
  BaseSchema,
  BBox,
  WorkspaceType,
  type Entity,
  type ItemFeature,
  type Tracklet,
} from "$lib/types/dataset";
import { ShapeType, type SaveTrackShape } from "$lib/types/shapeTypes";
import { nowTimestamp } from "$lib/utils/coreUtils";
import { getTable } from "$lib/utils/entityLookupUtils";
import {
  defineCreatedAnnotation,
  findOrCreateEntity,
  setTrackletOwnership,
} from "$lib/utils/entityOperations";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

function entityTableOf(manifest: WorkspaceManifest): string {
  return manifest.tablesByGroup.entities[0] ?? "entities";
}

function buildDetectionBBox(
  frame: DetectionTrackFrame,
  entity: Entity,
  trackletId: string,
  viewName: string,
  table: string,
  source: ReturnType<typeof buildModelSourceFields>,
): BBox {
  const now = nowTimestamp();
  const bbox = new BBox({
    id: nanoid(10),
    created_at: now,
    updated_at: now,
    table_info: { name: table, group: "annotations", base_schema: BaseSchema.BBox },
    data: {
      item_id: entity.data.item_id,
      view_name: viewName,
      view_id: frame.frameId,
      entity_id: entity.id,
      ...source,
      inference_metadata: {},
      frame_id: frame.frameId,
      frame_index: frame.frameIndex,
      tracklet_id: trackletId,
      entity_dynamic_state_id: "",
      coords: [...frame.coords],
      format: "xywh",
      is_normalized: true,
      confidence: frame.score,
    },
  });
  bbox.ui.datasetItemType = WorkspaceType.VIDEO;
  bbox.ui.frame_index = frame.frameIndex;
  return bbox;
}

/**
 * The rows that persist the kept tracks: one entity per track (its class in `labelField` when the
 * table has one), one tracklet per contiguous run, one bbox per kept frame with the model's score
 * as confidence and the model as provenance.
 */
export function buildTrackingByDetectionRows(
  input: TrackingByDetectionRowsInput,
): TrackingByDetectionRows {
  const entityTable = entityTableOf(input.manifest);
  const bboxTable = getTable(input.manifest, "annotations", BaseSchema.BBox);
  const entities: Entity[] = [];
  const tracklets: Tracklet[] = [];
  const bboxes: BBox[] = [];
  const classValues = new Set<string>();

  for (const track of input.tracks) {
    const source = buildModelSourceFields({
      modelName: input.source.modelName,
      providerName: input.source.providerName,
      metadata: { track_id: track.trackId, ...(track.className ? { class: track.className } : {}) },
    });
    const features: Record<string, ItemFeature> = {};
    if (input.labelField && track.className) {
      features[input.labelField] = { name: input.labelField, dtype: "str", value: track.className };
      classValues.add(track.className);
    }
    const entity = findOrCreateEntity(
      "new",
      { itemId: input.itemId },
      { [entityTable]: features },
      input.manifest,
    );
    entities.push(entity);

    for (const segment of splitTrackIntoSegments(track, input.params.maxGapFrames)) {
      const trackShape: SaveTrackShape = {
        type: ShapeType.track,
        status: "saving",
        viewRef: { id: "", name: input.viewName },
        itemId: input.itemId,
        imageWidth: input.frameSize.width,
        imageHeight: input.frameSize.height,
        attrs: { start_frame: segment.startFrame, end_frame: segment.endFrame },
      };
      const tracklet = defineCreatedAnnotation(
        entity,
        {},
        trackShape,
        trackShape.viewRef,
        input.manifest,
        true,
        segment.startFrame,
        { source },
      ) as Tracklet | undefined;
      if (!tracklet) continue;

      const segmentBoxes = applyKeyframeStride(segment, input.params.keyframeStride).map((frame) =>
        buildDetectionBBox(frame, entity, tracklet.id, input.viewName, bboxTable, source),
      );
      setTrackletOwnership(tracklet.id, segmentBoxes);
      tracklet.ui.childs = segmentBoxes;
      tracklets.push(tracklet);
      bboxes.push(...segmentBoxes);
    }
    entity.ui.childs = [
      ...tracklets.filter((t) => t.data.entity_id === entity.id),
      ...bboxes.filter((b) => b.data.entity_id === entity.id),
    ];
  }

  return { entities, tracklets, bboxes, classValues: [...classValues] };
}
