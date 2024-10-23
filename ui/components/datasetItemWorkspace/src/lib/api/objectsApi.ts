/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import {
  Annotation,
  BBox,
  Mask,
  Keypoints,
  Tracklet,
  Entity,
  Track,
  Image,
  SequenceFrame,
} from "@pixano/core";
import type {
  Reference,
  MView,
  DisplayControl,
  Shape,
  BBoxType,
  MaskType,
  SaveShape,
  KeypointsTemplate,
  SaveItem,
  DatasetSchema,
  ItemFeature,
} from "@pixano/core";
import { mask_utils } from "@pixano/models/src";

import { saveData } from "../../lib/stores/datasetItemWorkspaceStores";

import {
  HIGHLIGHTED_BOX_STROKE_FACTOR,
  GROUND_TRUTH,
  NOT_ANNOTATION_ITEM_OPACITY,
  PRE_ANNOTATION,
  HIGHLIGHTED_MASK_STROKE_FACTOR,
} from "../constants";
import type {
  ItemsMeta,
  ObjectProperties,
  ObjectsSortedByModelType,
} from "../types/datasetItemWorkspaceTypes";
import { DEFAULT_FEATURE } from "../settings/defaultFeatures";
import { nanoid } from "nanoid";
import { templates } from "../settings/keyPointsTemplates";

export const getObjectEntity = (ann: Annotation, entities: Entity[]): Entity | undefined => {
  return entities.find((entity) => entity.id === ann.data.entity_ref.id);
};

export const getObjectsEntities = (anns: Annotation[], entities: Entity[]): Entity[] => {
  const entities_ids = anns.map((ann) => ann.data.entity_ref.id);
  return entities.filter((entity) => entities_ids.includes(entity.id));
};

const defineTooltip = (bbox: BBox, entity: Entity): string | null => {
  if (!(bbox && bbox.is_bbox)) return null;

  const confidence =
    bbox.data.confidence !== 0.0 && bbox.data.source_ref.name !== GROUND_TRUTH
      ? " " + bbox.data.confidence.toFixed(2)
      : "";

  const tooltip =
    typeof entity.data[DEFAULT_FEATURE] === "string"
      ? entity.data[DEFAULT_FEATURE] + confidence
      : null;
  return tooltip;
};

export const mapObjectToBBox = (bbox: BBox, views: MView, entities: Entity[]): BBox | undefined => {
  if (!bbox) return;
  if (!bbox.is_bbox) return;
  if (bbox.datasetItemType === "video" && bbox.displayControl?.hidden) return;
  if (bbox.data.source_ref.name === PRE_ANNOTATION && bbox.highlighted !== "self") return;
  if (!bbox.data.view_ref.name) return;
  let bbox_denorm_coords = bbox.data.coords;
  if (bbox.data.is_normalized) {
    const view = views[bbox.data.view_ref.name];
    const image = Array.isArray(view) ? view[0] : view;
    const imageHeight = image.data.height || 1;
    const imageWidth = image.data.width || 1;
    const [x, y, width, height] = bbox.data.coords;
    bbox_denorm_coords = [
      x * imageWidth,
      y * imageHeight,
      width * imageWidth,
      height * imageHeight,
    ];
  }
  const entity = getObjectEntity(bbox, entities);
  const tooltip = entity ? defineTooltip(bbox, entity) : "";

  return {
    ...bbox,
    data: {
      ...bbox.data,
      coords: bbox_denorm_coords,
    },
    tooltip,
    opacity: bbox.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
    visible: !bbox.displayControl?.hidden,
    editing: bbox.displayControl?.editing,
    strokeFactor: bbox.highlighted === "self" ? HIGHLIGHTED_BOX_STROKE_FACTOR : 1,
    highlighted: bbox.highlighted,
  } as BBox;
};

export const mapObjectToMasks = (obj: Mask): Mask | undefined => {
  if (
    obj.is_mask &&
    obj.data.view_ref.name &&
    !obj.review_state &&
    !(obj.data.source_ref.name === PRE_ANNOTATION && obj.review_state === "accepted")
  ) {
    const rle = obj.data.counts as number[];
    const size = obj.data.size;
    const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
    const masksSVG = mask_utils.convertSegmentsToSVG(maskPoly);

    return {
      id: obj.id,
      svg: masksSVG,
      data: obj.data,
      visible: !obj.displayControl?.hidden && !obj.displayControl?.hidden,
      editing: obj.displayControl?.editing ?? false, // Display control should exist, but we need a fallback value for linting purpose
      opacity: obj.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
      strokeFactor: obj.highlighted === "self" ? HIGHLIGHTED_MASK_STROKE_FACTOR : 1,
      highlighted: obj.highlighted,
    } as Mask;
  }
  return undefined;
};

export const mapObjectToKeypoints = (
  keypoints: Keypoints,
  views: MView,
): KeypointsTemplate | undefined => {
  if (
    !keypoints ||
    !keypoints.data.view_ref.name ||
    (keypoints.datasetItemType === "video" && keypoints.displayControl?.hidden)
  )
    return;
  const template = templates.find((t) => t.id === keypoints.data.template_id);
  if (!template) return;

  const view = views[keypoints.data.view_ref.name];
  const image = Array.isArray(view) ? view[0] : view;
  const imageHeight = image.data.height || 1;
  const imageWidth = image.data.width || 1;
  const vertices = [];
  for (let i = 0; i < keypoints.data.coords.length / 2; i++) {
    const x = keypoints.data.coords[i * 2] * imageWidth;
    const y = keypoints.data.coords[i * 2 + 1] * imageHeight;
    const features = {
      ...(template.vertices[i].features || {}),
      ...{ state: keypoints.data.states[i] },
    };
    vertices.push({ x, y, features });
  }
  const kptTemplate = {
    id: keypoints.id,
    viewRef: keypoints.data.view_ref,
    entityRef: keypoints.data.entity_ref,
    vertices,
    edges: template.edges,
    editing: keypoints.displayControl?.editing,
    visible: !keypoints.displayControl?.hidden,
    highlighted: keypoints.highlighted,
  } as KeypointsTemplate;
  if ("frame_index" in keypoints) kptTemplate.frame_index = keypoints.frame_index;
  return kptTemplate;
};

export const toggleObjectDisplayControl = (
  object: Annotation,
  displayControlProperty: keyof DisplayControl,
  properties: ("bbox" | "mask" | "keypoints")[],
  value: boolean,
): Annotation => {
  object.displayControl = {
    ...(object.displayControl || {}),
    [displayControlProperty]: value,
  };
  return object;
};

export const addOrUpdateSaveItem = (objects: SaveItem[], newObj: SaveItem) => {
  //if delete, remove eventual refs to this obj in objects
  if (newObj.change_type === "delete") {
    objects = objects.filter((obj) => newObj.object.id !== obj.object.id);
  }
  //if newObj already in objects, find it & replace
  const index = objects.findIndex((obj) => obj.object.id === newObj.object.id);
  if (index !== -1) {
    objects[index] = newObj;
  } else {
    objects.push(newObj);
  }
  return objects;
};

export const sortObjectsByModel = (anns: Annotation[]) =>
  anns.reduce(
    (acc, ann) => {
      if (ann.data.source_ref.name === PRE_ANNOTATION) {
        if (!ann.review_state) acc[PRE_ANNOTATION] = [ann, ...acc[PRE_ANNOTATION]];
        return acc;
      }
      acc[ann.data.source_ref.name] = [ann, ...(acc[ann.data.source_ref.name] || [])];
      return acc;
    },
    { [GROUND_TRUTH]: [], [PRE_ANNOTATION]: [] } as ObjectsSortedByModelType<Annotation>,
  );

export const updateExistingObject = (objects: Annotation[], newShape: Shape): Annotation[] => {
  return objects.map((object) => {
    if (newShape?.status !== "editing") return object;
    if (newShape.highlighted === "all") {
      object.highlighted = "all";
      object.displayControl = {
        ...object.displayControl,
        editing: false,
      };
    }
    if (newShape.highlighted === "self") {
      object.highlighted = newShape.shapeId === object.id ? "self" : "none";
      object.displayControl = {
        ...object.displayControl,
        editing: newShape.shapeId === object.id,
      };
    }

    if (newShape.shapeId !== object.id) return object;

    // Check if the object is an image Annotation
    if (object.datasetItemType === "image") {
      let changed = false;
      if (newShape.type === "mask" && object.is_mask) {
        (object as Mask).data.counts = newShape.counts;
        changed = true;
      }
      if (newShape.type === "bbox" && object.is_bbox) {
        (object as BBox).data.coords = newShape.coords;
        changed = true;
      }
      if (newShape.type === "keypoints" && object.is_keypoints) {
        const coords = [];
        const states = [];
        for (const vertex of newShape.vertices) {
          coords.push(vertex.x);
          coords.push(vertex.y);
          if (vertex.features.state) states.push(vertex.features.state);
        }
        (object as Keypoints).data.coords = coords;
        (object as Keypoints).data.states = states;
        changed = true;
      }
      if (changed) {
        const save_item: SaveItem = {
          change_type: "update",
          object,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
      }
    }
    return object;
  });
};

export const getObjectsToPreAnnotate = (objects: Annotation[]): Annotation[] =>
  objects.filter(
    (object) => object.data.source_ref.name === PRE_ANNOTATION && !object.review_state,
  );

//Need to check, but it seems this function applies only to BBox
export const sortAndFilterObjectsToAnnotate = (
  objects: Annotation[],
  confidenceFilterValue: number[],
  currentFrameIndex: number,
): Annotation[] => {
  return objects
    .filter((object) => {
      if (object.datasetItemType === "image" && object.is_bbox) {
        const confidence = (object as BBox).data.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      if (
        object.datasetItemType === "video" &&
        object.is_bbox &&
        object.frame_index === currentFrameIndex
      ) {
        const confidence = (object as BBox).data.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      return false; // Ignore objects without bboxes
    })
    .sort((a, b) => {
      const firstBoxXPosition = (a as BBox).data.coords[0] || 0;
      const secondBoxXPosition = (b as BBox).data.coords[0] || 0;
      return firstBoxXPosition - secondBoxXPosition;
    });
};

export const mapObjectWithNewStatus = (
  allObjects: Annotation[],
  objectsToAnnotate: Annotation[],
  status: "accepted" | "rejected",
  features: ObjectProperties = {},
): Annotation[] => {
  //TODO (preAnnotation)
  features;
  return allObjects;

  // const nextObjectId = objectsToAnnotate[1]?.id;
  // return allObjects.map((object) => {
  //   if (object.id === nextObjectId) {
  //     object.highlighted = "self";
  //   } else {
  //     object.highlighted = "none";
  //   }
  //   if (object.id === objectsToAnnotate[0]?.id) {
  //     object.review_state = status;
  //     Object.keys(features || {}).forEach((key) => {
  //       if (object[features[key]]) {
  //         object[features[key]] = features[key];
  //       }
  //     });
  //   }
  //   return object;
  // });
};

export const createObjectCardId = (object: Annotation | Entity): string => `object-${object.id}`;

const getTable = (
  dataset_schema: DatasetSchema,
  group: keyof DatasetSchema["groups"],
  base_schema: string,
): string => {
  for (const group_table of dataset_schema.groups[group]) {
    if (dataset_schema.schemas[group_table].base_schema === base_schema) {
      //NOTE: if there is several group tables with same base_schema, we could compare with "fields" to choose the correct one
      //it shouldn't happen for entities, but may happens for annotations...
      return group_table;
    }
  }
  return dataset_schema.groups[group][0]; //lint protection, should not happens
};

export const defineCreatedEntity = (
  shape: SaveShape,
  features: Record<string, ItemFeature>,
  dataset_schema: DatasetSchema,
  isVideo: boolean,
): Entity | Track => {
  const table = getTable(dataset_schema, "entities", isVideo ? "Track" : "Entity");
  const now = new Date(Date.now()).toISOString();
  const entity = {
    id: nanoid(10),
    created_at: now,
    updated_at: now,
    table_info: { name: table, group: "entities", base_schema: isVideo ? "Track" : "Entity" },
    data: {
      item_ref: { name: "item", id: shape.itemId },
      view_ref: shape.viewRef,
      parent_ref: { name: "", id: "" },
    },
  };
  for (const feat of Object.values(features)) {
    entity.data = { ...entity.data, [feat.name]: feat.value };
  }
  if (isVideo) {
    //already done just before, but lint require entity.data.name, and can't know it's done...
    const track = { ...entity, data: { ...entity.data, name: features["name"].value as string } };
    return new Track(track);
  } else return new Entity(entity);
};

export const defineCreatedObject = (
  entity: Entity,
  shape: SaveShape,
  viewRef: Reference,
  dataset_schema: DatasetSchema,
  isVideo: boolean,
  currentFrameIndex: number,
): Annotation | undefined => {
  const now = new Date(Date.now()).toISOString();
  const baseAnn = {
    id: nanoid(10),
    created_at: now,
    updated_at: now,
  };
  const baseData = {
    item_ref: entity.data.item_ref,
    view_ref: viewRef,
    entity_ref: { name: entity.table_info.name, id: entity.id },
    source_ref: { name: GROUND_TRUTH, id: "" },
  };
  let newObject: Annotation | undefined = undefined;
  if (shape.type === "bbox") {
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
    const table = getTable(dataset_schema, "annotations", "BBox");
    newObject = new BBox({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: "BBox" },
      data: { ...baseData, ...bbox },
    });
  } else if (shape.type === "mask") {
    const mask: MaskType = {
      counts: shape.rle.counts,
      size: shape.rle.size,
    };
    const table = getTable(dataset_schema, "annotations", "CompressedRLE");
    newObject = new Mask({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: "CompressedRLE" },
      data: { ...baseData, ...mask },
    });
  } else if (shape.type === "keypoints") {
    const coords = [];
    const states = [];
    for (const vertex of shape.keypoints.vertices) {
      coords.push(vertex.x / shape.imageWidth);
      coords.push(vertex.y / shape.imageHeight);
      states.push(vertex.features.state ? vertex.features.state : "visible");
    }
    const keypoints = {
      template_id: shape.keypoints.id,
      coords,
      states,
    };
    const table = getTable(dataset_schema, "annotations", "KeyPoints");
    newObject = new Keypoints({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: "KeyPoints" },
      data: { ...baseData, ...keypoints },
    });
  } else if (shape.type === "tracklet") {
    const table = getTable(dataset_schema, "annotations", "Tracklet");
    newObject = new Tracklet({
      ...baseAnn,
      table_info: { name: table, group: "annotations", base_schema: "Tracklet" },
      data: { ...baseData, ...shape.attrs, start_timestamp: -1, end_timestamp: -1 }, //TODO timestamps
    });
  } else {
    return undefined;
  }
  //need to put UI fields after creation, else zod rejects
  newObject.datasetItemType = isVideo ? "video" : "image";
  if (isVideo) newObject.frame_index = currentFrameIndex;
  return newObject;
};

export const highlightCurrentObject = (
  objects: Annotation[],
  currentObject: Annotation,
  shouldUnHighlight: boolean = true,
) => {
  const isObjectHighlighted = currentObject.highlighted === "self";

  let highlight_ids: string[] = [];
  if (currentObject.is_tracklet) {
    //highlight childs
    highlight_ids = (currentObject as Tracklet).childs.map((ann) => ann.id);
  }

  return objects.map((object) => {
    object.displayControl = {
      ...object.displayControl,
      editing: object.id === currentObject.id ? object.displayControl?.editing : false,
    };
    if (isObjectHighlighted && shouldUnHighlight) {
      object.highlighted = "all";
    } else if (object.id === currentObject.id || highlight_ids.includes(object.id)) {
      object.highlighted = "self";
    } else {
      object.highlighted = "none";
    }
    return object;
  });
};

export const defineObjectThumbnail = (metas: ItemsMeta, views: MView, object: Annotation) => {
  let box: BBox | undefined = undefined;
  if (object.is_bbox) {
    box = object as BBox;
  }
  const view_name = object.data.view_ref.name;
  if (!box || !box.is_bbox || !view_name) return null;
  //prevent bug: if thumbnail is asked before data are fully loaded, we can have a error on a bad key
  if (!(view_name in views)) return null;
  const view =
    metas.type === "video"
      ? (views[view_name] as SequenceFrame[])[box.frame_index!]
      : (views[view_name] as Image);
  const coords = box.data.coords;
  return {
    baseImageDimensions: {
      width: view?.data.width,
      height: view?.data.height,
    },
    coords,
    uri: view?.data.url,
  };
};
