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

export const getTopEntity = (ann: Annotation, entities: Entity[]): Entity => {
  if (ann.ui.top_entity) {
    return ann.ui.top_entity;
  }
  let entity = entities.find((entity) => entity.id === ann.data.entity_ref.id);
  while (entity && entity.data.parent_ref.id !== "") {
    entity = entities.find(
      (parent_entity) => entity && parent_entity.id === entity.data.parent_ref.id,
    );
  }
  if (!entity) {
    console.error("ERROR: Unable to found top level Entity of annotation", ann);
  }
  //store top_entity to avoid computing each time
  ann.ui.top_entity = entity;
  return entity as Entity;
};

export const getObjectsEntities = (anns: Annotation[], entities: Entity[]): Entity[] => {
  return Array.from(new Set(anns.map((ann) => getTopEntity(ann, entities))));
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
  if (bbox.ui.datasetItemType === "video" && bbox.ui.displayControl?.hidden) return;
  if (bbox.data.source_ref.name === PRE_ANNOTATION && bbox.ui.highlighted !== "self") return;
  if (!bbox.data.view_ref.name) return;
  let bbox_denorm_coords = bbox.data.coords;
  if (bbox.data.is_normalized) {
    const view = views[bbox.data.view_ref.name];
    const image = Array.isArray(view) ? view[0] : view;
    const imageHeight = image.data.height || 1;
    const imageWidth = image.data.width || 1;
    //TODO: manage correctly format -- here we will change user format if save
    let reformated_coords = bbox.data.coords;
    if (bbox.data.format === "xyxy") {
      reformated_coords = [
        bbox.data.coords[0],
        bbox.data.coords[1],
        bbox.data.coords[2] - bbox.data.coords[0],
        bbox.data.coords[3] - bbox.data.coords[1],
      ];
    }
    const [x, y, width, height] = reformated_coords;
    bbox_denorm_coords = [
      x * imageWidth,
      y * imageHeight,
      width * imageWidth,
      height * imageHeight,
    ];
  }
  const entity = getTopEntity(bbox, entities);
  const tooltip = entity ? defineTooltip(bbox, entity) : "";

  return {
    ...bbox,
    data: {
      ...bbox.data,
      coords: bbox_denorm_coords,
      format: "xywh",
    },
    ui: {
      ...bbox.ui,
      tooltip,
      opacity: bbox.ui.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
      strokeFactor: bbox.ui.highlighted === "self" ? HIGHLIGHTED_BOX_STROKE_FACTOR : 1,
    },
  } as BBox;
};

export const mapObjectToMasks = (obj: Mask): Mask | undefined => {
  if (
    obj.is_mask &&
    obj.data.view_ref.name &&
    !obj.ui.review_state &&
    !(obj.data.source_ref.name === PRE_ANNOTATION && obj.ui.review_state === "accepted")
  ) {
    const rle = obj.data.counts as number[];
    const size = obj.data.size;
    const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
    const masksSVG = mask_utils.convertSegmentsToSVG(maskPoly);

    return {
      id: obj.id,
      data: obj.data,
      ui: {
        ...obj.ui,
        svg: masksSVG,
        opacity: obj.ui.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
        strokeFactor: obj.ui.highlighted === "self" ? HIGHLIGHTED_MASK_STROKE_FACTOR : 1,
      },
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
    (keypoints.ui.datasetItemType === "video" && keypoints.ui.displayControl?.hidden)
  )
    return;
  const template = templates.find((t) => t.template_id === keypoints.data.template_id);
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
    template_id: keypoints.data.template_id,
    viewRef: keypoints.data.view_ref,
    entityRef: keypoints.data.entity_ref,
    vertices,
    edges: template.edges,
    ui: {
      displayControl: {
        editing: keypoints.ui.displayControl?.editing,
        visible: !keypoints.ui.displayControl?.hidden,
      },
      highlighted: keypoints.ui.highlighted,
    },
  } as KeypointsTemplate;
  if ("frame_index" in keypoints.ui) kptTemplate.ui!.frame_index = keypoints.ui.frame_index;
  if ("top_entity" in keypoints.ui) kptTemplate.ui!.top_entity = keypoints.ui.top_entity;
  return kptTemplate;
};

export const toggleObjectDisplayControl = (
  object: Annotation,
  displayControlProperty: keyof DisplayControl,
  properties: ("bbox" | "mask" | "keypoints")[],
  value: boolean,
): Annotation => {
  object.ui.displayControl = {
    ...(object.ui.displayControl || {}),
    [displayControlProperty]: value,
  };
  return object;
};

export const addOrUpdateSaveItem = (objects: SaveItem[], newObj: SaveItem) => {
  const existing_sames = objects.filter((item) => newObj.object.id === item.object.id);
  //remove other refs to this same object (as the last state is the correct one)
  objects = objects.filter((item) => newObj.object.id !== item.object.id);

  if (
    newObj.change_type === "delete" &&
    existing_sames.some((item) => item.change_type === "add")
  ) {
    //deleting an object created in this "session" (after last save): no need to keep delete
    return objects;
  }
  if (
    newObj.change_type === "update" &&
    existing_sames.some((item) => item.change_type === "add")
  ) {
    newObj.change_type = "add";
  }
  objects.push(newObj);
  return objects;
};

export const sortObjectsByModel = (anns: Annotation[]) =>
  anns.reduce(
    (acc, ann) => {
      if (ann.data.source_ref.name === PRE_ANNOTATION) {
        if (!ann.ui.review_state) acc[PRE_ANNOTATION] = [...acc[PRE_ANNOTATION], ann];
        return acc;
      }
      acc[ann.data.source_ref.name] = [...(acc[ann.data.source_ref.name] || []), ann];
      return acc;
    },
    { [GROUND_TRUTH]: [], [PRE_ANNOTATION]: [] } as ObjectsSortedByModelType<Annotation>,
  );

export const updateExistingObject = (objects: Annotation[], newShape: Shape): Annotation[] => {
  return objects.map((ann) => {
    if (newShape?.status !== "editing") return ann;
    if (newShape.highlighted === "all") {
      ann.ui.highlighted = "all";
      ann.ui.displayControl = {
        ...ann.ui.displayControl,
        editing: false,
      };
    }
    if (newShape.highlighted === "self") {
      if (newShape.shapeId === ann.id) {
        ann.ui.highlighted = "self";
        ann.ui.displayControl = { ...ann.ui.displayControl, editing: true };
      } else {
        if (ann.is_tracklet) {
          //NOTE TODO: it works, but the states with 1 tracklet highlighted in a track with several tracklet leads to bug with icon click
          const tracklet_childs_ids = (ann as Tracklet).ui.childs.map((c_ann) => c_ann.id);
          if (tracklet_childs_ids.includes(newShape.shapeId)) {
            ann.ui.highlighted = "self";
          } else {
            ann.ui.highlighted = "none";
          }
        } else {
          //NOTE: maybe we want to keep all ann of tracklet/track highlighted ? (only one in edition, but all highlighted ?)
          ann.ui.highlighted = "none";
          ann.ui.displayControl = { ...ann.ui.displayControl, editing: false };
        }
      }
    }

    if (newShape.shapeId !== ann.id) return ann;

    // Check if the object is an image Annotation
    if (ann.ui.datasetItemType === "image") {
      let changed = false;
      if (newShape.type === "mask" && ann.is_mask) {
        (ann as Mask).data.counts = newShape.counts;
        changed = true;
      }
      if (newShape.type === "bbox" && ann.is_bbox) {
        (ann as BBox).data.coords = newShape.coords;
        changed = true;
      }
      if (newShape.type === "keypoints" && ann.is_keypoints) {
        const coords = [];
        const states = [];
        for (const vertex of newShape.vertices) {
          coords.push(vertex.x);
          coords.push(vertex.y);
          if (vertex.features.state) states.push(vertex.features.state);
        }
        (ann as Keypoints).data.coords = coords;
        (ann as Keypoints).data.states = states;
        changed = true;
      }
      if (changed) {
        const save_item: SaveItem = {
          change_type: "update",
          object: ann,
        };
        saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
      }
    }
    return ann;
  });
};

export const getObjectsToPreAnnotate = (objects: Annotation[]): Annotation[] =>
  objects.filter(
    (object) => object.data.source_ref.name === PRE_ANNOTATION && !object.ui.review_state,
  );

//Need to check, but it seems this function applies only to BBox
export const sortAndFilterObjectsToAnnotate = (
  objects: Annotation[],
  confidenceFilterValue: number[],
  currentFrameIndex: number,
): Annotation[] => {
  return objects
    .filter((object) => {
      if (object.ui.datasetItemType === "image" && object.is_bbox) {
        const confidence = (object as BBox).data.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      if (
        object.ui.datasetItemType === "video" &&
        object.is_bbox &&
        object.ui.frame_index === currentFrameIndex
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
  //     object.ui.highlighted = "self";
  //   } else {
  //     object.ui.highlighted = "none";
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
      parent_ref: { name: "", id: "" }, //TODO intermediate entity ??
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
      template_id: shape.keypoints.template_id,
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
  newObject.ui.datasetItemType = isVideo ? "video" : "image";
  if (isVideo && shape.type !== "tracklet") newObject.ui.frame_index = currentFrameIndex;
  return newObject;
};

//switch current highlight state (always switch according to hvalue if hvalue is set)
export const highlightAnnotation = (currentObject: Annotation, hvalue: boolean = undefined) => {
  if (hvalue === undefined) {
    if (
      !currentObject.ui.highlighted ||
      currentObject.ui.highlighted === "none" ||
      currentObject.ui.highlighted === "all"
    ) {
      currentObject.ui.highlighted = "self";
    } else {
      currentObject.ui.highlighted = "all";
    }
  } else {
    currentObject.ui.highlighted = hvalue?"self":"all";
  }
  return currentObject;
};

//called on other annotations (not the switched one) to adapt it state
export const unhighlightAnnotation = (
  currentObject: Annotation,
  other_was_highlighted: boolean,
) => {
  currentObject.ui.highlighted = other_was_highlighted ? "all" : "none";
  return currentObject;
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
      ? (views[view_name] as SequenceFrame[])[box.ui.frame_index!]
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
