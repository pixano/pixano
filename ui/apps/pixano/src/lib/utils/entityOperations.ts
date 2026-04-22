/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { nanoid } from "nanoid";

import { entities, views } from "$lib/stores/workspaceStores.svelte";
import {
  Annotation,
  BaseSchema,
  BBox,
  Entity,
  Keypoints,
  Mask,
  MultiPath,
  TextSpan,
  Tracklet,
  WorkspaceType,
  type BBoxData,
  type DS_NamedSchema,
  type ItemFeature,
  type MaskData,
  type Reference,
} from "$lib/types/dataset";
import { ShapeType, type EditShape, type SaveShape } from "$lib/types/shapeTypes";
import { toLegacyReference, toViewLocator } from "$lib/types/workspaceLocators";
import { nowTimestamp } from "$lib/utils/coreUtils";
import { getTable, PIXANO_SOURCE } from "$lib/utils/entityLookupUtils";
import { verticesToCoordsAndStates } from "$lib/utils/keypointsUtils";
import { resolveVideoFrameIdentity } from "$lib/utils/videoFrameIdentity";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

export const removeAnnotationsByIds = (
  anns: Annotation[] | undefined,
  ids: Iterable<string>,
): Annotation[] => {
  if (!anns || anns.length === 0) return [];
  const idsSet = ids instanceof Set ? ids : new Set(ids);
  return anns.filter((ann) => !idsSet.has(ann.id));
};

export const appendAnnotationsSorted = (
  anns: Annotation[] | undefined,
  additions: Annotation[],
  sortFn?: (a: Annotation, b: Annotation) => number,
): Annotation[] => {
  if ((!anns || anns.length === 0) && additions.length === 0) return [];
  const next = [...(anns ?? []), ...additions];
  if (sortFn) next.sort(sortFn);
  return next;
};

export const buildMaskDataAndInferenceMetadata = (
  shape: SaveShape,
): { mask: MaskData; inferenceMetadata: Record<string, unknown> } => {
  if (shape.type !== ShapeType.mask) {
    throw new Error(`Expected mask shape, got ${shape.type}`);
  }

  const emptyMaskCounts = [shape.imageWidth * shape.imageHeight];
  const mask: MaskData = {
    counts: shape.rle?.counts ?? emptyMaskCounts,
    size: shape.rle?.size ?? [shape.imageHeight, shape.imageWidth],
  };
  const inferenceMetadata = {};

  return { mask, inferenceMetadata };
};

export const applyEditedShapeDataToAnnotation = (ann: Annotation, shape: EditShape): boolean => {
  if (shape.type === ShapeType.mask && ann.is_type(BaseSchema.Mask)) {
    if ("counts" in shape && Array.isArray(shape.counts)) {
      (ann as Mask).data.counts = shape.counts;
    }
    return true;
  }

  if (
    (shape.type === ShapeType.polygon || shape.type === ShapeType.polyline) &&
    ann.is_type(BaseSchema.MultiPath)
  ) {
    const sourcePolys: Array<Array<{ x: number; y: number }>> =
      "polygonPoints" in shape && Array.isArray(shape.polygonPoints)
        ? shape.polygonPoints
        : "polylinePoints" in shape && Array.isArray(shape.polylinePoints)
          ? shape.polylinePoints
          : [];
    if (sourcePolys.length > 0) {
      const coords: number[] = [];
      const numPoints: number[] = [];
      for (const poly of sourcePolys) {
        numPoints.push(poly.length);
        for (const pt of poly) {
          coords.push(pt.x, pt.y);
        }
      }
      (ann as MultiPath).data.coords = coords;
      (ann as MultiPath).data.num_points = numPoints;
    }
    return true;
  }

  if (shape.type === ShapeType.bbox && ann.is_type(BaseSchema.BBox)) {
    (ann as BBox).data.coords = shape.coords;
    return true;
  }

  if (shape.type === ShapeType.keypoints && ann.is_type(BaseSchema.Keypoints)) {
    const { coords, states } = verticesToCoordsAndStates(shape.vertices);
    (ann as Keypoints).data.coords = coords;
    (ann as Keypoints).data.states = states;
    return true;
  }

  return false;
};

export const defineCreatedEntity = (
  shape: SaveShape,
  features: Record<string, ItemFeature>,
  entitySchema: DS_NamedSchema,
): Entity => {
  const table = entitySchema.name;
  const now = nowTimestamp();
  const entity = {
    id: nanoid(10),
    created_at: now,
    updated_at: now,
    table_info: { name: table, group: "entities", base_schema: entitySchema.base_schema },
    data: {
      item_id: shape.itemId,
      parent_id: "",
    },
  };

  if (features) {
    for (const feat of Object.values(features)) {
      entity.data = { ...entity.data, [feat.name]: feat.value };
    }
  }
  return new Entity(entity);
};

export const getFrameIndex = (view_name: string, frame_id: string): number => {
  const vs = views.value;
  if (!Array.isArray(vs[view_name])) return 0;
  const view = (vs[view_name] as import("$lib/types/dataset").SequenceFrame[]).find(
    (sf) => sf.id === frame_id,
  );
  if (view) return view.data.frame_index;
  else {
    console.error("Could not find a matching view:", view_name, frame_id);
    return 0;
  }
};

function getSingleEntitySchema(workspaceManifest: WorkspaceManifest): DS_NamedSchema {
  const entityTables = workspaceManifest.tablesByGroup.entities;
  if (entityTables.length !== 1) {
    console.error("ERROR: Expected exactly one entity table", workspaceManifest.tablesByName);
    throw new Error("ERROR: Expected exactly one entity table");
  }

  const tableName = entityTables[0];
  const table = workspaceManifest.tablesByName[tableName];
  if (!table || table.baseSchema !== BaseSchema.Entity) {
    console.error("ERROR: Invalid entity schema", tableName, table, workspaceManifest.tablesByName);
    throw new Error("ERROR: Invalid entity schema");
  }

  return {
    name: tableName,
    base_schema: table.baseSchema,
    fields: table.fields,
    schema: table.baseSchema,
  } satisfies DS_NamedSchema;
}

export const findOrCreateEntity = (
  selectedEntityId: string,
  shape: SaveShape,
  features: Record<string, Record<string, ItemFeature>>,
  workspaceManifest: WorkspaceManifest,
): Entity => {
  const entitySchema = getSingleEntitySchema(workspaceManifest);
  if (selectedEntityId === "new") {
    const entity = defineCreatedEntity(shape, features[entitySchema.name], entitySchema);
    entity.ui.childs = [];
    return entity;
  }

  const entity = entities.value.find((candidate) => candidate.id === selectedEntityId);
  if (entity) {
    return entity;
  }

  const createdEntity = defineCreatedEntity(shape, features[entitySchema.name], entitySchema);
  createdEntity.ui.childs = [];
  return createdEntity;
};

export const findOrCreateSubAndTopEntities = (
  selectedEntityId: string,
  shape: SaveShape,
  features: Record<string, Record<string, ItemFeature>>,
  workspaceManifest: WorkspaceManifest,
): {
  topEntity: Entity;
  subEntity: Entity | undefined;
} => {
  return {
    topEntity: findOrCreateEntity(selectedEntityId, shape, features, workspaceManifest),
    subEntity: undefined,
  };
};

export const defineCreatedAnnotation = (
  entity: Entity,
  features: Record<string, Record<string, ItemFeature>>,
  shape: SaveShape,
  viewRef: Reference,
  workspaceManifest: WorkspaceManifest,
  isVideo: boolean,
  currentFrameIndex: number,
): Annotation | undefined => {
  const now = nowTimestamp();
  const videoFrameRef =
    isVideo && shape.type !== ShapeType.track
      ? resolveVideoFrameIdentity(
          toViewLocator(viewRef),
          currentFrameIndex,
          Array.isArray(views.value[viewRef.name])
            ? (views.value[viewRef.name] as import("$lib/types/dataset").SequenceFrame[])
            : undefined,
        )
      : null;
  const annotationViewRef = videoFrameRef ? toLegacyReference(videoFrameRef.frameLocator) : viewRef;
  const annotationFrameIndex = videoFrameRef?.frameIndex ?? currentFrameIndex;
  const baseAnn = {
    id: nanoid(10),
    created_at: now,
    updated_at: now,
  };
  const baseData = {
    item_id: entity.data.item_id,
    view_name: annotationViewRef.name,
    entity_id: entity.id,
    source_type: PIXANO_SOURCE.type,
    source_name: PIXANO_SOURCE.name,
    source_metadata: PIXANO_SOURCE.metadata,
    inference_metadata: {},
  };
  const perFrameData = {
    ...baseData,
    frame_id: annotationViewRef.id,
    frame_index: videoFrameRef ? annotationFrameIndex : -1,
    tracklet_id: "",
    entity_dynamic_state_id: "",
  };
  let newAnnotation: Annotation | undefined = undefined;

  if (shape.type === ShapeType.bbox) {
    const { x, y, width, height } = shape.attrs;
    const coords = [
      x / shape.imageWidth,
      y / shape.imageHeight,
      width / shape.imageWidth,
      height / shape.imageHeight,
    ];

    const bbox: BBoxData = {
      coords,
      format: "xywh",
      is_normalized: true,
      confidence: 1,
    };

    const table = getTable(workspaceManifest, "annotations", BaseSchema.BBox);
    newAnnotation = new BBox({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.BBox },
      data: { ...perFrameData, ...bbox },
    });
  } else if (shape.type === ShapeType.mask) {
    const { mask, inferenceMetadata } = buildMaskDataAndInferenceMetadata(shape);

    const table = getTable(workspaceManifest, "annotations", BaseSchema.Mask);
    newAnnotation = new Mask({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.Mask },
      data: { ...perFrameData, inference_metadata: inferenceMetadata, ...mask },
    });
  } else if (shape.type === ShapeType.polygon || shape.type === ShapeType.polyline) {
    const isClosed = shape.type === ShapeType.polygon;
    const sourcePoints: Array<Array<{ x: number; y: number }>> =
      "polygonPoints" in shape && Array.isArray(shape.polygonPoints)
        ? shape.polygonPoints
        : "polylinePoints" in shape && Array.isArray(shape.polylinePoints)
          ? shape.polylinePoints
          : [];

    const coords: number[] = [];
    const num_points: number[] = [];
    for (const poly of sourcePoints) {
      num_points.push(poly.length);
      for (const pt of poly) {
        coords.push(pt.x / shape.imageWidth, pt.y / shape.imageHeight);
      }
    }

    const table = getTable(workspaceManifest, "annotations", BaseSchema.MultiPath);
    newAnnotation = new MultiPath({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.MultiPath },
      data: { ...perFrameData, coords, num_points, is_closed: isClosed },
    });
  } else if (shape.type === ShapeType.keypoints) {
    const coords = [];
    const states = [];

    for (let vi = 0; vi < shape.keypoints.graph.vertices.length; vi++) {
      const vertex = shape.keypoints.graph.vertices[vi];
      coords.push(vertex.x / shape.imageWidth);
      coords.push(vertex.y / shape.imageHeight);
      const meta = shape.keypoints.vertexMetadata[vi];
      states.push(meta?.state ? meta.state : "visible");
    }

    const keypoints = {
      template_id: shape.keypoints.template_id,
      coords,
      states,
    };

    const table = getTable(workspaceManifest, "annotations", BaseSchema.Keypoints);

    newAnnotation = new Keypoints({
      ...baseAnn,
      table_info: {
        name: table,
        group: "annotations",
        base_schema: BaseSchema.Keypoints,
      },
      data: { ...perFrameData, ...keypoints },
    });
  } else if (shape.type === ShapeType.track) {
    const table = getTable(workspaceManifest, "annotations", BaseSchema.Tracklet);

    newAnnotation = new Tracklet({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.Tracklet },
      data: { ...baseData, ...shape.attrs, start_timestamp: -1, end_timestamp: -1 },
    });
  } else if (shape.type === ShapeType.textSpan) {
    const table = getTable(workspaceManifest, "annotations", BaseSchema.TextSpan);

    newAnnotation = new TextSpan({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.TextSpan },
      data: { ...baseData, ...shape.attrs },
    });
  } else return undefined;

  //need to put UI fields after creation, else zod rejects
  newAnnotation.ui.datasetItemType = isVideo
    ? WorkspaceType.VIDEO
    : shape.type === ShapeType.textSpan
      ? WorkspaceType.IMAGE_TEXT_ENTITY_LINKING
      : WorkspaceType.IMAGE;

  if (isVideo && shape.type !== ShapeType.track) {
    newAnnotation.ui.frame_index = annotationFrameIndex;
    newAnnotation.data.frame_index = annotationFrameIndex;
    newAnnotation.data.frame_id = annotationViewRef.id;
    newAnnotation.data.view_name = annotationViewRef.name;
  }

  //add extra features if any
  if (newAnnotation.table_info.name in features) {
    for (const feat of Object.values(features[newAnnotation.table_info.name])) {
      newAnnotation.data = { ...newAnnotation.data, [feat.name]: feat.value };
    }
  }

  return newAnnotation;
};
