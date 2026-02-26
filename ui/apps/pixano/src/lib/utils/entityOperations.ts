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
  TextSpan,
  Tracklet,
  WorkspaceType,
  type BBoxData,
  type DatasetSchema,
  type DS_NamedSchema,
  type ItemFeature,
  type MaskData,
  type Reference,
} from "$lib/types/dataset";
import { ShapeType, type EditShape, type SaveShape } from "$lib/types/shapeTypes";
import { datasetSchema, sourcesStore } from "$lib/stores/appStores.svelte";
import { getPixanoSourceId, getTable } from "$lib/utils/entityLookupUtils";
import { verticesToCoordsAndStates } from "$lib/utils/keypointsUtils";
import { nowTimestamp } from "$lib/utils/coreUtils";

import { entities, views } from "$lib/stores/workspaceStores.svelte";

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
  if (shape.type !== ShapeType.mask && shape.type !== ShapeType.polygon) {
    throw new Error(`Expected mask or polygon shape, got ${shape.type}`);
  }

  const emptyMaskCounts = [shape.imageWidth * shape.imageHeight];
  const mask: MaskData = {
    counts: shape.rle?.counts ?? emptyMaskCounts,
    size: shape.rle?.size ?? [shape.imageHeight, shape.imageWidth],
  };
  const inferenceMetadata = {};

  return { mask, inferenceMetadata };
};

export const applyEditedShapeDataToAnnotation = (
  ann: Annotation,
  shape: EditShape,
): boolean => {
  if ((shape.type === ShapeType.mask || shape.type === ShapeType.polygon) && ann.is_type(BaseSchema.Mask)) {
    if ("counts" in shape && Array.isArray(shape.counts)) {
      (ann as Mask).data.counts = shape.counts;
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
  parentOfSub: Reference | undefined = undefined,
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
      parent_id: parentOfSub ? parentOfSub.id : "",
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
  const view = (vs[view_name] as import("$lib/types/dataset").SequenceFrame[]).find((sf) => sf.id === frame_id);
  if (view) return view.data.frame_index;
  else {
    console.error("Could not find a matching view:", view_name, frame_id);
    return 0;
  }
};

export const findOrCreateSubAndTopEntities = (
  selectedEntityId: string,
  shape: SaveShape,
  features: Record<string, Record<string, ItemFeature>>,
): {
  topEntity: Entity;
  subEntity: Entity | undefined;
} => {
  //Manage sub-entity: check if there is some subentity table(s)
  //if so, choose the correct one, and separate topEntity from subEntity ...
  //TMP: we should rely on "table relations" from datasetSchema.value, but it's not available yet
  //TMP: so, we will make the assumption that the only case with subentity is : 1 Track + 1 Entity (sub)
  //TMP: -> we take trackSchemas[0] and entitySchemas[0]
  let topEntity: Entity | undefined = undefined;
  let subEntity: Entity | undefined = undefined;
  let topEntitySchema: DS_NamedSchema | undefined = undefined;
  let subEntitySchema: DS_NamedSchema | undefined = undefined;
  const entitySchemas: DS_NamedSchema[] = [];
  const trackSchemas: DS_NamedSchema[] = [];
  const multiModalSchemas: DS_NamedSchema[] = [];
  for (const [name, sch] of Object.entries(datasetSchema.value?.schemas ?? {})) {
    if (sch.base_schema === BaseSchema.Track) {
      trackSchemas.push({ ...sch, name });
    } else if (sch.base_schema === BaseSchema.MultiModalEntity) {
      multiModalSchemas.push({ ...sch, name });
    } else if (sch.base_schema === BaseSchema.Entity) {
      entitySchemas.push({ ...sch, name });
    }
  }
  if (trackSchemas.length > 0) {
    topEntitySchema = trackSchemas[0];
    if (entitySchemas.length > 0) {
      subEntitySchema = entitySchemas[0];
    }
  } else if (multiModalSchemas.length > 0) {
    topEntitySchema = multiModalSchemas[0];
    if (entitySchemas.length > 0) {
      subEntitySchema = entitySchemas[0];
    }
  } else if (entitySchemas.length > 0) {
    topEntitySchema = entitySchemas[0];
  } else {
    console.error("ERROR: No available schema Entity", datasetSchema.value?.schemas ?? {});
    throw new Error("ERROR: No available schema Entity");
  }

  if (selectedEntityId === "new") {
    topEntity = defineCreatedEntity(
      shape,
      features[topEntitySchema.name],
      topEntitySchema,
    );
    topEntity.ui.childs = [];
    if (subEntitySchema) {
      subEntity = defineCreatedEntity(
        shape,
        features[subEntitySchema.name],
        subEntitySchema,
        {
          id: topEntity.id,
          name: topEntity.table_info.name,
        },
      );
      subEntity.ui.childs = [];
    }
  } else {
    topEntity = entities.value.find((entity) => entity.id === selectedEntityId);
    if (!topEntity) {
      topEntity = defineCreatedEntity(
        shape,
        features[topEntitySchema.name],
        topEntitySchema,
      );
      topEntity.ui.childs = [];
    }
    if (subEntitySchema) {
      //need to find entity with corresponding parent_id and table_info.name, and view name
      subEntity = entities.value.find(
        (entity) =>
          entity.table_info.name === subEntitySchema.name &&
          entity.table_info.base_schema === subEntitySchema.base_schema &&
          entity.data.parent_id === topEntity.id &&
          // match by child annotations' view_name
          entity.ui.childs?.every((ann) => ann.data.view_name === shape.viewRef.name),
      );
      if (!subEntity) {
        subEntity = defineCreatedEntity(
          shape,
          features[subEntitySchema.name],
          subEntitySchema,
          {
            id: topEntity.id,
            name: topEntity.table_info.name,
          },
        );
        subEntity.ui.childs = [];
      }
    }
  }
  return { topEntity, subEntity };
};

export const defineCreatedAnnotation = (
  entity: Entity,
  features: Record<string, Record<string, ItemFeature>>,
  shape: SaveShape,
  viewRef: Reference,
  dataset_schema: DatasetSchema,
  isVideo: boolean,
  currentFrameIndex: number,
): Annotation | undefined => {
  const now = nowTimestamp();
  const baseAnn = {
    id: nanoid(10),
    created_at: now,
    updated_at: now,
  };
  const sourceId = getPixanoSourceId(sourcesStore);
  const baseData = {
    item_id: entity.data.item_id,
    view_name: viewRef.name,
    frame_id: viewRef.id,
    entity_id: entity.id,
    source_id: sourceId,
    frame_index: -1,
    tracklet_id: "",
    entity_dynamic_state_id: "",
    inference_metadata: {},
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

    const table = getTable(dataset_schema, "annotations", BaseSchema.BBox);
    newAnnotation = new BBox({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.BBox },
      data: { ...baseData, ...bbox },
    });
  } else if (shape.type === ShapeType.mask || shape.type === ShapeType.polygon) {
    const { mask, inferenceMetadata } = buildMaskDataAndInferenceMetadata(shape);

    const table = getTable(dataset_schema, "annotations", BaseSchema.Mask);
    newAnnotation = new Mask({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.Mask },
      data: { ...baseData, inference_metadata: inferenceMetadata, ...mask },
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

    const table = getTable(dataset_schema, "annotations", BaseSchema.Keypoints);

    newAnnotation = new Keypoints({
      ...baseAnn,
      table_info: {
        name: table,
        group: "annotations",
        base_schema: BaseSchema.Keypoints,
      },
      data: { ...baseData, ...keypoints },
    });
  } else if (shape.type === ShapeType.track) {
    const table = getTable(dataset_schema, "annotations", BaseSchema.Tracklet);

    newAnnotation = new Tracklet({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: BaseSchema.Tracklet },
      data: { ...baseData, ...shape.attrs, start_timestamp: -1, end_timestamp: -1 }, //TODO timestamps
    });
  } else if (shape.type === ShapeType.textSpan) {
    const table = getTable(dataset_schema, "annotations", BaseSchema.TextSpan);

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

  if (isVideo && shape.type !== ShapeType.track)
    newAnnotation.ui.frame_index = currentFrameIndex;

  //add extra features if any
  if (newAnnotation.table_info.name in features) {
    for (const feat of Object.values(features[newAnnotation.table_info.name])) {
      newAnnotation.data = { ...newAnnotation.data, [feat.name]: feat.value };
    }
  }

  return newAnnotation;
};
