import { TaggedText, type AnnotationType } from "@pixano/core";

const DEFAULT_ANNOTATION: AnnotationType = {
  item_ref: { id: "", name: "" },
  view_ref: { id: "", name: "" },
  entity_ref: { id: "", name: "" },
  source_ref: { id: "", name: "" },
};

/**
 *
 * Function to create a new TaggedText object
 * While it is not added to objectsApi
 *
 */
export const getNewTaggedText = (id: string, content: string) => {
  const now = new Date().toISOString();
  const newTaggedText = new TaggedText({
    data: { content, ...DEFAULT_ANNOTATION },
    created_at: now,
    updated_at: now,
    id,
    table_info: { name: "TaggedText", group: "annotations", base_schema: "TaggedText" },
  });

  return newTaggedText;
};
