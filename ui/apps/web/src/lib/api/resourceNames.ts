/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Entities are the one resource no annotation kind owns — every kind's create
 * builder may emit one, so its name lives here. Annotation resource names are
 * NOT declared here on purpose: each kind's payload builder owns its own
 * (`BBOX_RESOURCE` in `kinds/2d/bbox/`, …), so adding a kind touches no shared
 * file. Read one through `payloadBuilderFor(kind).resource`.
 */
export const ENTITY_RESOURCE = "entities";

const TABLE_TO_RESOURCE_PATH: Record<string, string> = {
  entity_dynamic_states: "entity-dynamic-states",
  text_spans: "text-spans",
};

export function normalizeTableName(tableName: string): string {
  return tableName.replace(/-/g, "_");
}

export function resourcePathForTable(tableName: string): string {
  const normalized = normalizeTableName(tableName);
  return TABLE_TO_RESOURCE_PATH[normalized] ?? normalized.replace(/_/g, "-");
}
