/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import {
  Annotation,
  BaseSchema,
  BBox,
  Entity,
  Keypoints,
  Mask,
  SaveShapeType,
  TextSpan,
  Tracklet,
  WorkspaceType,
  type BBoxType,
  type DatasetSchema,
  type ItemFeature,
  type MaskType,
  type Reference,
  type SaveShape,
} from "@pixano/core";

import { sourcesStore } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { getPixanoSource } from "./getPixanoSource";
import { getTable } from "./getTable";

export const defineCreatedObject = (
  entity: Entity,
  features: Record<string, Record<string, ItemFeature>>,
  shape: SaveShape,
  viewRef: Reference,
  dataset_schema: DatasetSchema,
  isVideo: boolean,
  currentFrameIndex: number,
): Annotation | undefined => {
  const now = new Date(Date.now()).toISOString().replace(/Z$/, "+00:00");
  const baseAnn = {
    id: nanoid(10),
    created_at: now,
    updated_at: now,
  };
  const pixSource = getPixanoSource(sourcesStore);
  const baseData = {
    item_ref: entity.data.item_ref,
    view_ref: viewRef,
    entity_ref: { name: entity.table_info.name, id: entity.id },
    source_ref: { name: pixSource.table_info.name, id: pixSource.id },
    inference_metadata: {},
  };
  let newObject: Annotation | undefined = undefined;

  if (shape.type === SaveShapeType.bbox) {
    const { x, y, width, height } = shape.attrs;
    const coords = [
      x / shape.imageWidth,
      y / shape.imageHeight,
      width / shape.imageWidth,
      height / shape.imageHeight,
    ];

    const bbox: BBoxType = {
      coords,
      format: "xywh",
      is_normalized: true,
      confidence: 1,
    };

    const table = getTable(dataset_schema, "annotations", BaseSchema.BBox);
    newObject = new BBox({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.BBox },
      data: { ...baseData, ...bbox },
    });
  } else if (shape.type === SaveShapeType.mask) {
    const mask: MaskType = {
      counts: shape.rle.counts,
      size: shape.rle.size,
    };

    const table = getTable(dataset_schema, "annotations", BaseSchema.Mask);
    newObject = new Mask({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.Mask },
      data: { ...baseData, ...mask },
    });
  } else if (shape.type === SaveShapeType.keypoints) {
    const coords = [];
    const states = [];

    for (const vertex of shape.keypoints.vertices) {
      coords.push(vertex.x / shape.imageWidth);
      coords.push(vertex.y / shape.imageHeight);
      states.push(vertex.features.state ? vertex.features.state : "visible");
    }

    const keypoints = {
      template_id: shape.keypoints.template_id,
      coords,
      states,
    };

    const table = getTable(dataset_schema, "annotations", BaseSchema.Keypoints);

    newObject = new Keypoints({
      ...baseAnn,
      table_info: {
        name: table,
        group: "annotations",
        base_schema: BaseSchema.Keypoints,
      },
      data: { ...baseData, ...keypoints },
    });
  } else if (shape.type === SaveShapeType.tracklet) {
    const table = getTable(dataset_schema, "annotations", BaseSchema.Tracklet);

    newObject = new Tracklet({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.Tracklet },
      data: { ...baseData, ...shape.attrs, start_timestamp: -1, end_timestamp: -1 }, //TODO timestamps
    });
  } else if (shape.type === SaveShapeType.textSpan) {
    const table = getTable(dataset_schema, "annotations", BaseSchema.TextSpan);

    newObject = new TextSpan({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.TextSpan },
      data: { ...baseData, ...shape.attrs },
    });
  } else return undefined;

  //need to put UI fields after creation, else zod rejects
  newObject.ui.datasetItemType = isVideo
    ? WorkspaceType.VIDEO
    : shape.type === SaveShapeType.textSpan
      ? WorkspaceType.IMAGE_TEXT_ENTITY_LINKING
      : WorkspaceType.IMAGE;

  if (isVideo && shape.type !== SaveShapeType.tracklet)
    newObject.ui.frame_index = currentFrameIndex;

  //add extra features if any
  if (newObject.table_info.name in features) {
    for (const feat of Object.values(features[newObject.table_info.name])) {
      newObject.data = { ...newObject.data, [feat.name]: feat.value };
    }
  }

  return newObject;
};
