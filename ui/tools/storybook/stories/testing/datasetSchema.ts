/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, type DatasetSchema } from "@pixano/core";

export const datasetSchema: DatasetSchema = {
  relations: {},
  schemas: {
    bboxes: {
      base_schema: BaseSchema.BBox,
      fields: {
        confidence: { type: "float", collection: false },
        coords: { type: "float", collection: true },
        created_at: { type: "datetime", collection: false },
        entity_ref: { type: "EntityRef", collection: false },
        format: { type: "str", collection: false },
        id: { type: "str", collection: false },
        is_normalized: { type: "bool", collection: false },
        item_ref: { type: "ItemRef", collection: false },
        source_ref: { type: "SourceRef", collection: false },
        updated_at: { type: "datetime", collection: false },
        view_ref: { type: "ViewRef", collection: false },
      },
      schema: "BBox",
    },
    classifications: {
      base_schema: BaseSchema.Classification,
      fields: {
        confidences: { type: "float", collection: true },
        created_at: { type: "datetime", collection: false },
        entity_ref: { type: "EntityRef", collection: false },
        id: { type: "str", collection: false },
        item_ref: { type: "ItemRef", collection: false },
        labels: { type: "str", collection: true },
        source_ref: { type: "SourceRef", collection: false },
        updated_at: { type: "datetime", collection: false },
        view_ref: { type: "ViewRef", collection: false },
      },
      schema: "Classification",
    },
    conversations: {
      base_schema: BaseSchema.Conversation,
      fields: {
        created_at: { type: "datetime", collection: false },
        id: { type: "str", collection: false },
        item_ref: { type: "ItemRef", collection: false },
        kind: { type: "str", collection: false },
        parent_ref: { type: "EntityRef", collection: false },
        updated_at: { type: "datetime", collection: false },
        view_ref: { type: "ViewRef", collection: false },
      },
      schema: "Conversation",
    },
    image: {
      base_schema: BaseSchema.Image,
      fields: {
        created_at: { type: "datetime", collection: false },
        format: { type: "str", collection: false },
        height: { type: "int", collection: false },
        id: { type: "str", collection: false },
        item_ref: { type: "ItemRef", collection: false },
        parent_ref: { type: "ViewRef", collection: false },
        updated_at: { type: "datetime", collection: false },
        url: { type: "str", collection: false },
        width: { type: "int", collection: false },
      },
      schema: "Image",
    },
    item: {
      base_schema: BaseSchema.Item,
      fields: {
        created_at: { type: "datetime", collection: false },
        id: { type: "str", collection: false },
        split: { type: "str", collection: false },
        updated_at: { type: "datetime", collection: false },
      },
      schema: "Item",
    },
    masks: {
      base_schema: BaseSchema.Mask,
      fields: {
        counts: { type: "bytes", collection: false },
        created_at: { type: "datetime", collection: false },
        entity_ref: { type: "EntityRef", collection: false },
        id: { type: "str", collection: false },
        item_ref: { type: "ItemRef", collection: false },
        size: { type: "int", collection: true },
        source_ref: { type: "SourceRef", collection: false },
        updated_at: { type: "datetime", collection: false },
        view_ref: { type: "ViewRef", collection: false },
      },
      schema: "CompressedRLE",
    },
    messages: {
      base_schema: BaseSchema.Message,
      fields: {
        answer_choices: { type: "str", collection: true },
        content: { type: "str", collection: false },
        created_at: { type: "datetime", collection: false },
        entity_ref: { type: "EntityRef", collection: false },
        id: { type: "str", collection: false },
        item_ref: { type: "ItemRef", collection: false },
        number: { type: "int", collection: false },
        source_ref: { type: "SourceRef", collection: false },
        timestamp: { type: "datetime", collection: false },
        type: { type: "str", collection: false },
        updated_at: { type: "datetime", collection: false },
        user: { type: "str", collection: false },
        view_ref: { type: "ViewRef", collection: false },
      },
      schema: "Message",
    },
    multimodal_entities: {
      base_schema: BaseSchema.Entity,
      fields: {
        created_at: { type: "datetime", collection: false },
        id: { type: "str", collection: false },
        item_ref: { type: "ItemRef", collection: false },
        parent_ref: { type: "EntityRef", collection: false },
        updated_at: { type: "datetime", collection: false },
        view_ref: { type: "ViewRef", collection: false },
      },
      schema: "Entity",
    },
    text_spans: {
      base_schema: BaseSchema.TextSpan,
      fields: {
        annotation_ref: { type: "AnnotationRef", collection: false },
        created_at: { type: "datetime", collection: false },
        entity_ref: { type: "EntityRef", collection: false },
        id: { type: "str", collection: false },
        item_ref: { type: "ItemRef", collection: false },
        mention: { type: "str", collection: false },
        source_ref: { type: "SourceRef", collection: false },
        spans_end: { type: "int", collection: true },
        spans_start: { type: "int", collection: true },
        updated_at: { type: "datetime", collection: false },
        view_ref: { type: "ViewRef", collection: false },
      },
      schema: "TextSpan",
    },
  },
  groups: {
    annotations: ["text_spans", "classifications", "messages", "bboxes", "masks"],
    entities: ["conversations", "multimodal_entities"],
    item: ["item"],
    views: ["image"],
    embeddings: [],
  },
};
