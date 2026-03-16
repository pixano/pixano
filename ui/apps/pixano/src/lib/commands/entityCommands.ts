/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { EntityNode, NodeId } from "$lib/document";
import type { Command } from "$lib/types/commands";

// --------------- Add Entity ---------------

export interface AddEntityPayload {
  readonly node: EntityNode;
}

export function createAddEntity(node: EntityNode): Command {
  return {
    type: "AddEntity",
    payload: { node } satisfies AddEntityPayload,
  };
}

// --------------- Delete Entity ---------------

export interface DeleteEntityPayload {
  readonly nodeId: NodeId;
  /** If true, also deletes all child annotations and sub-entities. */
  readonly cascade: boolean;
}

export function createDeleteEntity(nodeId: NodeId, cascade: boolean = true): Command {
  return {
    type: "DeleteEntity",
    payload: { nodeId, cascade } satisfies DeleteEntityPayload,
  };
}

// --------------- Merge Entities ---------------

export interface MergeEntitiesPayload {
  /** The entity that will absorb the others. */
  readonly targetEntityId: NodeId;
  /** The entities being merged into the target. */
  readonly sourceEntityIds: readonly NodeId[];
}

export function createMergeEntities(targetEntityId: NodeId, sourceEntityIds: NodeId[]): Command {
  return {
    type: "MergeEntities",
    payload: { targetEntityId, sourceEntityIds } satisfies MergeEntitiesPayload,
  };
}
