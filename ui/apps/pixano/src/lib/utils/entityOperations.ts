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
  Track,
  WorkspaceType,
  type BBoxData,
  type DatasetSchema,
  type DS_NamedSchema,
  type ItemFeature,
  type MaskData,
  type Reference,
  type SequenceFrame,
} from "$lib/types/dataset";
import { ShapeType, type SaveShape } from "$lib/types/shapeTypes";
import { datasetSchema, sourcesStore } from "$lib/stores/appStores.svelte";
import { getPixanoSource, getTable } from "$lib/utils/entityLookupUtils";
import { nowTimestamp } from "$lib/utils/coreUtils";

import { entities, views } from "$lib/stores/workspaceStores.svelte";

export const defineCreatedEntity = (
  shape: SaveShape,
  features: Record<string, ItemFeature>,
  entitySchema: DS_NamedSchema,
  parentOfSub: Reference | undefined = undefined,
  alternateViewRef: Reference | undefined = undefined,
): Entity => {
  const table = entitySchema.name;
  const now = nowTimestamp();
  const entity = {
    id: nanoid(10),
    created_at: now,
    updated_at: now,
    table_info: { name: table, group: "entities", base_schema: entitySchema.base_schema },
    data: {
      item_ref: { name: "item", id: shape.itemId },
      view_ref:
        parentOfSub && alternateViewRef ? alternateViewRef : shape.viewRef || { name: "", id: "" },
      parent_ref: parentOfSub ? parentOfSub : { name: "", id: "" },
    },
  };

  if (features) {
    for (const feat of Object.values(features)) {
      entity.data = { ...entity.data, [feat.name]: feat.value };
    }
  }
  return new Entity(entity);
};

export const getFrameIndexFromViewRef = (viewRef: Reference): number => {
  const vs = views.value;
  if (!Array.isArray(vs[viewRef.name])) return 0;
  const view = (vs[viewRef.name] as SequenceFrame[]).find((sf) => sf.id === viewRef.id);
  if (view) return view.data.frame_index;
  else {
    console.error("Could not find a matching view:", viewRef);
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
      //need to find entity with corresponding parent_ref.id and table_info.name, and view name
      subEntity = entities.value.find(
        (entity) =>
          //need to find entity with corresponding parent_ref.id and table_info.name, and view name
          entity.table_info.name === subEntitySchema.name &&
          entity.table_info.base_schema === subEntitySchema.base_schema &&
          entity.data.parent_ref.id === topEntity!.id &&
          //badly, *sub*entity.data.view_ref (id, or at least name) is not always set (it should!)
          (entity.data.view_ref.id !== ""
            ? entity.data.view_ref.id === shape.viewRef.id
            : entity.data.view_ref.name !== ""
              ? entity.data.view_ref.name === shape.viewRef.name
              : entity.ui.childs?.every((ann) => ann.data.view_ref.name === shape.viewRef.name)),
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
  const pixSource = getPixanoSource(sourcesStore);
  const baseData = {
    item_ref: entity.data.item_ref,
    view_ref: viewRef,
    entity_ref: { name: entity.table_info.name, id: entity.id },
    source_ref: { name: pixSource.table_info.name, id: pixSource.id },
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
    const emptyMaskCounts = [shape.imageWidth * shape.imageHeight];
    const mask: MaskData =
      shape.type === ShapeType.mask
        ? {
            counts: shape.rle.counts,
            size: shape.rle.size,
          }
        : shape.polygonMode === "mask"
          ? {
              counts: shape.rle?.counts ?? emptyMaskCounts,
              size: shape.rle?.size ?? [shape.imageHeight, shape.imageWidth],
            }
          : {
              // Raw polygon mode keeps vector geometry as primary payload.
              counts: emptyMaskCounts,
              size: [shape.imageHeight, shape.imageWidth],
            };

    const inferenceMetadata =
      shape.type === ShapeType.polygon && shape.polygonMode === "polygon"
        ? {
            geometry_mode: "polygon",
            polygon_svg: shape.masksImageSVG,
            polygon_points: shape.polygonPoints,
          }
        : {};

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

    newAnnotation = new Track({
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
