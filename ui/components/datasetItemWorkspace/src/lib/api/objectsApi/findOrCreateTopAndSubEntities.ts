/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { get } from "svelte/store";

import {
  BaseSchema,
  Entity,
  type DS_NamedSchema,
  type ItemFeature,
  type SaveShape,
} from "@pixano/core";

import { datasetSchema } from "../../../../../../apps/pixano/src/lib/stores/datasetStores";
import { entities } from "../../stores/datasetItemWorkspaceStores";
import { defineCreatedEntity } from "./defineCreatedEntity";

export const findOrCreateSubAndTopEntities = (
  selectedEntityId: string,
  shape: SaveShape,
  features: Record<string, Record<string, ItemFeature>>,
): {
  topEntity: Entity;
  subEntity: Entity | undefined;
} => {
  //Manage sub-entity: check if there is some subentity table(s)
  //if so, choose the correct one, and separate topEntity from subEntity ...
  //TMP: we should rely on "table relations" from get(datasetSchema), but it's not available yet
  //TMP: so, we will make the assumption that the only case with subentity is : 1 Track + 1 Entity (sub)
  //TMP: -> we take trackSchemas[0] and entitySchemas[0]
  let topEntity: Entity | undefined = undefined;
  let subEntity: Entity | undefined = undefined;
  let topEntitySchema: DS_NamedSchema | undefined = undefined;
  let subEntitySchema: DS_NamedSchema | undefined = undefined;
  const entitySchemas: DS_NamedSchema[] = [];
  const trackSchemas: DS_NamedSchema[] = [];
  const multiModalSchemas: DS_NamedSchema[] = [];
  Object.entries(get(datasetSchema)?.schemas ?? {}).forEach(([name, sch]) => {
    if (sch.base_schema === BaseSchema.Track) {
      trackSchemas.push({ ...sch, name });
    }
  });
  Object.entries(get(datasetSchema)?.schemas ?? {}).forEach(([name, sch]) => {
    if (sch.base_schema === BaseSchema.MultiModalEntity) {
      multiModalSchemas.push({ ...sch, name });
    }
  });
  Object.entries(get(datasetSchema)?.schemas ?? {}).forEach(([name, sch]) => {
    if (sch.base_schema === BaseSchema.Entity) {
      entitySchemas.push({ ...sch, name });
    }
  });
  if (trackSchemas.length > 0) {
    topEntitySchema = trackSchemas[0];
    if (entitySchemas.length > 0) {
      subEntitySchema = entitySchemas[0];
    }
  } else if (multiModalSchemas.length > 0) {
    topEntitySchema = multiModalSchemas[0];
    if (entitySchemas.length > 0) {
      subEntitySchema = entitySchemas[0];
    }
  } else if (entitySchemas.length > 0) {
    topEntitySchema = entitySchemas[0];
  } else {
    console.error("ERROR: No available schema Entity", get(datasetSchema)?.schemas ?? {});
    throw new Error("ERROR: No available schema Entity");
  }

  if (selectedEntityId === "new") {
    topEntity = defineCreatedEntity(
      shape,
      features[topEntitySchema.name],
      get(datasetSchema),
      topEntitySchema,
    );
    topEntity.ui.childs = [];
    if (subEntitySchema) {
      subEntity = defineCreatedEntity(
        shape,
        features[subEntitySchema.name],
        get(datasetSchema),
        subEntitySchema,
        {
          id: topEntity.id,
          name: topEntity.table_info.name,
        },
      );
      subEntity.ui.childs = [];
    }
  } else {
    topEntity = get(entities).find((entity) => entity.id === selectedEntityId);
    if (!topEntity) {
      topEntity = defineCreatedEntity(
        shape,
        features[topEntitySchema.name],
        get(datasetSchema),
        topEntitySchema,
      );
      topEntity.ui.childs = [];
    }
    if (subEntitySchema) {
      //need to find entity with corresponding parent_ref.id and table_info.name, and view name
      subEntity = get(entities).find(
        (entity) =>
          //need to find entity with corresponding parent_ref.id and table_info.name, and view name
          entity.table_info.name === subEntitySchema.name &&
          entity.table_info.base_schema === subEntitySchema.base_schema &&
          entity.data.parent_ref.id === topEntity!.id &&
          //badly, *sub*entity.data.view_ref (id, or at least name) is not always set (it should!)
          (entity.data.view_ref.id !== ""
            ? entity.data.view_ref.id === shape.viewRef.id
            : entity.data.view_ref.name !== ""
              ? entity.data.view_ref.name === shape.viewRef.name
              : entity.ui.childs?.every((ann) => ann.data.view_ref.name === shape.viewRef.name)),
      );
      if (!subEntity) {
        subEntity = defineCreatedEntity(
          shape,
          features[subEntitySchema.name],
          get(datasetSchema),
          subEntitySchema,
          {
            id: topEntity.id,
            name: topEntity.table_info.name,
          },
        );
        subEntity.ui.childs = [];
      }
    }
  }
  return { topEntity, subEntity };
};
