/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Annotation, Entity, View } from "@pixano/core";

import { PRE_ANNOTATION } from "../../constants";

export type MView = Record<string, View | View[]>;

export const getObjectEntity = (ann: Annotation, entities: Entity[]): Entity | undefined => {
  return entities.find((entity) => entity.id === ann.data.entity_ref.id);
};

export const getObjectsToPreAnnotate = (objects: Annotation[]): Annotation[] =>
  objects.filter(
    (object) => object.data.source_ref.name === PRE_ANNOTATION && !object.ui.review_state,
  );

export * from "./addOrUpdateSaveItem";
export * from "./defineCreatedEntity";
export * from "./defineCreatedObject";
export * from "./defineObjectThumbnail";
export * from "./sortAndFilterObjectsToAnnotate";
export * from "./getPixanoSource";
export * from "./getTable";
export * from "./getTopEntity";
export * from "./highlightObject";
export * from "./mapObjectToBBox";
export * from "./mapObjectToKeypoints";
export * from "./mapObjectToMasks";
export * from "./mapObjectWithNewStatus";
export * from "./toggleObjectDisplayControl";
export * from "./updateExistingObject";
