import type {
  ItemObject,
  BBox,
  DisplayControl,
  Mask,
  DatasetItem,
  Shape,
  ItemView,
  SaveShape,
  ItemObjectBase,
  ItemRLE,
  PolygonGroupPoint,
  MaskPoints,
  MaskSVG,
  ItemBBox,
} from "@pixano/core";
import { mask_utils } from "@pixano/models/src";

import {
  HIGHLIGHTED_BOX_STROKE_FACTOR,
  GROUND_TRUTH,
  NOT_ANNOTATION_ITEM_OPACITY,
  PRE_ANNOTATION,
  HIGHLIGHTED_MASK_STROKE_FACTOR,
} from "../constants";
import type {
  ObjectProperties,
  ObjectsSortedByModelType,
} from "../types/datasetItemWorkspaceTypes";
import { DEFAULT_FEATURE } from "../settings/defaultFeatures";
import { nanoid } from "nanoid";
import { parseSvgPath } from "@pixano/canvas2d/src/api/maskApi";

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
  const box = obj.datasetItemType === "video" ? obj.displayedFrame?.bbox : obj.bbox;

  if (!box || (obj.datasetItemType === "video" && obj.displayedFrame?.hidden)) return;
  if (obj.source_id === PRE_ANNOTATION && obj.highlighted !== "self") return;
  const view = views?.[obj.view_id];
  const image: ItemView = Array.isArray(view) ? view[0] : view;
  const imageHeight = (image.features.height.value as number) || 1;
  const imageWidth = (image.features.width.value as number) || 1;
  const [x, y, width, height] = box.coords;
  const bbox = [x * imageWidth, y * imageHeight, width * imageWidth, height * imageHeight];

  const tooltip = defineTooltip(obj);

  return {
    id: obj.id,
    viewId: obj.view_id,
    catId: (obj.features.category_id?.value || 1) as number,
    bbox,
    tooltip,
    opacity: obj.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
    visible: !box.displayControl?.hidden && !obj.displayControl?.hidden,
    editing: obj.displayControl?.editing,
    strokeFactor: obj.highlighted === "self" ? HIGHLIGHTED_BOX_STROKE_FACTOR : 1,
    highlighted: obj.highlighted,
  } as BBox;
};

export const convertMaskCountToPoints = (mask: ItemRLE): [MaskSVG, MaskPoints] => {
  const rle = mask.counts;
  const size = mask.size;
  const maskPoly = mask_utils.generatePolygonSegments(rle, size[0]);
  const svg = mask_utils.convertSegmentsToSVG(maskPoly);
  const points = svg.reduce((acc, val) => [...acc, parseSvgPath(val)], [] as PolygonGroupPoint[][]);
  return [svg, points];
};

export const mapObjectToMasks = (obj: ItemObject) => {
  const mask = obj.datasetItemType === "video" ? obj.displayedFrame?.mask : obj.mask;
  if (
    !mask ||
    obj.review_state ||
    (obj.source_id === PRE_ANNOTATION && obj.review_state === "accepted")
  )
    return;

  const [svg] = convertMaskCountToPoints(mask);

  return {
    id: obj.id,
    viewId: obj.view_id,
    svg,
    rle: obj.mask,
    catId: (obj.features.category_id?.value || 1) as number,
    visible: !mask.displayControl?.hidden && !obj.displayControl?.hidden,
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
    if (newShape.shapeId !== object.id) return object;
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

const createObjectFromShape = (
  baseObject: Pick<ItemObject, "item_id" | "source_id" | "view_id" | "features" | "id">,
  isVideo: boolean,
  trackItem: { bbox?: ItemBBox; mask?: ItemRLE },
  lastFrameIndex: number,
): ItemObject => {
  if (isVideo) {
    return {
      ...baseObject,
      datasetItemType: "video",
      track: [
        {
          start: 0,
          end: lastFrameIndex,
          keyFrames: [
            { ...trackItem, frameIndex: 0 },
            { ...trackItem, frameIndex: lastFrameIndex },
          ],
        },
      ],
      displayedFrame: { ...trackItem, frameIndex: 0 },
    };
  } else {
    return {
      ...baseObject,
      ...trackItem,
      datasetItemType: "image",
    };
  }
};

export const defineCreatedObject = (
  shape: SaveShape,
  datasetItemType: DatasetItem["type"],
  features: ItemObjectBase["features"],
  lastFrameIndex: number,
) => {
  let newObject: ItemObject | null = null;
  const baseObject = {
    id: nanoid(10),
    item_id: shape.itemId,
    source_id: GROUND_TRUTH,
    view_id: shape.viewId,
    features,
  };
  const isVideo = datasetItemType === "video";
  if (shape.type === "rectangle") {
    const { x, y, width, height } = shape.attrs;
    const coords = [
      x / shape.imageWidth,
      y / shape.imageHeight,
      width / shape.imageWidth,
      height / shape.imageHeight,
    ];
    const bbox = {
      coords,
      format: "xywh",
      is_normalized: true,
      confidence: 1,
    };
    newObject = createObjectFromShape(baseObject, isVideo, { bbox }, lastFrameIndex);
  }
  if (shape.type === "mask") {
    const mask = {
      counts: shape.rle.counts,
      size: shape.rle.size,
    };
    newObject = createObjectFromShape(baseObject, isVideo, { mask }, lastFrameIndex);
  }
  return newObject;
};
