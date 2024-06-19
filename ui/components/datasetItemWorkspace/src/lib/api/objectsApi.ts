/**
 * @copyright CEA
 * @author CEA
 * @license CECILL
 *
 * This software is a collaborative computer program whose purpose is to
 * generate and explore labeled data for computer vision applications.
 * This software is governed by the CeCILL-C license under French law and
 * abiding by the rules of distribution of free software. You can use,
 * modify and/ or redistribute the software under the terms of the CeCILL-C
 * license as circulated by CEA, CNRS and INRIA at the following URL
 *
 * http://www.cecill.info
 */

// Imports
import type {
  ItemObject,
  ItemBBox,
  BBox,
  DisplayControl,
  Mask,
  DatasetItem,
  Shape,
  ItemView,
  SaveShape,
  ItemObjectBase,
  VideoItemBBox,
  KeypointsTemplate,
  VideoObject,
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
  ItemsMeta,
  ObjectProperties,
  ObjectsSortedByModelType,
} from "../types/datasetItemWorkspaceTypes";
import { DEFAULT_FEATURE } from "../settings/defaultFeatures";
import { nanoid } from "nanoid";
import { templates } from "../settings/keyPointsTemplates";

const defineTooltip = (object: ItemObject): string | null => {
  let bbox: ItemBBox | undefined;

  // Check object type to extract the bbox object
  if (object.datasetItemType === "image" && object.bbox) bbox = object.bbox;
  else if (object.datasetItemType === "video") {
    const displayedBox = object.displayedBox;
    bbox = displayedBox;
  }

  if (!bbox) return null;

  const confidence =
    bbox.confidence !== 0.0 && object.source_id !== GROUND_TRUTH
      ? " " + bbox.confidence.toFixed(2)
      : "";
  const tooltip =
    typeof object.features[DEFAULT_FEATURE]?.value === "string"
      ? object.features[DEFAULT_FEATURE]?.value + confidence
      : null;
  return tooltip;
};

export const mapObjectToBBox = (obj: ItemObject, views: DatasetItem["views"]): BBox | undefined => {
  const box = obj.datasetItemType === "video" ? obj.displayedBox : obj.bbox;
  if (!box || (obj.datasetItemType === "video" && box.displayControl?.hidden)) return;
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

export const mapObjectToMasks = (obj: ItemObject): Mask | undefined => {
  if (
    obj.datasetItemType === "image" && // Only images use masks ?
    obj.mask &&
    !obj.review_state &&
    !(obj.source_id === PRE_ANNOTATION && obj.review_state === "accepted")
  ) {
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
      visible: !obj.mask.displayControl?.hidden && !obj.displayControl?.hidden,
      editing: obj.displayControl?.editing ?? false, // Display control should exist, but we need a fallback value for linting purpose
      opacity: obj.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
      strokeFactor: obj.highlighted === "self" ? HIGHLIGHTED_MASK_STROKE_FACTOR : 1,
      highlighted: obj.highlighted,
    };
  }

  return undefined;
};

export const mapObjectToKeypoints = (
  object: ItemObject,
  views: DatasetItem["views"],
): KeypointsTemplate | undefined => {
  const keypoints =
    object.datasetItemType === "video" ? object.displayedKeypoints : object.keypoints;
  if (!keypoints || (object.datasetItemType === "video" && keypoints.displayControl?.hidden))
    return undefined;
  const template = templates.find((t) => t.id === keypoints?.template_id);
  if (!template) return undefined;
  const view = views?.[object.view_id];
  const image: ItemView = Array.isArray(view) ? view[0] : view;
  const imageHeight = (image.features.height.value as number) || 1;
  const imageWidth = (image.features.width.value as number) || 1;
  const vertices = keypoints.vertices.map((vertex, i) => ({
    ...vertex,
    x: vertex.x * imageWidth,
    y: vertex.y * imageHeight,
    features: {
      ...(template.vertices[i].features || {}),
      ...(vertex.features || {}),
    },
  }));
  return {
    id: object.id,
    vertices,
    edges: template.edges,
    editing: object.displayControl?.editing,
    visible: !keypoints.displayControl?.hidden && !object.displayControl?.hidden,
    highlighted: object.highlighted,
  };
};

export const toggleObjectDisplayControl = (
  object: ItemObject,
  displayControlProperty: keyof DisplayControl,
  properties: ("bbox" | "mask" | "keypoints")[],
  value: boolean,
): ItemObject => {
  // Check if the object is an ImageObject
  if (object.datasetItemType === "image") {
    if (properties.includes("bbox") && object.bbox) {
      object.bbox.displayControl = {
        ...object.bbox.displayControl,
        [displayControlProperty]: value,
      };
    }
    if (properties.includes("mask") && object.mask) {
      object.mask.displayControl = {
        ...object.mask.displayControl,
        [displayControlProperty]: value,
      };
    }
    if (properties.includes("keypoints") && object.keypoints) {
      object.keypoints.displayControl = {
        ...(object.keypoints.displayControl || {}),
        [displayControlProperty]: value,
      };
    }
    if (properties.includes("bbox") && properties.includes("mask")) {
      object.displayControl = {
        ...object.displayControl,
        [displayControlProperty]: value,
      };
    }
  }

  // Check if the object is a VideoObject
  if (object.datasetItemType === "video") {
    if (properties.includes("bbox")) {
      object.displayControl = {
        ...(object.displayControl || {}),
        [displayControlProperty]: value,
      };
    }
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

export const updateExistingObject = (objects: ItemObject[], newShape: Shape): ItemObject[] => {
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

    // Check if the object is an ImageObject
    if (object.datasetItemType === "image") {
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
      if (newShape.type === "keypoint" && object.keypoints) {
        return {
          ...object,
          keypoints: {
            ...object.keypoints,
            vertices: newShape.vertices,
          },
        };
      }
    }

    return object;
  });
};

export const getObjectsToPreAnnotate = (objects: ItemObject[]): ItemObject[] =>
  objects.filter((object) => object.source_id === PRE_ANNOTATION && !object.review_state);

export const sortAndFilterObjectsToAnnotate = (
  objects: ItemObject[],
  confidenceFilterValue: number[],
): ItemObject[] => {
  return objects
    .filter((object) => {
      if (object.datasetItemType === "image" && object.bbox) {
        const confidence = object.bbox.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      if (object.datasetItemType === "video" && object.displayedBox) {
        const confidence = object.displayedBox.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      return false; // Ignore objects without bboxes
    })
    .sort((a, b) => {
      let firstBoxXPosition = 0;
      let secondBoxXPosition = 0;

      // Get first bbox position
      if (a.datasetItemType === "image" && a.bbox) firstBoxXPosition = a.bbox.coords[0] || 0;
      if (a.datasetItemType === "video" && a.displayedBox)
        firstBoxXPosition = a.displayedBox.coords[0] || 0;

      // Get second bbox position
      if (b.datasetItemType === "image" && b.bbox) secondBoxXPosition = b.bbox.coords[0] || 0;
      if (b.datasetItemType === "video" && b.displayedBox)
        secondBoxXPosition = b.displayedBox.coords[0] || 0;

      return firstBoxXPosition - secondBoxXPosition;
    });
};

export const mapObjectWithNewStatus = (
  allObjects: ItemObject[],
  objectsToAnnotate: ItemObject[],
  status: "accepted" | "rejected",
  features: ObjectProperties = {},
): ItemObject[] => {
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

export const createObjectCardId = (object: ItemObject): string => `object-${object.id}`;

export const defineCreatedObject = (
  shape: SaveShape,
  videoType: DatasetItem["type"],
  features: ItemObjectBase["features"],
  currentFrameIndex: number,
) => {
  const isVideo = videoType === "video";
  let newObject: ItemObject | null = null;
  const baseObject = {
    id: nanoid(10),
    item_id: shape.itemId,
    source_id: GROUND_TRUTH,
    view_id: shape.viewId,
    features,
  };
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
    const isVideo = videoType === "video";
    if (isVideo) {
      const id = nanoid(5);
      newObject = {
        ...baseObject,
        highlighted: "self",
        displayControl: {
          editing: true,
        },
        datasetItemType: "video",
        displayedBox: { ...bbox, frame_index: 0, tracklet_id: id },
        boxes: [
          {
            ...bbox,
            frame_index: currentFrameIndex,
            is_key: true,
            is_thumbnail: true,
            tracklet_id: id,
          },
          { ...bbox, frame_index: currentFrameIndex + 5, is_key: true, tracklet_id: id },
        ],
        track: [
          {
            start: currentFrameIndex,
            end: currentFrameIndex + 5,
            id,
          },
        ],
      };
    } else {
      newObject = {
        ...baseObject,
        datasetItemType: "image",
        bbox,
      };
    }
  }
  if (shape.type === "mask") {
    newObject = {
      ...baseObject,
      datasetItemType: "image",
      mask: {
        counts: shape.rle.counts,
        size: shape.rle.size,
      },
    };
  }
  if (shape.type === "keypoint") {
    const keypoints = {
      template_id: shape.keypoints.id,
      vertices: shape.keypoints.vertices.map((vertex) => ({
        ...vertex,
        x: vertex.x / shape.imageWidth,
        y: vertex.y / shape.imageHeight,
      })),
    };
    if (isVideo) {
      const id = nanoid(5);
      newObject = {
        ...baseObject,
        datasetItemType: "video",
        keypoints: [
          {
            ...keypoints,
            frame_index: currentFrameIndex,
            tracklet_id: id,
            is_key: true,
            is_thumbnail: true,
          },
          { ...keypoints, frame_index: currentFrameIndex + 5, tracklet_id: id, is_key: true },
        ],
        track: [
          {
            start: currentFrameIndex,
            end: currentFrameIndex + 5,
            id,
          },
        ],
        displayedKeypoints: { ...keypoints, frame_index: 0, tracklet_id: id },
      };
    } else {
      newObject = {
        ...baseObject,
        datasetItemType: "image",
        keypoints,
      };
    }
  }
  return newObject;
};

export const highlightCurrentObject = (
  objects: ItemObject[],
  currentObject: ItemObject,
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

const findThumbnailBox = (boxes: VideoObject["boxes"]) => {
  if (!boxes) return undefined;
  const box = boxes.find((b) => b.is_thumbnail);
  return box;
};

export const defineObjectThumbnail = (metas: ItemsMeta, object: ItemObject) => {
  const box = object.datasetItemType === "video" ? findThumbnailBox(object.boxes) : object.bbox;
  if (!box) return null;
  const view =
    metas.type === "video"
      ? (metas.views[object.view_id] as ItemView[])[(box as VideoItemBBox).frame_index]
      : (metas.views[object.view_id] as ItemView);
  const coords = box.coords;
  return {
    baseImageDimensions: {
      width: view?.features.width.value as number,
      height: view?.features.height.value as number,
    },
    coords,
    uri: view?.uri,
  };
};
