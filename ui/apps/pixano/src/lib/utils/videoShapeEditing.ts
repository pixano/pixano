/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, BBox, Keypoints, type Annotation, type SaveItem } from "$lib/types/dataset";
import { ShapeType, type EditShape } from "$lib/types/shapeTypes";
import { applyPixanoSourceFields } from "$lib/utils/entityLookupUtils";
import { applyEditedShapeDataToAnnotation } from "$lib/utils/entityOperations";
import { verticesToCoordsAndStates } from "$lib/utils/keypointsUtils";

/**
 * Edit or create an annotation within a tracklet.
 *
 * If `shape.shapeId` refers to an existing annotation the coords are updated
 * in-place. Otherwise the shape is assumed to be an interpolated ghost — we
 * clone the reference annotation and materialise a new one at the current
 * frame.
 */
export function editKeyItemInTracklet(
  allAnnotations: Annotation[],
  shape: EditShape,
  currentFrame: number,
  currentBBoxes: BBox[],
  currentKeypoints: {
    id: string;
    ui?: { startRef?: { id: string } };
    viewRef: { name: string; id: string };
  }[],
): { objects: Annotation[]; save_data: SaveItem } {
  let saveData: SaveItem;
  let updatedAnnotations: Annotation[];

  const existingAnn = allAnnotations.find((ann) => ann.id === shape.shapeId);

  if (existingAnn) {
    if (existingAnn.is_type(BaseSchema.Mask)) {
      // mask not implemented yet in video
    } else if (!applyEditedShapeDataToAnnotation(existingAnn, shape)) {
      console.error(
        `ERROR: mismatching types ${shape.type} & ${existingAnn.table_info.base_schema}`,
      );
    }
    applyPixanoSourceFields(existingAnn);
    updatedAnnotations = allAnnotations.map((ann) =>
      ann.id === existingAnn.id ? existingAnn : ann,
    );
    saveData = { change_type: "update", data: existingAnn };
  } else {
    // Updated an interpolated annotation: create it using the start ref as base
    let newAnn: Annotation | undefined = undefined;

    if (shape.type === ShapeType.bbox) {
      const interpolatedBox = currentBBoxes.find((box) => box.id === shape.shapeId);
      const sourceBBox = interpolatedBox?.ui?.startRef;
      if (interpolatedBox && sourceBBox) {
        newAnn = BBox.cloneForFrame(sourceBBox, {
          id: shape.shapeId,
          coords: shape.coords,
          view_name: shape.viewRef.name,
          frame_id: shape.viewRef.id,
          frame_index: currentFrame,
        });
        newAnn.data.tracklet_id = sourceBBox.data.tracklet_id;
      }
    } else if (shape.type === ShapeType.keypoints) {
      const interpolatedKpt = currentKeypoints.find((kpt) => kpt.id === shape.shapeId);
      if (interpolatedKpt?.ui?.startRef) {
        const keypointRef = allAnnotations.find(
          (ann) => ann.is_type(BaseSchema.Keypoints) && ann.id === interpolatedKpt.ui?.startRef?.id,
        ) as Keypoints;
        if (keypointRef) {
          const { coords, states } = verticesToCoordsAndStates(shape.vertices);
          newAnn = Keypoints.cloneForFrame(keypointRef, {
            id: shape.shapeId,
            coords,
            states,
            view_name: shape.viewRef.name,
            frame_id: shape.viewRef.id,
            frame_index: currentFrame,
          });
          newAnn.data.tracklet_id = keypointRef.data.tracklet_id;
        }
      }
    } else if (
      shape.type === ShapeType.mask ||
      shape.type === ShapeType.polygon ||
      shape.type === ShapeType.polyline
    ) {
      // mask / polygon / polyline not implemented yet in video
    }

    if (!newAnn) {
      throw new Error("Masks are not managed yet in video!");
    }

    applyPixanoSourceFields(newAnn);
    updatedAnnotations = [...allAnnotations, newAnn];
    saveData = { change_type: "add", data: newAnn };
  }

  return { objects: updatedAnnotations, save_data: saveData };
}
