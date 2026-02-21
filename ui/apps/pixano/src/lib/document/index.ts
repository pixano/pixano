/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Types
export type {
  NodeId,
  NodeType,
  DocumentNode,
  AnnotationNode,
  EntityNode,
  Relation,
  RelationType,
  Reference,
  TableInfo,
  CoordinateFrame,
  CoordinateDimensions,
  CoordinateFrameType,
  Timeline,
  TimelineRange,
  Patch,
  Document,
  DocumentQuery,
} from "$lib/types/document";

// Implementation
export { DocumentImpl } from "./DocumentImpl";

// Factory & Conversion
export { createDocumentFromDatasetItem } from "./createDocumentFromDatasetItem";
export { toDatasetItem } from "./toDatasetItem";
