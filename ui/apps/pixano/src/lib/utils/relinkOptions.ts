/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Annotation, BaseSchema, Entity, Tracklet, type Reference } from "$lib/types/dataset";
import { getDefaultDisplayFeat } from "$lib/utils/workspaceDefaultFeatures";

/**
 * A candidate parent entity for a new annotation.
 *
 * `kind` encodes the linking semantics instead of label-prefix strings:
 * - `new`: create a fresh entity.
 * - `move`: link to this entity (no tracklet overlap).
 * - `merge`: link and merge into the overlapping tracklet(s) in `targets`.
 * - `forbidden`: disabled — `conflicts` same-kind annotations already exist there.
 */
export interface RelinkOption {
  id: string;
  /** Display name (entity display attribute, or its id). */
  name: string;
  kind: "new" | "move" | "merge" | "forbidden";
  conflicts: number;
  targets: string[];
}

interface RelinkContext {
  entities: Entity[];
  baseSchema: BaseSchema;
  viewRef: Reference;
  track?: Annotation | null;
  /** Top entity id of `track`, when editing a track (that object is excluded). */
  trackTopEntityId?: string | null;
  currentFrameIndex: number;
}

interface AllowInfo {
  hard_forbidden: boolean;
  overlap: boolean;
  numSameKindInSameView: number;
  overlapTargetIds: string[];
}

function entityAllowInfo(entity: Entity, context: RelinkContext): AllowInfo {
  const { baseSchema, viewRef, track, trackTopEntityId, currentFrameIndex } = context;
  if (
    entity.data.parent_id !== "" ||
    entity.is_conversation ||
    (track && trackTopEntityId != null && trackTopEntityId === entity.id)
  ) {
    return { hard_forbidden: true, overlap: false, numSameKindInSameView: 0, overlapTargetIds: [] };
  }
  const entityTracks = entity.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Tracklet));
  const annsNotTracks = entity.ui.childs?.filter((ann) => !ann.is_type(BaseSchema.Tracklet));
  let numSameKindInSameView = 0;
  let overlap: boolean | undefined = undefined;
  let overlapTargetIds: string[] = [];

  if (track && track.is_type(BaseSchema.Tracklet)) {
    const trackBaseSchemaByFrameIndex = (track as Tracklet).ui.childs.reduce(
      (acc, ann) => {
        if (ann.ui.frame_index) {
          acc[ann.ui.frame_index] = ann.table_info.base_schema;
        }
        return acc;
      },
      {} as Record<number, BaseSchema>,
    );
    const sameKind = annsNotTracks?.filter(
      //NOTE we "miss" interpolated shapes. So we can "insert"
      (ann) =>
        ann.ui.frame_index
          ? ann.data.view_name === viewRef.name &&
            trackBaseSchemaByFrameIndex[ann.ui.frame_index] === ann.table_info.base_schema
          : false,
    );
    numSameKindInSameView = sameKind ? sameKind.length : 0;
    const overlapTracks = entityTracks?.filter(
      (ann) =>
        (ann as Tracklet).data.view_name === viewRef.name &&
        (ann as Tracklet).data.start_frame <= (track as Tracklet).data.end_frame &&
        (ann as Tracklet).data.end_frame >= (track as Tracklet).data.start_frame,
    );
    overlap = overlapTracks ? overlapTracks.length > 0 : false;
    if (overlapTracks && overlapTracks.length > 0) {
      overlapTargetIds = overlapTracks.map((ann) => ann.id);
    }
  } else {
    const sameKind = annsNotTracks?.filter(
      //NOTE we "miss" interpolated shapes. So we can "insert"
      (ann) => ann.data.frame_id === viewRef.id && baseSchema === ann.table_info.base_schema,
    );
    numSameKindInSameView = sameKind ? sameKind.length : 0;
    //WARNING: if we ever allow relinking a tracklet child, currentFrameIndex is unreliable.
    const overlapTracks = entityTracks?.filter(
      (ann) =>
        (ann as Tracklet).data.view_name === viewRef.name &&
        (ann as Tracklet).data.start_frame <= currentFrameIndex &&
        (ann as Tracklet).data.end_frame >= currentFrameIndex,
    );
    overlap = overlapTracks ? overlapTracks.length > 0 : false;
    if (overlapTracks && overlapTracks.length > 0) {
      overlapTargetIds = overlapTracks.map((ann) => ann.id);
    }
  }
  // !overlap → move · overlap && 0 same-kind → merge (keep target tracklet) · else forbidden
  return {
    hard_forbidden: false,
    overlap: overlap ?? false,
    numSameKindInSameView,
    overlapTargetIds,
  };
}

/**
 * Build the parent-entity options for the save-annotation form.
 *
 * The "Create new entity" option always comes first; hard-forbidden entities
 * (sub-entities, conversations, the track's own entity) are omitted entirely.
 */
export function buildRelinkOptions(context: RelinkContext): RelinkOption[] {
  const options: RelinkOption[] = [{ id: "new", name: "", kind: "new", conflicts: 0, targets: [] }];
  for (const entity of context.entities) {
    const info = entityAllowInfo(entity, context);
    if (info.hard_forbidden) continue;
    const displayFeat = getDefaultDisplayFeat(entity);
    options.push({
      id: entity.id,
      name: displayFeat ? String(displayFeat) : entity.id,
      kind: info.overlap ? (info.numSameKindInSameView === 0 ? "merge" : "forbidden") : "move",
      conflicts: info.numSameKindInSameView,
      targets: info.overlapTargetIds,
    });
  }
  return options;
}
