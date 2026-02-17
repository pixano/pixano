/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Types
export type { Command, CommandResult, Patch, CommandProcessor } from "./types";
export type { HistoryStack, HistoryEntry, Transaction } from "./types";

// Implementations
export { CommandProcessorImpl } from "./impl/CommandProcessorImpl";
export { HistoryStackImpl } from "./impl/HistoryStackImpl";

// Concrete commands — Annotations
export {
  createAddAnnotation,
  createDeleteAnnotation,
  createUpdateAnnotation,
  createBatchDelete,
} from "./commands/annotationCommands";
export type {
  AddAnnotationPayload,
  DeleteAnnotationPayload,
  UpdateAnnotationPayload,
  BatchDeletePayload,
} from "./commands/annotationCommands";

// Concrete commands — Entities
export {
  createAddEntity,
  createDeleteEntity,
  createMergeEntities,
} from "./commands/entityCommands";
export type {
  AddEntityPayload,
  DeleteEntityPayload,
  MergeEntitiesPayload,
} from "./commands/entityCommands";
