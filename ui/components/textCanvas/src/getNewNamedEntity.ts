import { NamedEntity, type AnnotationType } from "@pixano/core";

const DEFAULT_ANNOTATION: AnnotationType = {
  item_ref: { id: "", name: "" },
  view_ref: { id: "", name: "" },
  entity_ref: { id: "", name: "" },
  source_ref: { id: "", name: "" },
};

/**
 *
 * Function to create a new NamedEntity object
 * While it is not added to objectsApi
 *
 */
export const getNewNamedEntity = (id: string, content: string) => {
  const now = new Date().toISOString();
  const newNamedEntity = new NamedEntity({
    data: { content, ...DEFAULT_ANNOTATION },
    created_at: now,
    updated_at: now,
    id,
    table_info: { name: "NamedEntity", group: "annotations", base_schema: "NamedEntity" },
  });

  return newNamedEntity;
};
