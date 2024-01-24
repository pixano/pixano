import type { ItemObject, BBox, DisplayControl, Mask, DatasetItem, Shape } from "@pixano/core";
import { mask_utils } from "@pixano/models/src";

import {
  ANNOTATION_ITEM_STROKE_FACTOR,
  GROUND_TRUTH,
  MODEL_RUN,
  NOT_ANNOTATION_ITEM_OPACITY,
  PRE_ANNOTATION,
} from "../constants";
import type { ObjectsSortedByModelType } from "../types/imageWorkspaceTypes";
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
    strokeFactor: obj.highlighted === "self" ? ANNOTATION_ITEM_STROKE_FACTOR : 1,
  } as BBox;
};

export const mapObjectToMasks = (obj: ItemObject) => {
  if (!obj.mask) return;
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
    opacity: 1.0,
    isManual: !!obj.isManual,
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
      if (object.source_id === GROUND_TRUTH) {
        acc[GROUND_TRUTH] = [object, ...acc[GROUND_TRUTH]];
      } else {
        const modelAlreadyExists = acc[MODEL_RUN].some(
          (model) => model.modelName === object.source_id,
        );
        if (!modelAlreadyExists) {
          acc[MODEL_RUN] = [
            ...acc[MODEL_RUN],
            {
              modelName: object.source_id,
              objects: [object],
            },
          ];
        }
        if (modelAlreadyExists) {
          acc[MODEL_RUN] = acc[MODEL_RUN].map((model) => {
            if (model.modelName === object.source_id) {
              return {
                ...model,
                objects: [...model.objects, object],
              };
            }
            return model;
          });
        }
      }
      acc[PRE_ANNOTATION] = acc[MODEL_RUN][0]?.objects || [];
      return acc;
    },
    { [GROUND_TRUTH]: [], [MODEL_RUN]: [], [PRE_ANNOTATION]: [] } as ObjectsSortedByModelType,
  );

export const updateExistingObject = (old: ItemObject[], newShape: Shape) =>
  old.map((object) => {
    if (newShape?.status !== "editing") return object;
    if (newShape.type === "mask" && object.id === newShape.maskId && object.mask) {
      return {
        ...object,
        mask: {
          ...object.mask,
          counts: newShape.counts,
        },
      };
    }
    if (newShape.type === "rectangle" && object.id === newShape.rectangleId && object.bbox) {
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
