/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** The fields of an entity that its place in the parent chain depends on. */
export type HierarchyEntity = {
  id: string;
  data: { parent_id?: unknown };
};

function getParentId(entity: HierarchyEntity): string {
  return typeof entity.data.parent_id === "string" ? entity.data.parent_id : "";
}

function resolveTopEntityId(
  entityId: string,
  entitiesById: ReadonlyMap<string, HierarchyEntity>,
  memo: Map<string, string>,
  ancestors: Set<string>,
): string {
  const memoized = memo.get(entityId);
  if (memoized) return memoized;

  const entity = entitiesById.get(entityId);
  if (!entity) {
    memo.set(entityId, entityId);
    return entityId;
  }

  const parentId = getParentId(entity);
  if (parentId === "" || !entitiesById.has(parentId) || ancestors.has(parentId)) {
    memo.set(entityId, entity.id);
    return entity.id;
  }

  ancestors.add(entity.id);
  const topEntityId = resolveTopEntityId(parentId, entitiesById, memo, ancestors);
  ancestors.delete(entity.id);
  memo.set(entity.id, topEntityId);
  return topEntityId;
}

/**
 * Map every entity id to the id of its top-level ancestor.
 *
 * A top-level entity maps to itself, and so does an entity whose parent is missing or part of a
 * cycle.
 */
export function buildTopEntityIdByEntityId(
  entities: readonly HierarchyEntity[],
): Map<string, string> {
  const entitiesById = new Map(entities.map((entity) => [entity.id, entity]));
  const topEntityIdByEntityId = new Map<string, string>();

  for (const entity of entities) {
    const topEntityId = resolveTopEntityId(
      entity.id,
      entitiesById,
      topEntityIdByEntityId,
      new Set<string>(),
    );
    topEntityIdByEntityId.set(entity.id, topEntityId);
  }

  return topEntityIdByEntityId;
}
