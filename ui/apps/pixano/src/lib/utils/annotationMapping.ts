/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  HIGHLIGHTED_BOX_STROKE_FACTOR,
  HIGHLIGHTED_MASK_STROKE_FACTOR,
  NOT_ANNOTATION_ITEM_OPACITY,
  PRE_ANNOTATION,
} from "$lib/constants/workspaceConstants";
import { sourcesStore } from "$lib/stores/appStores.svelte";
import {
  BaseSchema,
  WorkspaceType,
  type BBox,
  type Entity,
  type Keypoints,
  type Mask,
} from "$lib/types/dataset";
import type { Annotation } from "$lib/types/dataset";
import type { KeypointAnnotation } from "$lib/types/shapeTypes";
import type { EntityProperties, MView } from "$lib/types/workspace";
import { getTopEntity } from "$lib/utils/entityLookupUtils";
import { templates } from "$lib/utils/keyPointsTemplates";
import {
  generateSvgFromMaskRle,
  isPolygonPointsMetadata,
  isPolygonSvgMetadata,
} from "$lib/utils/maskUtils";
import { getDefaultDisplayFeat } from "$lib/utils/workspaceDefaultFeatures";

type CachedMaskSvg = {
  countsRef: Mask["data"]["counts"];
  height: number;
  width: number;
  svg: string[];
};
type HighlightState = "all" | "self" | "none";

const maskSvgCacheById = new Map<string, CachedMaskSvg>();

const getMaskSvgForDisplay = (mask: Mask, metadata: unknown): string[] => {
  if (isPolygonSvgMetadata(metadata)) {
    return metadata.polygon_svg;
  }

  const countsRef = mask.data.counts;
  const [height = 0, width = 0] = mask.data.size;
  const cached = maskSvgCacheById.get(mask.id);
  if (
    cached &&
    cached.countsRef === countsRef &&
    cached.height === height &&
    cached.width === width
  ) {
    return cached.svg;
  }

  const svg = generateSvgFromMaskRle(countsRef as number[], mask.data.size);
  maskSvgCacheById.set(mask.id, { countsRef, height, width, svg });
  return svg;
};

const isPreAnnotation = (source_id: string): boolean => {
  const source = sourcesStore.value.find((s) => s.id === source_id);
  return source?.data.name === PRE_ANNOTATION;
};

const defineTooltip = (bbox: BBox, entity: Entity): string | null => {
  if (!(bbox && bbox.is_type(BaseSchema.BBox))) return null;

  const source = sourcesStore.value.find((src) => src.id === bbox.data.source_id);

  const confidence =
    bbox.data.confidence !== 0.0 &&
    (!source || (source.data.kind !== "ground_truth" && source.data.name !== "Pixano"))
      ? bbox.data.confidence.toFixed(2)
      : null;

  const displayFeat = getDefaultDisplayFeat(entity);
  return displayFeat
    ? confidence
      ? displayFeat + " " + confidence
      : displayFeat
    : confidence
      ? confidence
      : "";
};

export const mapBBoxForDisplay = (
  bbox: BBox,
  views: MView,
  highlightedOverride?: HighlightState,
): BBox | undefined => {
  if (!bbox) return;
  if (!bbox.is_type(BaseSchema.BBox)) return;
  const effectiveHighlight = highlightedOverride ?? bbox.ui.displayControl.highlighted;
  if (bbox.ui.datasetItemType === WorkspaceType.VIDEO && bbox.ui.displayControl.hidden) return;
  if (isPreAnnotation(bbox.data.source_id) && effectiveHighlight !== "self") return;
  if (!bbox.data.view_name) return;
  let bbox_ui_coords = bbox.data.coords;
  if (bbox.data.format === "xyxy") {
    bbox_ui_coords = [
      bbox_ui_coords[0],
      bbox_ui_coords[1],
      bbox_ui_coords[2] - bbox_ui_coords[0],
      bbox_ui_coords[3] - bbox_ui_coords[1],
    ];
  }
  if (bbox.data.is_normalized) {
    const view = views[bbox.data.view_name];
    if (!view) return;
    const image = Array.isArray(view) ? view[0] : view;
    const imageHeight = image.data.height || 1;
    const imageWidth = image.data.width || 1;
    //TODO: manage correctly format -- here we will change user format if save
    bbox_ui_coords = [
      bbox_ui_coords[0] * imageWidth,
      bbox_ui_coords[1] * imageHeight,
      bbox_ui_coords[2] * imageWidth,
      bbox_ui_coords[3] * imageHeight,
    ];
  }
  const entity = getTopEntity(bbox);
  const tooltip = entity ? defineTooltip(bbox, entity) : "";

  return {
    ...bbox,
    data: {
      ...bbox.data,
      coords: bbox_ui_coords,
      format: "xywh",
    },
    ui: {
      ...bbox.ui,
      tooltip,
      displayControl: { ...bbox.ui.displayControl, highlighted: effectiveHighlight },
      opacity: effectiveHighlight === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
      strokeFactor: effectiveHighlight === "self" ? HIGHLIGHTED_BOX_STROKE_FACTOR : 1,
    },
  } as BBox;
};

export const mapKeypointsForDisplay = (
  keypoints: Keypoints,
  views: MView,
  highlightedOverride?: HighlightState,
): KeypointAnnotation | undefined => {
  if (
    !keypoints ||
    !keypoints.data.view_name ||
    (keypoints.ui.datasetItemType === WorkspaceType.VIDEO && keypoints.ui.displayControl.hidden)
  )
    return;
  const template = templates.find((t) => t.template_id === keypoints.data.template_id);
  if (!template) return;

  const view = views[keypoints.data.view_name];
  if (!view) return;
  const image = Array.isArray(view) ? view[0] : view;
  const imageHeight = image.data.height || 1;
  const imageWidth = image.data.width || 1;
  const effectiveHighlight = highlightedOverride ?? keypoints.ui.displayControl.highlighted;
  const displayControl = { ...keypoints.ui.displayControl, highlighted: effectiveHighlight };
  const vertices: Array<{ x: number; y: number }> = [];
  const vertexMetadata: KeypointAnnotation["vertexMetadata"] = [];
  for (let i = 0; i < keypoints.data.coords.length / 2; i++) {
    const x = keypoints.data.coords[i * 2] * imageWidth;
    const y = keypoints.data.coords[i * 2 + 1] * imageHeight;
    vertices.push({ x, y });
    vertexMetadata.push({
      ...(template.vertexMetadata[i] || { state: "visible", label: "", color: "" }),
      state: keypoints.data.states[i] as KeypointAnnotation["vertexMetadata"][number]["state"],
    });
  }
  const kptTemplate = {
    id: keypoints.id,
    template_id: keypoints.data.template_id,
    viewRef: { name: keypoints.data.view_name, id: keypoints.data.frame_id },
    entityRef: { name: "", id: keypoints.data.entity_id },
    graph: { vertices, edges: [...template.graph.edges] },
    vertexMetadata,
    ui: { ...keypoints.ui, displayControl },
    table_info: keypoints.table_info,
  } as KeypointAnnotation;
  if ("frame_index" in keypoints.ui) kptTemplate.ui.frame_index = keypoints.ui.frame_index;
  if ("top_entities" in keypoints.ui) kptTemplate.ui.top_entities = keypoints.ui.top_entities;
  return kptTemplate;
};

export const mapMaskForDisplay = (
  obj: Mask,
  highlightedOverride?: HighlightState,
): Mask | undefined => {
  if (
    obj.is_type(BaseSchema.Mask) &&
    obj.data.view_name &&
    !obj.ui.review_state &&
    !(isPreAnnotation(obj.data.source_id) && obj.ui.review_state === "accepted")
  ) {
    const metadata = obj.data.inference_metadata;
    const effectiveHighlight = highlightedOverride ?? obj.ui.displayControl.highlighted;

    const masksSVG = getMaskSvgForDisplay(obj, metadata);

    return {
      ...obj,
      data: obj.data,
      ui: {
        ...obj.ui,
        displayControl: { ...obj.ui.displayControl, highlighted: effectiveHighlight },
        svg: masksSVG,
        ...(isPolygonPointsMetadata(metadata) ? { rawPoints: metadata.polygon_points } : {}),
        opacity: effectiveHighlight === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
        strokeFactor: effectiveHighlight === "self" ? HIGHLIGHTED_MASK_STROKE_FACTOR : 1,
      },
    } as Mask;
  }
  return undefined;
};

export const mapAnnotationWithNewStatus = (
  allAnnotations: Annotation[],
  annotationsToReview: Annotation[],
  status: "accepted" | "rejected",
  features: EntityProperties = {}, // eslint-disable-line @typescript-eslint/no-unused-vars
): Annotation[] => {
  //TODO (preAnnotation)
  return allAnnotations;
};
