import { BaseSchema, type DatasetSchema, type FieldInfo, type WorkspaceType } from "$lib/types/dataset";
import { resourcePathForTable } from "$lib/api/resourceNames";

export type WorkspaceTableGroup = keyof DatasetSchema["groups"];

export interface WorkspaceTableManifest {
  name: string;
  group: WorkspaceTableGroup;
  baseSchema: BaseSchema;
  fields: Record<string, FieldInfo>;
}

export interface WorkspaceManifest {
  workspaceType: WorkspaceType;
  tablesByName: Record<string, WorkspaceTableManifest>;
  tablesByGroup: Record<WorkspaceTableGroup, string[]>;
  relations: Record<string, string[]>;
  baseSchemaToTable: Partial<Record<WorkspaceTableGroup, Partial<Record<BaseSchema, string>>>>;
}

export function buildWorkspaceManifest(
  schema: DatasetSchema,
  workspaceType: WorkspaceType,
): WorkspaceManifest {
  const tablesByName: Record<string, WorkspaceTableManifest> = {};
  const baseSchemaToTable: WorkspaceManifest["baseSchemaToTable"] = {
    annotations: {},
    entities: {},
    item: {},
    views: {},
    embeddings: {},
  };

  for (const [group, tables] of Object.entries(schema.groups) as Array<[
    WorkspaceTableGroup,
    string[],
  ]>) {
    for (const table of tables) {
      const tableSchema = schema.schemas[table];
      if (!tableSchema) continue;

      tablesByName[table] = {
        name: table,
        group,
        baseSchema: tableSchema.base_schema,
        fields: tableSchema.fields,
      };

      if (!(tableSchema.base_schema in baseSchemaToTable[group]!)) {
        baseSchemaToTable[group]![tableSchema.base_schema] = table;
      }
    }
  }

  return {
    workspaceType,
    tablesByName,
    tablesByGroup: {
      annotations: [...schema.groups.annotations],
      entities: [...schema.groups.entities],
      item: [...schema.groups.item],
      views: [...schema.groups.views],
      embeddings: [...schema.groups.embeddings],
    },
    relations: schema.relations,
    baseSchemaToTable,
  };
}

export function resolveWorkspaceTable(
  manifest: WorkspaceManifest,
  group: WorkspaceTableGroup,
  baseSchema: BaseSchema,
): string | undefined {
  return manifest.baseSchemaToTable[group]?.[baseSchema];
}

export function getWorkspaceResourcePaths(
  manifest: WorkspaceManifest,
  group: Extract<WorkspaceTableGroup, "annotations" | "entities" | "views" | "embeddings" | "item">,
): string[] {
  return manifest.tablesByGroup[group].map(resourcePathForTable);
}
