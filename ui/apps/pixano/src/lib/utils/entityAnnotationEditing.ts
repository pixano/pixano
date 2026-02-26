/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { sourcesStore } from "$lib/stores/appStores.svelte";
import { annotations, newShape } from "$lib/stores/workspaceStores.svelte";
import { Annotation, WorkspaceType } from "$lib/types/dataset";
import { ShapeType, type EditShape, type Shape } from "$lib/types/shapeTypes";
import { getTopEntity, saveUpdatedWithPixanoSource } from "$lib/utils/entityLookupUtils";
import { applyEditedShapeDataToAnnotation } from "$lib/utils/entityOperations";
import { highlightEntity } from "$lib/utils/highlightOperations";

type SelectionShape = {
  status: EditShape["status"];
  type: EditShape["type"];
  highlighted?: EditShape["highlighted"];
  top_entity_id?: string;
  shapeId?: string;
};

export const tryHighlightSelectionShape = (
  shape: SelectionShape,
  objects: Annotation[],
): boolean => {
  const isSelectionOnlyHighlight =
    shape.status === "editing" && shape.type === ShapeType.none && shape.highlighted === "self";
  if (!isSelectionOnlyHighlight) return false;

  let targetEntityId = shape.top_entity_id ?? "";
  if (!targetEntityId && shape.shapeId) {
    const selectedAnnotation = objects.find((ann) => ann.id === shape.shapeId);
    if (selectedAnnotation) {
      targetEntityId = getTopEntity(selectedAnnotation).id;
    }
  }
  if (targetEntityId) {
    highlightEntity(targetEntityId, false);
  }
  return true;
};

/**
 * Applies a shape edit to annotations and resets the newShape state.
 * Shared across Image, EntityLinking, and VQA workspace variants.
 */
export const applyNewShapeEditing = (shape: Shape): void => {
  if (shape.status !== "editing") {
    newShape.value = { status: "none" };
    return;
  }

  if (tryHighlightSelectionShape(shape, annotations.value)) {
    newShape.value = { status: "none" };
    return;
  }

  annotations.update((objects) => updateExistingAnnotation(objects, shape));
  newShape.value = { status: "none" };
};

export const updateExistingAnnotation = (objects: Annotation[], shape: EditShape): Annotation[] => {
  if (tryHighlightSelectionShape(shape, objects)) {
    return objects;
  }

  if (shape.status === "editing" && !objects.find((ann) => ann.id === shape.shapeId) && shape.highlighted === "self") {
    // it is an interpolated object. Highlight anyway.
    if (shape.top_entity_id) highlightEntity(shape.top_entity_id, false);
    return objects;
  }

  return objects.map((ann) => {
    if (shape.status !== "editing") return ann;

    if (shape.highlighted === "all") {
      ann.ui.displayControl = {
        ...ann.ui.displayControl,
        highlighted: "all",
        editing: false,
      };
    }

    if (shape.highlighted === "self" && shape.shapeId === ann.id) {
      highlightEntity(getTopEntity(ann).id, false);
    }

    if (shape.shapeId !== ann.id || ann.ui.datasetItemType === WorkspaceType.VIDEO) {
      return ann;
    }

    if (!applyEditedShapeDataToAnnotation(ann, shape)) {
      return ann;
    }

    saveUpdatedWithPixanoSource(ann, sourcesStore);
    return ann;
  });
};
