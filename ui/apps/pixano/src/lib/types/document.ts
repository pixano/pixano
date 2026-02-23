/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// ============================================================
// @pixano/document — Framework-agnostic annotation document model
// ============================================================

// --------------- Branded Types ---------------

/**
 * Branded string type for node identifiers.
 * Provides nominal typing to prevent accidental string misuse.
 */
export type NodeId = string & { readonly __brand: "NodeId" };

/** The category of a node in the document graph. */
export type NodeType = "annotation" | "entity" | "view" | "item" | "source";

// --------------- References & Table Info ---------------

/** A named reference to another node (mirrors backend Reference schema). */
export interface Reference {
  readonly id: string;
  readonly name: string;
}

/** Metadata about the backend table a node belongs to. */
export interface TableInfo {
  readonly name: string;
  readonly group: string;
  readonly base_schema: string;
}

// --------------- Document Nodes ---------------

/** Base node in the document graph. */
export interface DocumentNode {
  readonly id: NodeId;
  readonly nodeType: NodeType;
  readonly tableInfo: TableInfo;
  readonly data: Readonly<Record<string, unknown>>;
  readonly createdAt: string;
  readonly updatedAt: string;
}

/** An annotation node — linked to an item, view, entity, and source. */
export interface AnnotationNode extends DocumentNode {
  readonly nodeType: "annotation";
  readonly itemRef: Reference;
  readonly viewRef: Reference;
  readonly entityRef: Reference;
  readonly sourceRef: Reference;
}

/** An entity node — groups annotations together (e.g., a tracked object). */
export interface EntityNode extends DocumentNode {
  readonly nodeType: "entity";
  readonly itemRef: Reference;
  readonly parentRef?: Reference;
}

// --------------- Relations ---------------

/** Edge types in the document graph. */
export type RelationType =
  | "entity_ref"
  | "view_ref"
  | "item_ref"
  | "source_ref"
  | "parent_ref"
  | "track_child";

/** A directed edge between two nodes. */
export interface Relation {
  readonly sourceId: NodeId;
  readonly targetId: NodeId;
  readonly type: RelationType;
}

// --------------- Coordinate Frames ---------------

export type CoordinateFrameType = "image2d" | "world3d" | "textSpan" | "temporal";

export interface CoordinateDimensions {
  readonly width?: number;
  readonly height?: number;
  readonly depth?: number;
  readonly length?: number;
}

/** A coordinate frame associated with a view (image dimensions, 3D world, etc.). */
export interface CoordinateFrame {
  readonly id: string;
  readonly type: CoordinateFrameType;
  readonly viewId: NodeId;
  readonly dimensions: CoordinateDimensions;
}

// --------------- Timeline ---------------

/** A range of frames in a video timeline. */
export interface TimelineRange {
  readonly start: number;
  readonly end: number;
}

/** Timeline metadata for a video view. */
export interface Timeline {
  readonly viewName: string;
  readonly frameCount: number;
  readonly fps?: number;
  readonly trackletRanges: ReadonlyMap<NodeId, TimelineRange>;
}

// --------------- Document Query ---------------

/** Query descriptor for subscribing to document subsets. */
export interface DocumentQuery {
  readonly nodeTypes?: readonly NodeType[];
  readonly viewName?: string;
  readonly baseSchema?: string;
  readonly entityId?: NodeId;
}

// --------------- Patches ---------------

/** A granular patch describing a single node-level change. */
export type Patch =
  | { readonly type: "add"; readonly nodeId: NodeId; readonly node: DocumentNode }
  | { readonly type: "remove"; readonly nodeId: NodeId }
  | {
      readonly type: "update";
      readonly nodeId: NodeId;
      readonly changes: Readonly<Record<string, unknown>>;
    };

// --------------- Document ---------------

/**
 * The root Document interface — an immutable snapshot of an annotation workspace.
 *
 * Provides read-only access to nodes, relations, and derived collections.
 * All mutations go through the Command system, which produces a new Document.
 */
export interface Document {
  readonly id: string;
  readonly item: DocumentNode;

  // --- Node access ---
  getNode(id: NodeId): DocumentNode | undefined;
  getNodes(): ReadonlyArray<DocumentNode>;

  // --- Typed collection access ---
  getAnnotations(): ReadonlyArray<AnnotationNode>;
  getEntities(): ReadonlyArray<EntityNode>;

  // --- Filtered access ---
  getAnnotationsByView(viewName: string): ReadonlyArray<AnnotationNode>;
  getAnnotationsByEntity(entityId: NodeId): ReadonlyArray<AnnotationNode>;
  getAnnotationsByType(baseSchema: string): ReadonlyArray<AnnotationNode>;

  // --- Relations ---
  getRelations(): ReadonlyArray<Relation>;

  // --- Coordinate & Timeline ---
  getTimeline(viewName: string): Timeline | undefined;
  getCoordinateFrame(viewId: NodeId): CoordinateFrame | undefined;

  // --- Versioning ---
  readonly version: number;
}
