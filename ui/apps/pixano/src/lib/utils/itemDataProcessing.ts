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
  DatasetItem,
  Entity,
  initDisplayControl,
  isSequenceFrameArray,
  Mask,
  Track,
  isVideoEntity,
  WorkspaceType,
  type BBoxData,
  type FeaturesValues,
  type SaveItem,
  type SequenceFrame,
  type View,
} from "$lib/types/dataset";
import { getBoundingBoxFromMaskSvgPaths, rleFrString, isPolygonSvgMetadata, generateSvgFromMaskRle } from "$lib/utils/maskUtils";
import { nowTimestamp } from "$lib/utils/coreUtils";
import { sortByFrameIndex } from "$lib/utils/videoUtils";

/**
 * Prepare a single annotation for front-end display.
 * Unpacks mask RLE, generates SVG polygons, and attaches frame indices for video.
 */
function prepareAnnotation(
  ann: Annotation,
  workspaceType: WorkspaceType,
  views: Record<string, View | View[]>,
): Annotation {
  ann.ui = { datasetItemType: workspaceType, displayControl: initDisplayControl };

  if (ann.table_info.base_schema === BaseSchema.Mask) {
    const mask: Mask = ann as Mask;
    // Unpack Compressed RLE to uncompressed RLE
    if (typeof mask.data.counts === "string") mask.data.counts = rleFrString(mask.data.counts);
    const metadata = mask.data.inference_metadata as Record<string, unknown>;
    if (!mask.ui.svg) {
      if (isPolygonSvgMetadata(metadata)) {
        mask.ui.svg = metadata.polygon_svg;
      } else {
        mask.ui.svg = generateSvgFromMaskRle(mask.data.counts as number[], mask.data.size);
      }
    }
  }

  if (workspaceType === WorkspaceType.VIDEO) {
    if (ann.table_info.base_schema !== BaseSchema.Tracklet) {
      const mediaView = views[ann.data.view_ref.name];
      if (Array.isArray(mediaView)) {
        const seqframe = (mediaView as SequenceFrame[]).find((sf) => sf.id === ann.data.view_ref.id);
        if (seqframe?.data.frame_index !== undefined) {
          ann.ui.frame_index = seqframe.data.frame_index;
        }
      }
    }
  }

  return ann;
}

/**
 * Auto-generate missing bounding boxes for masks that lack them.
 * Returns the new bboxes and corresponding save items (pure — no store mutation).
 */
function generateMissingBBoxes(
  annotations: Annotation[],
  annotationTables: string[],
): { generatedBBoxes: BBox[]; generatedSaveItems: SaveItem[] } {
  const generatedBBoxes: BBox[] = [];
  const generatedSaveItems: SaveItem[] = [];

  const bboxTableNames = annotationTables.filter((name) => name.toLowerCase().includes("bbox"));
  const defaultBBoxTable = bboxTableNames.length > 0 ? bboxTableNames[0] : null;

  for (const ann of annotations) {
    if (ann.is_type(BaseSchema.Mask)) {
      const mask = ann as Mask;
      const hasBBox = annotations.some(
        (other) =>
          other.is_type(BaseSchema.BBox) &&
          other.data.entity_ref.id === mask.data.entity_ref.id &&
          other.data.view_ref.id === mask.data.view_ref.id &&
          other.data.view_ref.name === mask.data.view_ref.name,
      );

      if (!hasBBox) {
        const bboxCoords = getBoundingBoxFromMaskSvgPaths(mask.ui.svg);
        if (bboxCoords) {
          const now = nowTimestamp();
          const bboxData: BBoxData = {
            item_ref: mask.data.item_ref,
            view_ref: mask.data.view_ref,
            entity_ref: mask.data.entity_ref,
            source_ref: mask.data.source_ref,
            inference_metadata: {},
            coords: [bboxCoords.x, bboxCoords.y, bboxCoords.width, bboxCoords.height],
            format: "xywh",
            is_normalized: false,
            confidence: 1,
          };

          const newBBox = new BBox({
            id: nanoid(10),
            created_at: now,
            updated_at: now,
            table_info: {
              name: defaultBBoxTable || mask.table_info.name.replace("mask", "bbox"),
              group: "annotations",
              base_schema: BaseSchema.BBox,
            },
            data: bboxData,
          });
          newBBox.ui = {
            datasetItemType: mask.ui.datasetItemType,
            displayControl: { ...initDisplayControl, highlighted: "none" },
            frame_index: mask.ui.frame_index,
          };
          generatedBBoxes.push(newBBox);
          generatedSaveItems.push({ change_type: "add", data: newBBox });
        }
      }
    }
  }

  return { generatedBBoxes, generatedSaveItems };
}

/**
 * Build entity hierarchy: attach child annotations to entities, and gather
 * sub-entity children for parent tracks.
 */
function buildEntityHierarchy(
  selectedItem: DatasetItem,
  processedAnnotations: Annotation[],
): Entity[] {
  let newEntities: Entity[] = [];
  const subEntitiesChilds: Record<string, Annotation[]> = {};

  for (const itemEntities of Object.values(selectedItem.entities)) {
    for (const entity of itemEntities) {
      entity.ui = {
        ...entity.ui,
        childs: processedAnnotations.filter((ann) => ann.data.entity_ref.id === entity.id),
      };
      newEntities.push(entity);
      if (entity.data.parent_ref.id !== "" && entity.ui.childs) {
        if (entity.data.parent_ref.id in subEntitiesChilds) {
          subEntitiesChilds[entity.data.parent_ref.id] = subEntitiesChilds[
            entity.data.parent_ref.id
          ].concat(entity.ui.childs);
        } else {
          subEntitiesChilds[entity.data.parent_ref.id] = entity.ui.childs;
        }
      }
    }
  }

  if (Object.keys(subEntitiesChilds).length > 0) {
    newEntities = newEntities.map((entity) => {
      if (isVideoEntity(entity) && entity.id in subEntitiesChilds) {
        entity.ui.childs = [...entity.ui.childs!, ...subEntitiesChilds[entity.id]];
      }
      return entity;
    });
  }

  return newEntities;
}

/**
 * Attach tracklet children and top entities to annotations.
 * Must be called after entities are set in the store (uses getTopEntity which reads the store).
 */
export function attachTrackChildren(
  anns: Annotation[],
  getTopEntity: (ann: Annotation) => Entity,
): Annotation[] {
  return anns.map((ann) => {
    const topEntity = getTopEntity(ann);
    if (ann.is_type(BaseSchema.Tracklet)) {
      const track = ann as Track;
      if (topEntity) {
        track.ui.childs =
          topEntity.ui.childs?.filter(
            (child) =>
              child.ui.frame_index !== undefined &&
              child.ui.frame_index <= track.data.end_timestep &&
              child.ui.frame_index >= track.data.start_timestep &&
              child.data.view_ref.name === track.data.view_ref.name,
          ) || [];
        track.ui.childs.sort((a, b) => a.ui.frame_index! - b.ui.frame_index!);
      }
    }
    return ann;
  });
}

/**
 * Compute video speed from views (time between frames).
 */
function computeVideoSpeed(
  views: Record<string, View | View[]>,
): number | undefined {
  for (const view in views) {
    if (isSequenceFrameArray(views[view])) {
      const video = views[view] as SequenceFrame[];
      return Math.round(
        (video[video.length - 1].data.timestamp - video[0].data.timestamp) / video.length,
      );
    }
  }
  return undefined;
}

interface ProcessedItemData {
  annotations: Annotation[];
  entities: Entity[];
  generatedBBoxes: BBox[];
  generatedSaveItems: SaveItem[];
  videoSpeed: number | undefined;
}

/**
 * Top-level orchestrator: processes a DatasetItem into front-end-ready data.
 * Pure function — no store mutations.
 */
export function processDatasetItem(
  selectedItem: DatasetItem,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  featureValues: FeaturesValues,
): ProcessedItemData {
  const workspaceType = selectedItem.ui.type;

  // Compute video speed
  const videoSpeed = computeVideoSpeed(selectedItem.views);

  // Prepare all annotations
  const newAnns: Annotation[] = [];
  for (const anns of Object.values(selectedItem.annotations)) {
    for (const ann of anns) {
      newAnns.push(prepareAnnotation(ann, workspaceType, selectedItem.views));
    }
  }

  // Generate missing bboxes
  const annotationTables = Object.keys(selectedItem.annotations);
  const { generatedBBoxes, generatedSaveItems } = generateMissingBBoxes(
    newAnns,
    annotationTables,
  );

  if (generatedBBoxes.length > 0) {
    newAnns.push(...generatedBBoxes);
  }

  // Sort by frame_index
  newAnns.sort((a, b) => sortByFrameIndex(a, b));

  // Build entity hierarchy
  const entities = buildEntityHierarchy(selectedItem, newAnns);

  return {
    annotations: newAnns,
    entities,
    generatedBBoxes,
    generatedSaveItems,
    videoSpeed,
  };
}
