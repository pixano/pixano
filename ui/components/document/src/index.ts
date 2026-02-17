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
} from "./types";

// Implementation
export { DocumentImpl } from "./impl/DocumentImpl";

// Factory & Conversion
export { createDocumentFromDatasetItem } from "./factory/createDocumentFromDatasetItem";
export { toDatasetItem } from "./factory/toDatasetItem";
