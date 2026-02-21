/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { AnnotationNode, DocumentNode, NodeId } from "$lib/document";

import type { Command } from "$lib/types/commands";

// --------------- Add Annotation ---------------

export interface AddAnnotationPayload {
  readonly node: AnnotationNode;
}

export function createAddAnnotation(node: AnnotationNode): Command {
  return {
    type: "AddAnnotation",
    payload: { node } satisfies AddAnnotationPayload,
  };
}

// --------------- Delete Annotation ---------------

export interface DeleteAnnotationPayload {
  readonly nodeId: NodeId;
  /** If true, also deletes the entity if this was its last annotation. */
  readonly cascade: boolean;
}

export function createDeleteAnnotation(nodeId: NodeId, cascade: boolean = false): Command {
  return {
    type: "DeleteAnnotation",
    payload: { nodeId, cascade } satisfies DeleteAnnotationPayload,
  };
}

// --------------- Update Annotation ---------------

export interface UpdateAnnotationPayload {
  readonly nodeId: NodeId;
  readonly changes: Readonly<Record<string, unknown>>;
}

export function createUpdateAnnotation(
  nodeId: NodeId,
  changes: Record<string, unknown>,
): Command {
  return {
    type: "UpdateAnnotation",
    payload: { nodeId, changes } satisfies UpdateAnnotationPayload,
  };
}

// --------------- Batch Delete (for cascade) ---------------

export interface BatchDeletePayload {
  readonly nodeIds: readonly NodeId[];
  /** Snapshot of deleted nodes for undo. */
  readonly deletedNodes?: readonly DocumentNode[];
}

export function createBatchDelete(nodeIds: NodeId[]): Command {
  return {
    type: "BatchDelete",
    payload: { nodeIds } satisfies BatchDeletePayload,
  };
}
