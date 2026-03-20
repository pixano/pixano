/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  AddAnnotationPayload,
  BatchDeletePayload,
  DeleteAnnotationPayload,
  UpdateAnnotationPayload,
} from "../commands/annotationCommands";
import {
  createBatchDelete,
  createDeleteAnnotation,
  createUpdateAnnotation,
} from "../commands/annotationCommands";
import type {
  AddEntityPayload,
  DeleteEntityPayload,
  MergeEntitiesPayload,
} from "../commands/entityCommands";
import { createDeleteEntity } from "../commands/entityCommands";
import type { AnnotationNode, Document, DocumentNode, NodeId, Patch } from "$lib/document";
import { DocumentImpl } from "$lib/document";
import type { Command, CommandProcessor, CommandResult } from "$lib/types/commands";

type CommandHandler = (document: Document, payload: unknown) => CommandResult;

/**
 * Concrete CommandProcessor that dispatches to handler functions.
 *
 * Each handler is a pure function: (Document, payload) → CommandResult.
 * The inverse command is computed at execution time.
 */
export class CommandProcessorImpl implements CommandProcessor {
  private handlers = new Map<string, CommandHandler>();

  constructor() {
    this.registerBuiltinHandlers();
  }

  apply(document: Document, command: Command): CommandResult {
    const handler = this.handlers.get(command.type);
    if (!handler) {
      throw new Error(`Unknown command type: ${command.type}`);
    }
    return handler(document, command.payload);
  }

  registerHandler(commandType: string, handler: CommandHandler): void {
    this.handlers.set(commandType, handler);
  }

  private registerBuiltinHandlers(): void {
    this.handlers.set("AddAnnotation", (doc, payload) =>
      this.handleAddAnnotation(doc, payload as AddAnnotationPayload),
    );
    this.handlers.set("DeleteAnnotation", (doc, payload) =>
      this.handleDeleteAnnotation(doc, payload as DeleteAnnotationPayload),
    );
    this.handlers.set("UpdateAnnotation", (doc, payload) =>
      this.handleUpdateAnnotation(doc, payload as UpdateAnnotationPayload),
    );
    this.handlers.set("BatchDelete", (doc, payload) =>
      this.handleBatchDelete(doc, payload as BatchDeletePayload),
    );
    this.handlers.set("AddEntity", (doc, payload) =>
      this.handleAddEntity(doc, payload as AddEntityPayload),
    );
    this.handlers.set("DeleteEntity", (doc, payload) =>
      this.handleDeleteEntity(doc, payload as DeleteEntityPayload),
    );
    this.handlers.set("MergeEntities", (doc, payload) =>
      this.handleMergeEntities(doc, payload as MergeEntitiesPayload),
    );
    this.handlers.set("BatchAdd", (doc, payload) =>
      this.handleBatchAdd(doc, payload as { nodes: DocumentNode[] }),
    );
  }

  // --------------- Handlers ---------------

  private handleAddAnnotation(document: Document, payload: AddAnnotationPayload): CommandResult {
    const { node } = payload;
    const patches: Patch[] = [{ type: "add", nodeId: node.id, node }];
    const newDocument = this.applyPatches(document, patches);
    const inverse = createDeleteAnnotation(node.id, false);

    return { newDocument, inverse, patches };
  }

  private handleDeleteAnnotation(
    document: Document,
    payload: DeleteAnnotationPayload,
  ): CommandResult {
    const { nodeId, cascade } = payload;
    const node = document.getNode(nodeId);
    if (!node || node.nodeType !== "annotation") {
      return { newDocument: document, inverse: { type: "Noop", payload: {} }, patches: [] };
    }

    const ann = node as AnnotationNode;
    const patches: Patch[] = [{ type: "remove", nodeId }];

    if (cascade) {
      // Check if this was the last annotation for its entity
      const entityId = ann.entityRef.id as NodeId;
      const entityAnnotations = document.getAnnotationsByEntity(entityId);
      if (entityAnnotations.length <= 1) {
        // Delete the entity and its sub-entities too
        const entity = document.getNode(entityId);
        if (entity) {
          patches.push({ type: "remove", nodeId: entityId });
          // Delete sub-entities
          for (const ent of document.getEntities()) {
            if (ent.parentRef?.id === entityId) {
              patches.push({ type: "remove", nodeId: ent.id });
            }
          }
        }
      }
    }

    const newDocument = this.applyPatches(document, patches);

    // Build inverse: re-add all deleted nodes
    const deletedNodes = patches
      .filter((p) => p.type === "remove")
      .map((p) => document.getNode(p.nodeId))
      .filter((n): n is DocumentNode => n !== undefined);

    const inverse: Command = {
      type: "BatchAdd",
      payload: { nodes: deletedNodes },
    };

    return { newDocument, inverse, patches };
  }

  private handleUpdateAnnotation(
    document: Document,
    payload: UpdateAnnotationPayload,
  ): CommandResult {
    const { nodeId, changes } = payload;
    const existing = document.getNode(nodeId);
    if (!existing) {
      return { newDocument: document, inverse: { type: "Noop", payload: {} }, patches: [] };
    }

    // Compute inverse: restore old values
    const oldValues: Record<string, unknown> = {};
    for (const key of Object.keys(changes)) {
      oldValues[key] = existing.data[key];
    }

    const patches: Patch[] = [{ type: "update", nodeId, changes }];
    const newDocument = this.applyPatches(document, patches);
    const inverse = createUpdateAnnotation(nodeId, oldValues);

    return { newDocument, inverse, patches };
  }

  private handleBatchDelete(document: Document, payload: BatchDeletePayload): CommandResult {
    const { nodeIds } = payload;
    const patches: Patch[] = nodeIds.map((nodeId) => ({ type: "remove" as const, nodeId }));

    const deletedNodes = nodeIds
      .map((id) => document.getNode(id))
      .filter((n): n is DocumentNode => n !== undefined);

    const newDocument = this.applyPatches(document, patches);
    const inverse: Command = {
      type: "BatchAdd",
      payload: { nodes: deletedNodes },
    };

    return { newDocument, inverse, patches };
  }

  private handleBatchAdd(document: Document, payload: { nodes: DocumentNode[] }): CommandResult {
    const { nodes } = payload;
    const patches: Patch[] = nodes.map((node) => ({
      type: "add" as const,
      nodeId: node.id,
      node,
    }));
    const newDocument = this.applyPatches(document, patches);
    const inverse = createBatchDelete(nodes.map((n) => n.id));

    return { newDocument, inverse, patches };
  }

  private handleAddEntity(document: Document, payload: AddEntityPayload): CommandResult {
    const { node } = payload;
    const patches: Patch[] = [{ type: "add", nodeId: node.id, node }];
    const newDocument = this.applyPatches(document, patches);
    const inverse = createDeleteEntity(node.id, false);

    return { newDocument, inverse, patches };
  }

  private handleDeleteEntity(document: Document, payload: DeleteEntityPayload): CommandResult {
    const { nodeId, cascade } = payload;
    const entity = document.getNode(nodeId);
    if (!entity || entity.nodeType !== "entity") {
      return { newDocument: document, inverse: { type: "Noop", payload: {} }, patches: [] };
    }

    const patches: Patch[] = [{ type: "remove", nodeId }];

    if (cascade) {
      // Delete all annotations referencing this entity
      const entityAnnotations = document.getAnnotationsByEntity(nodeId);
      for (const ann of entityAnnotations) {
        patches.push({ type: "remove", nodeId: ann.id });
      }

      // Delete sub-entities
      for (const ent of document.getEntities()) {
        if (ent.parentRef?.id === nodeId) {
          patches.push({ type: "remove", nodeId: ent.id });
          // And their annotations
          const subAnn = document.getAnnotationsByEntity(ent.id);
          for (const ann of subAnn) {
            patches.push({ type: "remove", nodeId: ann.id });
          }
        }
      }
    }

    const newDocument = this.applyPatches(document, patches);

    const deletedNodes = patches
      .filter((p) => p.type === "remove")
      .map((p) => document.getNode(p.nodeId))
      .filter((n): n is DocumentNode => n !== undefined);

    const inverse: Command = {
      type: "BatchAdd",
      payload: { nodes: deletedNodes },
    };

    return { newDocument, inverse, patches };
  }

  private handleMergeEntities(document: Document, payload: MergeEntitiesPayload): CommandResult {
    const { targetEntityId, sourceEntityIds } = payload;
    const patches: Patch[] = [];

    // Move all annotations from source entities to target
    const movedAnnotations: { nodeId: NodeId; oldEntityRef: string }[] = [];

    for (const sourceId of sourceEntityIds) {
      const sourceAnnotations = document.getAnnotationsByEntity(sourceId);
      for (const ann of sourceAnnotations) {
        movedAnnotations.push({ nodeId: ann.id, oldEntityRef: ann.entityRef.id });
        patches.push({
          type: "update",
          nodeId: ann.id,
          changes: { entity_id: targetEntityId },
        });
      }

      // Remove source entity
      patches.push({ type: "remove", nodeId: sourceId });

      // Remove source sub-entities
      for (const ent of document.getEntities()) {
        if (ent.parentRef?.id === sourceId) {
          patches.push({ type: "remove", nodeId: ent.id });
        }
      }
    }

    const newDocument = this.applyPatches(document, patches);

    // Inverse: unmerge by restoring old entity refs and re-adding deleted entities
    const deletedNodes = patches
      .filter((p) => p.type === "remove")
      .map((p) => document.getNode(p.nodeId))
      .filter((n): n is DocumentNode => n !== undefined);

    const inversePatches: unknown[] = [
      ...deletedNodes.map((n) => ({ type: "add", nodeId: n.id, node: n })),
      ...movedAnnotations.map((m) => ({
        type: "update",
        nodeId: m.nodeId,
        changes: { entity_id: m.oldEntityRef },
      })),
    ];

    const inverse: Command = {
      type: "UnmergeEntities",
      payload: { patches: inversePatches, deletedNodes },
    };

    return { newDocument, inverse, patches };
  }

  // --------------- Helpers ---------------

  private applyPatches(document: Document, patches: Patch[]): Document {
    if (document instanceof DocumentImpl) {
      return document.withPatches(patches);
    }
    // Fallback for non-DocumentImpl (e.g., in tests with mock documents)
    throw new Error("Document must be a DocumentImpl instance for patch application");
  }
}
