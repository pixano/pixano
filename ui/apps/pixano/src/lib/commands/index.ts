/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Types
export type { Command, CommandResult, Patch, CommandProcessor } from "$lib/types/commands";
export type { HistoryStack, HistoryEntry, Transaction } from "$lib/types/commands";

// Implementations
export { CommandProcessorImpl } from "./CommandProcessorImpl";
export { HistoryStackImpl } from "./HistoryStackImpl";

// Concrete commands — Annotations
export {
  createAddAnnotation,
  createDeleteAnnotation,
  createUpdateAnnotation,
  createBatchDelete,
} from "./annotationCommands";
export type {
  AddAnnotationPayload,
  DeleteAnnotationPayload,
  UpdateAnnotationPayload,
  BatchDeletePayload,
} from "./annotationCommands";

// Concrete commands — Entities
export {
  createAddEntity,
  createDeleteEntity,
  createMergeEntities,
} from "./entityCommands";
export type {
  AddEntityPayload,
  DeleteEntityPayload,
  MergeEntitiesPayload,
} from "./entityCommands";
