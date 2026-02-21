/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, WorkspaceType, type BBox, type Entity, type Keypoints, type Mask, type Source } from "$lib/types/dataset";
import type { KeypointAnnotation } from "$lib/types/shapeTypes";
import { sourcesStore } from "$lib/stores/appStores.svelte";
import { isPolygonSvgMetadata, isPolygonPointsMetadata, generateSvgFromMaskRle } from "$lib/utils/maskUtils";

import {
  HIGHLIGHTED_BOX_STROKE_FACTOR,
  HIGHLIGHTED_MASK_STROKE_FACTOR,
  NOT_ANNOTATION_ITEM_OPACITY,
  PRE_ANNOTATION,
} from "$lib/constants/workspaceConstants";
import { getDefaultDisplayFeat } from "$lib/utils/workspaceDefaultFeatures";
import { templates } from "$lib/utils/keyPointsTemplates";
import type { MView, EntityProperties } from "$lib/types/workspace";
import { getTopEntity } from "$lib/utils/entityLookupUtils";
import type { Annotation } from "$lib/types/dataset";

const defineTooltip = (bbox: BBox, entity: Entity): string | null => {
  if (!(bbox && bbox.is_type(BaseSchema.BBox))) return null;

  const source = (sourcesStore.value as Source[]).find((src) => src.id === bbox.data.source_ref.id);

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

export const mapBBoxForDisplay = (bbox: BBox, views: MView): BBox | undefined => {
  if (!bbox) return;
  if (!bbox.is_type(BaseSchema.BBox)) return;
  if (bbox.ui.datasetItemType === WorkspaceType.VIDEO && bbox.ui.displayControl.hidden) return;
  if (bbox.data.source_ref.name === PRE_ANNOTATION && bbox.ui.displayControl.highlighted !== "self")
    return;
  if (!bbox.data.view_ref.name) return;
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
    const view = views[bbox.data.view_ref.name];
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
      opacity: bbox.ui.displayControl.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
      strokeFactor:
        bbox.ui.displayControl.highlighted === "self" ? HIGHLIGHTED_BOX_STROKE_FACTOR : 1,
    },
  } as BBox;
};

export const mapKeypointsForDisplay = (
  keypoints: Keypoints,
  views: MView,
): KeypointAnnotation | undefined => {
  if (
    !keypoints ||
    !keypoints.data.view_ref.name ||
    (keypoints.ui.datasetItemType === WorkspaceType.VIDEO && keypoints.ui.displayControl.hidden)
  )
    return;
  const template = templates.find((t) => t.template_id === keypoints.data.template_id);
  if (!template) return;

  const view = views[keypoints.data.view_ref.name];
  if (!view) return;
  const image = Array.isArray(view) ? view[0] : view;
  const imageHeight = image.data.height || 1;
  const imageWidth = image.data.width || 1;
  const vertices = [];
  const vertexMetadata = [];
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
    viewRef: keypoints.data.view_ref,
    entityRef: keypoints.data.entity_ref,
    graph: { vertices, edges: [...template.graph.edges] },
    vertexMetadata,
    ui: keypoints.ui,
    table_info: keypoints.table_info,
  } as KeypointAnnotation;
  if ("frame_index" in keypoints.ui) kptTemplate.ui!.frame_index = keypoints.ui.frame_index;
  if ("top_entities" in keypoints.ui) kptTemplate.ui!.top_entities = keypoints.ui.top_entities;
  return kptTemplate;
};

export const mapMaskForDisplay = (obj: Mask): Mask | undefined => {
  if (
    obj.is_type(BaseSchema.Mask) &&
    obj.data.view_ref.name &&
    !obj.ui.review_state &&
    !(obj.data.source_ref.name === PRE_ANNOTATION && obj.ui.review_state === "accepted")
  ) {
    const metadata = obj.data.inference_metadata as Record<string, unknown>;

    const masksSVG = isPolygonSvgMetadata(metadata)
      ? metadata.polygon_svg
      : generateSvgFromMaskRle(obj.data.counts as number[], obj.data.size);

    return {
      ...obj,
      data: obj.data,
      ui: {
        ...obj.ui,
        svg: masksSVG,
        ...(isPolygonPointsMetadata(metadata) ? { rawPoints: metadata.polygon_points } : {}),
        opacity: obj.ui.displayControl.highlighted === "none" ? NOT_ANNOTATION_ITEM_OPACITY : 1.0,
        strokeFactor:
          obj.ui.displayControl.highlighted === "self" ? HIGHLIGHTED_MASK_STROKE_FACTOR : 1,
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
