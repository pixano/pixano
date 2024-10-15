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
  Entity,
  View,
  Image,
  SequenceFrame,
  DatasetItem,
  Keypoints,
} from "@pixano/core";
import type {
  MView,
  DisplayControl,
  Shape,
  BBoxType,
  MaskType,
  SaveShape,
  VideoItemBBox,
  KeypointsTemplate,
  SaveItem,
  SaveUpdate,
  DatasetSchema,
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

export const mapObjectToBBox = (
  bbox: BBox,
  views: DatasetItem["views"],
  entities: Entity[],
): BBox => {
  if (!bbox) return {};
  if (!bbox.is_bbox) return {};
  if (bbox.datasetItemType === "video" && bbox.displayControl?.hidden) return {};
  if (bbox.data.source_ref.name === PRE_ANNOTATION && bbox.highlighted !== "self") return {};
  if (!bbox.data.view_ref.name) return {};
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
    visible: !bbox.displayControl?.hidden && !bbox.displayControl?.hidden,
    editing: bbox.displayControl?.editing,
    strokeFactor: bbox.highlighted === "self" ? HIGHLIGHTED_BOX_STROKE_FACTOR : 1,
    highlighted: bbox.highlighted,
  } as BBox;
};

export const mapObjectToMasks = (obj: Mask): Mask | undefined => {
  if (
    obj.datasetItemType === "image" && // Only images use masks ?
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
    };
  }
  return undefined;
};

export const mapObjectToKeypoints = (object: Keypoints, views: MView): KeypointsTemplate[] => {
  const res_m_keypoints: KeypointsTemplate[] = [];
  const m_keypoints: Keypoints[] = (
    object.datasetItemType === "video" ? object.displayedMKeypoints : [object]
  ) as Keypoints[];
  if (!m_keypoints) return [] as KeypointsTemplate[];
  for (const keypoints of m_keypoints) {
    if (
      !keypoints ||
      !keypoints.data.view_ref.name ||
      (object.datasetItemType === "video" && keypoints.displayControl?.hidden)
    )
      continue;
    const template = templates.find((t) => t.id === keypoints.data.template_id);
    if (!template) continue;
    const view = views?.[keypoints.data.view_ref.name];
    const image: View = Array.isArray(view) ? view[0] : view;
    const imageHeight = image.data.height || 1;
    const imageWidth = image.data.width || 1;
    const vertices = [];
    for (let i = 0; i < keypoints.data.coords.length / 2; i++) {
      const x = keypoints.data.coords[i * 2] * imageWidth;
      const y = keypoints.data.coords[i * 2 + 1] * imageHeight;
      const features = {
        ...(template.vertices[i].features || {}),
        ...({ state: keypoints.data.states[i] } || {}),
      };
      vertices.push({ x, y, features });
    }
    res_m_keypoints.push({
      id: object.id,
      viewRef: keypoints.data.view_ref,
      entityRef: keypoints.data.entity_ref,
      vertices,
      edges: template.edges,
      editing: object.displayControl?.editing,
      visible: !keypoints.displayControl?.hidden && !object.displayControl?.hidden,
      highlighted: object.highlighted,
    } as KeypointsTemplate);
  }
  return res_m_keypoints;
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
  let index = -1;
  // annotations in front are (sometime?) created without an id
  if ("id" in newObj.object) {
    index = objects.findIndex((obj) => obj.object.id === newObj.object.id);
  } else if ("frame_index" in newObj.object.data) {
    index = objects.findIndex(
      (obj) =>
        "frame_index" in obj.object.data &&
        "frame_index" in newObj.object.data && //required by tslint even if tested before
        obj.object.data.frame_index === newObj.object.data.frame_index &&
        obj.object.data.view_ref.id == newObj.object.data.view_ref.id &&
        obj.object.table_info.base_schema == newObj.object.table_info.base_schema,
    );
  }
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
    { [GROUND_TRUTH]: [], [PRE_ANNOTATION]: [] } as ObjectsSortedByModelType,
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
      console.log("XXX ToSave: update shape", newShape);
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
          states.push(vertex.features.state);
        }
        (object as Keypoints).data.coords = coords;
        (object as Keypoints).data.states = states;
        changed = true;
      }
      if (changed) {
        const save_item: SaveUpdate = {
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
): Annotation[] => {
  return objects
    .filter((object) => {
      if (object.datasetItemType === "image" && object.is_bbox) {
        const confidence = object.data.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      if (
        object.datasetItemType === "video" &&
        object.displayedMBox &&
        object.displayedMBox.length > 0
      ) {
        //TMP TODO for video object on several view, we take the first available view (?)
        const confidence = object.displayedMBox[0].confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      return false; // Ignore objects without bboxes
    })
    .sort((a, b) => {
      let firstBoxXPosition = 0;
      let secondBoxXPosition = 0;

      // Get first bbox position
      if (a.datasetItemType === "image" && a.is_bbox)
        firstBoxXPosition = (a as BBox).data.coords[0] || 0;
      if (a.datasetItemType === "video" && a.displayedMBox && a.displayedMBox.length > 0)
        firstBoxXPosition = a.displayedMBox[0].coords[0] || 0;

      // Get second bbox position
      if (b.datasetItemType === "image" && b.is_bbox)
        secondBoxXPosition = (b as BBox).data.coords[0] || 0;
      if (b.datasetItemType === "video" && b.displayedMBox && b.displayedMBox.length > 0)
        secondBoxXPosition = b.displayedMBox[0].coords[0] || 0;

      return firstBoxXPosition - secondBoxXPosition;
    });
};

export const mapObjectWithNewStatus = (
  allObjects: Annotation[],
  objectsToAnnotate: Annotation[],
  status: "accepted" | "rejected",
  features: ObjectProperties = {},
): Annotation[] => {
  const nextObjectId = objectsToAnnotate[1]?.id;
  return allObjects.map((object) => {
    if (object.id === nextObjectId) {
      object.highlighted = "self";
    } else {
      object.highlighted = "none";
    }
    if (object.id === objectsToAnnotate[0]?.id) {
      object.review_state = status;
      Object.keys(features || {}).forEach((key) => {
        if (object.features[key]) {
          object.features[key].value = features[key];
        }
      });
    }
    return object;
  });
};

export const createObjectCardId = (object: Annotation | Entity): string => `object-${object.id}`;

export const defineCreatedEntity = (
  shape: SaveShape,
  features: Record<string, ItemFeature>,
  //currentFrameIndex: number,
  dataset_schema: DatasetSchema,
): Entity => {
  let table = "";
  for (const entity_table of dataset_schema.groups.entities) {
    if (dataset_schema.schemas[entity_table].base_schema === "Entity") {
      //NOTE: if there is several entity tables, we could compare with "fields" to choose the correct one
      //but it shouldn't happen for entities
      table = entity_table;
      break;
    }
  }
  const now = new Date(Date.now()).toISOString();
  const entity = {
    id: nanoid(10),
    created_at: now,
    updated_at: now,
    table_info: { name: table, group: "entities", base_schema: "Entity" },
    data: {
      item_ref: { name: "item", id: shape.itemId },
      view_ref: shape.viewRef,
      parent_ref: { name: "", id: "" },
    },
  };
  for (const feat of Object.values(features)) {
    entity.data[feat.name] = feat.value;
  }
  return new Entity(entity);
};

export const defineCreatedObject = (
  entity: Entity,
  shape: SaveShape,
  videoType: DatasetItem["type"],
  features: Record<string, ItemFeature>,
  currentFrameIndex: number,
): Annotation => {
  const isVideo = videoType === "video";
  const now = new Date(Date.now()).toISOString();
  const baseAnn: Annotation = {
    id: nanoid(10),
    created_at: now,
    updated_at: now,
  };
  const baseData = {
    item_ref: entity.data.item_ref,
    view_ref: entity.data.view_ref,
    entity_ref: { name: entity.table_info.name, id: entity.id },
    source_ref: { name: GROUND_TRUTH, id: "" },
  };

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
    baseAnn.table_info = { name: "bbox", group: "annotations", base_schema: "BBox" }; //TODO name!!
    baseAnn.data = { ...baseData, ...bbox };
    const newBbox = new BBox(baseAnn);
    //BUG: need to put this after... zod do not accept
    newBbox.datasetItemType = isVideo ? "video" : "image";
    newBbox.features = features;
    newBbox.highlighted = "self";
    newBbox.displayControl = { editing: true };
    if (isVideo) {
      //TODO add tracklet
      // track: [
      //   {
      //     start: currentFrameIndex,
      //     end: currentFrameIndex + 5,
      //     id,
      //     view_id: shape.viewRef,
      //   },
      // ]
      newBbox.frame_index = currentFrameIndex;
    }

    return newBbox;
  }
  if (shape.type === "mask") {
    const mask: MaskType = {
      counts: shape.rle.counts,
      size: shape.rle.size,
    };
    baseAnn.table_info = { name: "mask", group: "annotations", base_schema: "CompressedRLE" }; //TODO name!!
    baseAnn.data = { ...baseData, ...mask };
    const newMask = new Mask(baseAnn);
    //BUG: need to put this after... zod do not accept
    newMask.datasetItemType = isVideo ? "video" : "image";
    newMask.features = features;
    newMask.highlighted = "self";
    newMask.displayControl = { editing: true };
    if (isVideo) {
      //TODO add tracklet
      // track: [
      //   {
      //     start: currentFrameIndex,
      //     end: currentFrameIndex + 5,
      //     id,
      //     view_id: shape.viewRef,
      //   },
      // ]
      newMask.frame_index = currentFrameIndex;
    }
    return newMask;
  }
  if (shape.type === "keypoints") {
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
    baseAnn.table_info = { name: "keypoints", group: "annotations", base_schema: "KeyPoints" }; //TODO name!!
    baseAnn.data = { ...baseData, ...keypoints };
    const newKPT = new Keypoints(baseAnn);
    //BUG: need to put this after... zod do not accept
    newKPT.datasetItemType = isVideo ? "video" : "image";
    newKPT.features = features;
    newKPT.highlighted = "self";
    newKPT.displayControl = { editing: true };
    if (isVideo) {
      //TODO add tracklet
      // track: [
      //   {
      //     start: currentFrameIndex,
      //     end: currentFrameIndex + 5,
      //     id,
      //     view_id: shape.viewRef,
      //   },
      // ]
      newKPT.frame_index = currentFrameIndex;
    }

    return newKPT;
  }
  //return newObject;
  //TMP WIP
  return baseAnn;
};

export const highlightCurrentObject = (
  objects: Annotation[],
  currentObject: Annotation,
  shouldUnHighlight: boolean = true,
) => {
  const isObjectHighlighted = currentObject.highlighted === "self";

  return objects.map((object) => {
    object.displayControl = {
      ...object.displayControl,
      editing: object.id === currentObject.id ? object.displayControl?.editing : false,
    };
    if (isObjectHighlighted && shouldUnHighlight) {
      object.highlighted = "all";
    } else if (object.id === currentObject.id) {
      object.highlighted = "self";
    } else {
      object.highlighted = "none";
    }
    return object;
  });
};

const findThumbnailBox = (boxes: Annotation) => {
  if (!boxes) return undefined;
  //return boxes.find((b) => b.is_thumbnail);
  //TMP
  return undefined;
};

export const defineObjectThumbnail = (metas: ItemsMeta, views: MView, object: Annotation) => {
  let box: BBox;
  const view_name = object.data.view_ref.name;
  if (object.datasetItemType === "video") {
    box = findThumbnailBox(object); //TODO ? which thumbnail in multiview cases ?
  } else {
    box = object;
  }
  if (!box || !box.is_bbox || !view_name) return null;
  //prevent bug: if thumbnail is asked before data are fully loaded, we can have a error on a bad key
  if (!(view_name in views)) return null;
  const view =
    metas.type === "video"
      ? (views[view_name] as SequenceFrame[])[(box as VideoItemBBox).frame_index]
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
