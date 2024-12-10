/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Annotation, Entity, View } from "@pixano/core";

export type MView = Record<string, View | View[]>;

export const createObjectCardId = (object: Annotation | Entity): string => `object-${object.id}`;

export const getObjectEntity = (ann: Annotation, entities: Entity[]): Entity | undefined => {
  return entities.find((entity) => entity.id === ann.data.entity_ref.id);
};

export * from "./getPixanoSource";
export * from "./getTable";
export * from "./getTopEntity";
export * from "./mapObjectToKeypoints";
export * from "./mapObjectWithNewStatus";
export * from "./toggleObjectDisplayControl";
export * from "./getTopEntity";
export * from "./defineCreatedEntity";
export * from "./defineCreatedObject";
export * from "./defineObjectThumbnail";
export * from "./getPixanoSource";
export * from "./mapObjectToBBox";
export * from "./mapObjectToKeypoints";
export * from "./mapObjectWithNewStatus";
export * from "./toggleObjectDisplayControl";
export * from "./updateExistingObject";
export * from './mapObjectToMasks'
