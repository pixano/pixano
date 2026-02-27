/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, Entity, type SaveItem, type Schema } from "$lib/types/dataset";

import { addSchemas, updateSchemas, deleteSchemasByIds } from "./schemaApi";

/**
 * Groups save items by change type, then by group and table.
 * For "delete" items, stores the IDs; for "add"/"update", stores the schema objects (minus `ui`).
 */
export function reduceByTypeAndGroupAndTable(
  saveData: SaveItem[],
  type: string,
): Record<string, Record<string, (Schema | string)[]>> {
  const type_data = saveData.filter((d) => d.change_type === type);
  return type_data.reduce(
    (acc, item) => {
      const group = item.data.table_info.group;
      const table = item.data.table_info.name;
      if (!acc[group]) {
        acc[group] = {};
      }
      if (!acc[group][table]) {
        acc[group][table] = [];
      }
      if (type === "delete") {
        acc[group][table].push(item.data.id);
      } else {
        //remove ui field  ('ui' is not used, it's OK -- so we disable linters for the line)
        // @ts-expect-error Property ui may not exist, but we don't care as we don't use it
        const { ui, ...bodyObj } = item.data; // eslint-disable-line @typescript-eslint/no-unused-vars
        acc[group][table].push(bodyObj as Schema);
      }
      return acc;
    },
    {} as Record<string, Record<string, (Schema | string)[]>>,
  );
}

function resolveRoute(group: string): { route: string; no_table: boolean } {
  if (group === "item") return { route: "items", no_table: true };
  if (group === "source") return { route: "sources", no_table: true };
  return { route: group, no_table: false };
}

/**
 * Persists save items via add/update/delete API calls.
 * Entities are sorted first to avoid database consistency-check issues.
 */
export async function persistSaveItems(saveData: SaveItem[], datasetId: string): Promise<void> {
  // Entities first to avoid database consistency checks issues
  saveData.sort((a, b) => {
    const priority = (object: Schema) => {
      if (object.table_info.base_schema === BaseSchema.Track) return 0;
      if (object.table_info.base_schema === BaseSchema.Entity) {
        if ((object as Entity).data.parent_id === "") return 1;
        else return 2;
      }
      return 3;
    };
    return priority(a.data) - priority(b.data);
  });

  const add_data_by_group_and_table = reduceByTypeAndGroupAndTable(saveData, "add");
  for (const group in add_data_by_group_and_table) {
    for (const [table, schs] of Object.entries(add_data_by_group_and_table[group])) {
      const { route, no_table } = resolveRoute(group);
      await addSchemas(route, datasetId, schs as Schema[], table, no_table);
    }
  }

  const update_data_by_group_and_table = reduceByTypeAndGroupAndTable(saveData, "update");
  for (const group in update_data_by_group_and_table) {
    for (const [table, schs] of Object.entries(update_data_by_group_and_table[group])) {
      const { route, no_table } = resolveRoute(group);
      await updateSchemas(route, datasetId, schs as Schema[], table, no_table);
    }
  }

  const delete_ids_by_group_and_table = reduceByTypeAndGroupAndTable(saveData, "delete");
  for (const group in delete_ids_by_group_and_table) {
    for (const [table, ids] of Object.entries(delete_ids_by_group_and_table[group])) {
      const { route, no_table } = resolveRoute(group);
      await deleteSchemasByIds(route, datasetId, ids as string[], table, no_table);
    }
  }
}
