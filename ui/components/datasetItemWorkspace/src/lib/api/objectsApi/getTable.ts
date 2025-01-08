/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { BaseSchema, DatasetSchema } from "@pixano/core";

export const getTable = (
  dataset_schema: DatasetSchema,
  group: keyof DatasetSchema["groups"],
  base_schema: BaseSchema,
): string => {
  for (const group_table of dataset_schema.groups[group]) {
    if (dataset_schema.schemas[group_table].base_schema === base_schema) {
      //NOTE: if there is several group tables with same base_schema, we could compare with "fields" to choose the correct one
      //it shouldn't happen for entities, but may happens for annotations...
      return group_table;
    }
  }
  return dataset_schema.groups[group][0]; //lint protection, should not happens
};
