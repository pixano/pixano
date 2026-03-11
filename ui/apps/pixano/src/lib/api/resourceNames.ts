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
