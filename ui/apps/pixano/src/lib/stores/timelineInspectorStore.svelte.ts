/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * What the video timeline shows: one row per object with tracks of its own (unless its
 * track is hidden), and the row the selection points at. The rules live in lib/timeline;
 * this module wires them to the workspace stores, keeping each result while its inputs are
 * unchanged so a display-only commit re-renders nothing.
 */

import { untrack } from "svelte";

import { reactiveDerived, reactiveStore } from "./reactiveStore.svelte";
import { currentItemId, timelineZoom, videoViewNames } from "./videoStores.svelte";
import {
  annotationColors,
  editedTrackletId,
  entities,
  highlightedEntity,
  selectedTool,
  tracks,
} from "./workspaceStores.svelte";
import {
  extendTimelineRanks,
  orderTimelineRows,
  resolveSelectedRow,
  sameTimelineRows,
  storedSelfEntityId,
  type RankKey,
} from "$lib/timeline/timelineRows";
import { buildTrackModels, sortViewNames, type TrackModelCache } from "$lib/timeline/trackModel";
import type { EntityTrackModel, LaneGeom } from "$lib/timeline/types";
import { ToolType } from "$lib/types/tools";
import { effectProbe } from "$lib/utils/effectProbe";
import { buildTopEntityIdByEntityId } from "$lib/utils/entityHierarchy";
import { TIMELINE_ZOOM_MIN } from "$lib/utils/timelineZoom";

/** The row last clicked, so a sub-entity's row stays selected while its parent is focused. */
export const timelineFocusedRowId = reactiveStore<string | null>(null);

/** The record's cameras, in natural order. */
export const timelineViewOrder = reactiveDerived<string[]>(() =>
  sortViewNames(videoViewNames.value),
);

let trackModelCache: TrackModelCache | null = null;

/** Each object's own tracks, per camera and merged; the same Map while nothing drawn changes. */
export const timelineTrackModels = reactiveDerived<ReadonlyMap<string, EntityTrackModel>>(() => {
  const tracklets = tracks.value;
  const colors = annotationColors.value;
  const viewOrder = timelineViewOrder.value;
  // Children are read once per changed track (and cached): tracking every keyframe here would
  // make each derived run register thousands of signals.
  effectProbe("Timeline.trackModels");
  return untrack(() => {
    trackModelCache = buildTrackModels(
      tracklets,
      viewOrder,
      (tracklet) =>
        colors.colorOfAnnotation(tracklet as Parameters<typeof colors.colorOfAnnotation>[0]),
      trackModelCache,
    );
    return trackModelCache.models;
  });
});

/** Every entity id with the id of its top-level entity. */
export const timelineTopEntityIds = reactiveDerived<ReadonlyMap<string, string>>(() =>
  buildTopEntityIdByEntityId(entities.value),
);

/** The objects that get a row: tracks of their own, and neither they nor their parent hidden. */
export const timelineCandidateIds = reactiveDerived<string[]>(() => {
  const models = timelineTrackModels.value;
  const topIds = timelineTopEntityIds.value;
  const hidden = new Set(
    entities.value.filter((entity) => entity.ui.displayControl.hidden).map((entity) => entity.id),
  );
  return entities.value
    .filter((entity) => models.has(entity.id))
    .filter((entity) => !hidden.has(entity.id) && !hidden.has(topIds.get(entity.id) ?? entity.id))
    .map((entity) => entity.id);
});

let rankedItemId = "";
let rowRanks: ReadonlyMap<string, number> = new Map();

/** Row order, frozen for a record visit: an edit never moves a row, and new rows go last. */
const timelineRowRanks = reactiveDerived<ReadonlyMap<string, number>>(() => {
  const itemId = currentItemId.value;
  const models = timelineTrackModels.value;
  const tracked = entities.value.filter((entity) => models.has(entity.id));
  return untrack(() => {
    if (itemId !== rankedItemId) {
      rankedItemId = itemId;
      rowRanks = new Map();
    }
    const keys: RankKey[] = tracked.map((entity) => ({
      id: entity.id,
      firstFrame: models.get(entity.id)?.firstFrame ?? Number.POSITIVE_INFINITY,
      name: typeof entity.data.name === "string" ? entity.data.name : null,
      parentId: entity.data.parent_id || null,
    }));
    rowRanks = extendTimelineRanks(rowRanks, keys);
    return rowRanks;
  });
});

let lastRows: readonly string[] | null = null;

/** The rows, in order. */
export const timelineRows = reactiveDerived<readonly string[]>(() => {
  const next = orderTimelineRows(timelineCandidateIds.value, timelineRowRanks.value);
  if (lastRows && sameTimelineRows(lastRows, next)) return lastRows;
  lastRows = next;
  return next;
});

/** The tracked objects of the record, hidden ones included (for the empty state). */
export const timelineTrackedCount = reactiveDerived<number>(() => timelineTrackModels.value.size);

/**
 * The selected top-level object: the focused one, or, under tools that keep the selection on
 * the annotations (Fusion, a drawing tool after a save), the one stored as highlighted.
 */
export const timelineSelectedEntityId = reactiveDerived<string | null>(() => {
  if (highlightedEntity.value) return highlightedEntity.value;
  if ((selectedTool.value?.type ?? ToolType.Pan) === ToolType.Pan) return null;
  return storedSelfEntityId(tracks.value);
});

/** The selected row: the clicked or edited sub-entity row of the selected object, else its row. */
export const timelineSelectedRowId = reactiveDerived<string | null>(() => {
  const topIds = timelineTopEntityIds.value;
  const editedId = editedTrackletId.value;
  const edited = editedId ? tracks.value.find((tracklet) => tracklet.id === editedId) : undefined;
  return resolveSelectedRow({
    selectedTopId: timelineSelectedEntityId.value,
    focusedRowId: timelineFocusedRowId.value,
    editedTrackOwnerId: edited?.data.entity_id ?? null,
    topIdOf: (entityId) => topIds.get(entityId) ?? entityId,
  });
});

/** The lane the keyframe buttons, J/K and the selected keyframe follow. */
export const timelineNavLane = reactiveDerived<LaneGeom | null>(() => {
  const rowId = timelineSelectedRowId.value;
  return rowId ? (timelineTrackModels.value.get(rowId)?.union ?? null) : null;
});

$effect.root(() => {
  let lastItemId = "";

  // The focused row and the zoom belong to one record.
  $effect(() => {
    const itemId = currentItemId.value;
    if (itemId === lastItemId) return;
    lastItemId = itemId;
    untrack(() => {
      timelineFocusedRowId.value = null;
      timelineZoom.value = [TIMELINE_ZOOM_MIN];
    });
  });
});
