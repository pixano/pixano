import type { ItemObject, BBox, DisplayControl, Mask, DatasetItem, Shape } from "@pixano/core";
import { mask_utils } from "@pixano/models/src";

import {
  HIGHLIGHTED_BOX_STROKE_FACTOR,
  GROUND_TRUTH,
  NOT_ANNOTATION_ITEM_OPACITY,
  PRE_ANNOTATION,
  HIGHLIGHTED_MASK_STROKE_FACTOR,
} from "../constants";
import type { ObjectProperties, ObjectsSortedByModelType } from "../types/imageWorkspaceTypes";
import { DEFAULT_FEATURE } from "../settings/defaultFeatures";

const defineTooltip = (object: ItemObject) => {
  if (!object.bbox) return null;
  const confidence =
    object.bbox.confidence != 0.0 && object.source_id !== GROUND_TRUTH
      ? " " + object.bbox.confidence.toFixed(2)
      : "";
  const tooltip =
    typeof object.features[DEFAULT_FEATURE]?.value == "string"
      ? object.features[DEFAULT_FEATURE]?.value + confidence
      : null;
  return tooltip;
};

export const mapObjectToBBox = (obj: ItemObject, views: DatasetItem["views"]) => {
  if (!obj.bbox) return;
  if (obj.source_id === PRE_ANNOTATION && obj.highlighted !== "self") return;
  const imageHeight = (views?.[obj.view_id]?.features.height.value as number) || 1;
  const imageWidth = (views?.[obj.view_id]?.features.width.value as number) || 1;
  const x = obj.bbox.coords[0] * imageWidth;
  const y = obj.bbox.coords[1] * imageHeight;
  const w = obj.bbox.coords[2] * imageWidth;
  const h = obj.bbox.coords[3] * imageHeight;
  const tooltip = defineTooltip(obj);
  return {
    id: obj.id,
    viewId: obj.view_id,
    catId: (obj.features.category_id?.value || 1) as number,
    bbox: [x, y, w, h],
    tooltip,
    opacity: obj.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
    visible: !obj.bbox.displayControl?.hidden,
    editing: obj.displayControl?.editing,
    locked: obj.displayControl?.locked,
    strokeFactor: obj.highlighted === "self" ? HIGHLIGHTED_BOX_STROKE_FACTOR : 1,
    highlighted: obj.highlighted,
  } as BBox;
};

export const mapObjectToMasks = (obj: ItemObject) => {
  if (
    !obj.mask ||
    obj.review_state ||
    (obj.source_id === PRE_ANNOTATION && obj.review_state === "accepted")
  )
    return;
  const rle = obj.mask.counts;
  const size = obj.mask.size;
  const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
  const masksSVG = mask_utils.convertSegmentsToSVG(maskPoly);

  return {
    id: obj.id,
    viewId: obj.view_id,
    svg: masksSVG,
    rle: obj.mask,
    catId: (obj.features.category_id?.value || 1) as number,
    visible: !obj.mask.displayControl?.hidden,
    editing: obj.displayControl?.editing,
    opacity: obj.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
    strokeFactor: obj.highlighted === "self" ? HIGHLIGHTED_MASK_STROKE_FACTOR : 1,
    highlighted: obj.highlighted,
  } as Mask;
};

export const toggleObjectDisplayControl = (
  object: ItemObject,
  displayControlProperty: keyof DisplayControl,
  properties: ("bbox" | "mask")[],
  value: boolean,
) => {
  if (properties.includes("bbox")) {
    if (object.bbox) {
      object.bbox.displayControl = {
        ...object.bbox.displayControl,
        [displayControlProperty]: value,
      };
    }
  }
  if (properties.includes("mask")) {
    if (object.mask) {
      object.mask.displayControl = {
        ...object.mask.displayControl,
        [displayControlProperty]: value,
      };
    }
  }
  if (properties.includes("bbox") && properties.includes("mask")) {
    object.displayControl = {
      ...object.displayControl,
      [displayControlProperty]: value,
    };
  }
  return object;
};

export const sortObjectsByModel = (objects: ItemObject[]) =>
  objects.reduce(
    (acc, object) => {
      if (object.source_id === PRE_ANNOTATION) {
        if (!object.review_state) acc[PRE_ANNOTATION] = [object, ...acc[PRE_ANNOTATION]];
        return acc;
      }
      acc[object.source_id] = [object, ...(acc[object.source_id] || [])];
      return acc;
    },
    { [GROUND_TRUTH]: [], [PRE_ANNOTATION]: [] } as ObjectsSortedByModelType,
  );

export const updateExistingObject = (old: ItemObject[], newShape: Shape) => {
  return old.map((object) => {
    if (newShape?.status !== "editing") return object;
    if (newShape.highlighted === "all") {
      object.highlighted = "all";
    }
    if (newShape.highlighted === "self") {
      object.highlighted = newShape.shapeId === object.id ? "self" : "none";
    }
    if (newShape.type === "mask" && object.mask) {
      return {
        ...object,
        mask: {
          ...object.mask,
          counts: newShape.counts,
        },
      };
    }
    if (newShape.type === "rectangle" && object.bbox) {
      return {
        ...object,
        bbox: {
          ...object.bbox,
          coords: newShape.coords,
        },
      };
    }
    return object;
  });
};

export const getObjectsToPreAnnotate = (objects: ItemObject[]) =>
  objects.filter((object) => object.source_id === PRE_ANNOTATION && !object.review_state);

export const sortAndFilterObjectsToAnnotate = (
  objects: ItemObject[],
  confidenceFilterValue: number[],
) =>
  objects
    .filter((object) => {
      const confidence = object.bbox?.confidence || 0;
      return confidence >= confidenceFilterValue[0];
    })
    .sort((a, b) => {
      const firstBoxXPosition = a.bbox?.coords[0] || 0;
      const secondBoxXPosition = b.bbox?.coords[0] || 0;
      return firstBoxXPosition - secondBoxXPosition;
    });

export const mapObjectWithNewStatus = (
  allObjects: ItemObject[],
  objectsToAnnotate: ItemObject[],
  status: "accepted" | "rejected",
  features: ObjectProperties = {},
) => {
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

export const createObjectCardId = (object: ItemObject) => `object-${object.id}`;
