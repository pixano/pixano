/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  AnnotationNode,
  CoordinateFrame,
  Document,
  DocumentNode,
  EntityNode,
  NodeId,
  Patch,
  Relation,
  Timeline,
} from "../types";

/**
 * Immutable Document implementation backed by Maps for O(1) ID lookups.
 *
 * All data is frozen at construction time. Mutations produce new instances
 * through the Command system.
 */
export class DocumentImpl implements Document {
  readonly id: string;
  readonly item: DocumentNode;
  readonly version: number;

  private readonly nodes: ReadonlyMap<NodeId, DocumentNode>;
  private readonly relations: ReadonlyArray<Relation>;
  private readonly coordinateFrames: ReadonlyMap<NodeId, CoordinateFrame>;
  private readonly timelines: ReadonlyMap<string, Timeline>;

  // Pre-computed indexes for fast filtered access
  private readonly annotationNodes: ReadonlyArray<AnnotationNode>;
  private readonly entityNodes: ReadonlyArray<EntityNode>;
  private readonly annotationsByView: ReadonlyMap<string, ReadonlyArray<AnnotationNode>>;
  private readonly annotationsByEntity: ReadonlyMap<NodeId, ReadonlyArray<AnnotationNode>>;
  private readonly annotationsByType: ReadonlyMap<string, ReadonlyArray<AnnotationNode>>;

  constructor(params: {
    id: string;
    item: DocumentNode;
    nodes: Map<NodeId, DocumentNode>;
    relations: Relation[];
    coordinateFrames: Map<NodeId, CoordinateFrame>;
    timelines: Map<string, Timeline>;
    version: number;
  }) {
    this.id = params.id;
    this.item = params.item;
    this.version = params.version;
    this.nodes = params.nodes;
    this.relations = Object.freeze([...params.relations]);
    this.coordinateFrames = params.coordinateFrames;
    this.timelines = params.timelines;

    // Build indexes
    const annotations: AnnotationNode[] = [];
    const entities: EntityNode[] = [];
    const byView = new Map<string, AnnotationNode[]>();
    const byEntity = new Map<NodeId, AnnotationNode[]>();
    const byType = new Map<string, AnnotationNode[]>();

    for (const node of params.nodes.values()) {
      if (node.nodeType === "annotation") {
        const ann = node as AnnotationNode;
        annotations.push(ann);

        // Index by view
        const viewName = ann.viewRef.name;
        if (!byView.has(viewName)) byView.set(viewName, []);
        byView.get(viewName)!.push(ann);

        // Index by entity
        const entityId = ann.entityRef.id as NodeId;
        if (!byEntity.has(entityId)) byEntity.set(entityId, []);
        byEntity.get(entityId)!.push(ann);

        // Index by base schema
        const baseSchema = ann.tableInfo.base_schema;
        if (!byType.has(baseSchema)) byType.set(baseSchema, []);
        byType.get(baseSchema)!.push(ann);
      } else if (node.nodeType === "entity") {
        entities.push(node as EntityNode);
      }
    }

    this.annotationNodes = Object.freeze(annotations);
    this.entityNodes = Object.freeze(entities);
    this.annotationsByView = byView;
    this.annotationsByEntity = byEntity;
    this.annotationsByType = byType;
  }

  getNode(id: NodeId): DocumentNode | undefined {
    return this.nodes.get(id);
  }

  getNodes(): ReadonlyArray<DocumentNode> {
    return Object.freeze([...this.nodes.values()]);
  }

  getAnnotations(): ReadonlyArray<AnnotationNode> {
    return this.annotationNodes;
  }

  getEntities(): ReadonlyArray<EntityNode> {
    return this.entityNodes;
  }

  getAnnotationsByView(viewName: string): ReadonlyArray<AnnotationNode> {
    return this.annotationsByView.get(viewName) ?? [];
  }

  getAnnotationsByEntity(entityId: NodeId): ReadonlyArray<AnnotationNode> {
    return this.annotationsByEntity.get(entityId) ?? [];
  }

  getAnnotationsByType(baseSchema: string): ReadonlyArray<AnnotationNode> {
    return this.annotationsByType.get(baseSchema) ?? [];
  }

  getRelations(): ReadonlyArray<Relation> {
    return this.relations;
  }

  getTimeline(viewName: string): Timeline | undefined {
    return this.timelines.get(viewName);
  }

  getCoordinateFrame(viewId: NodeId): CoordinateFrame | undefined {
    return this.coordinateFrames.get(viewId);
  }

  /**
   * Create a new Document with applied patches.
   * Uses structural sharing — unchanged nodes are reused by reference.
   */
  withPatches(patches: Patch[]): DocumentImpl {
    const newNodes = new Map(this.nodes as Map<NodeId, DocumentNode>);
    const newRelations = [...this.relations];
    const newFrames = new Map(this.coordinateFrames as Map<NodeId, CoordinateFrame>);
    const newTimelines = new Map(this.timelines as Map<string, Timeline>);

    for (const patch of patches) {
      switch (patch.type) {
        case "add":
          newNodes.set(patch.nodeId, patch.node);
          break;
        case "remove":
          newNodes.delete(patch.nodeId);
          break;
        case "update": {
          const existing = newNodes.get(patch.nodeId);
          if (existing) {
            newNodes.set(patch.nodeId, {
              ...existing,
              data: { ...existing.data, ...patch.changes },
            } as DocumentNode);
          }
          break;
        }
      }
    }

    return new DocumentImpl({
      id: this.id,
      item: this.item,
      nodes: newNodes,
      relations: newRelations,
      coordinateFrames: newFrames,
      timelines: newTimelines,
      version: this.version + 1,
    });
  }
}
