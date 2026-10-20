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
import { isTracking } from "./trackingStore.svelte";
import { currentItemId, timelineZoom, videoViewNames } from "./videoStores.svelte";
import {
  annotationColors,
  editedTrackletId,
  entities,
  highlightedEntity,
  newShape,
  selectedTool,
  tracks,
} from "./workspaceStores.svelte";
import {
  keyframeScopeView,
  nextArming,
  resolveViewChoice,
  scopedLane,
  type AddInViewTarget,
} from "$lib/timeline/timelineCameras";
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
/** Rows expanded into one sub-row per camera. */
export const timelineExpandedEntityIds = reactiveStore<string[]>([]);
/** The camera the timeline shows alone, or null for all of them. */
export const timelineViewFilter = reactiveStore<string | null>(null);
/** The camera the keyframe tools and the pencil follow on an expanded row. */
export const timelineActiveCamera = reactiveStore<string | null>(null);
/** The object armed for drawing in a camera ("+ Add in this view"). */
export const timelineAddInViewTarget = reactiveStore<AddInViewTarget | null>(null);

/** The record's cameras, in natural order. */
export const timelineViewOrder = reactiveDerived<string[]>(() =>
  sortViewNames(videoViewNames.value),
);

/** Whether the record has several cameras: only then does the timeline show camera rows. */
export const timelineMultiView = reactiveDerived<boolean>(() => timelineViewOrder.value.length > 1);

/** The camera shown alone, if it is still one of the record's. */
export const effectiveTimelineViewFilter = reactiveDerived<string | null>(() =>
  timelineMultiView.value
    ? resolveViewChoice(timelineViewFilter.value, timelineViewOrder.value, null)
    : null,
);

/** The active camera, the first one until another is chosen. */
export const effectiveActiveCamera = reactiveDerived<string | null>(() =>
  resolveViewChoice(
    timelineActiveCamera.value,
    timelineViewOrder.value,
    timelineViewOrder.value[0] ?? null,
  ),
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

/** The camera the keyframe tools follow on the selected row, or null for all its cameras. */
export const timelineNavScopeView = reactiveDerived<string | null>(() => {
  const rowId = timelineSelectedRowId.value;
  return keyframeScopeView({
    viewCount: timelineViewOrder.value.length,
    viewFilter: effectiveTimelineViewFilter.value,
    expanded: rowId !== null && timelineExpandedEntityIds.value.includes(rowId),
    activeCamera: effectiveActiveCamera.value,
  });
});

/** The lane the keyframe buttons, J/K and the selected keyframe follow. */
export const timelineNavLane = reactiveDerived<LaneGeom | null>(() => {
  const rowId = timelineSelectedRowId.value;
  const model = rowId ? timelineTrackModels.value.get(rowId) : undefined;
  return model ? scopedLane(model, timelineNavScopeView.value) : null;
});

export function toggleTimelineRowExpanded(entityId: string): void {
  timelineExpandedEntityIds.update((ids) =>
    ids.includes(entityId) ? ids.filter((id) => id !== entityId) : [...ids, entityId],
  );
}

/** Show one camera alone (null for all of them); it becomes the active camera too. */
export function selectTimelineView(view: string | null): void {
  timelineViewFilter.value = view;
  if (view !== null) timelineActiveCamera.value = view;
}

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
      timelineExpandedEntityIds.value = [];
      timelineViewFilter.value = null;
      timelineActiveCamera.value = null;
      timelineAddInViewTarget.value = null;
    });
  });

  // An armed object lasts while the box tool or its tracking session is on, and until the
  // save form closes or the object is gone.
  $effect(() => {
    const toolType = selectedTool.value?.type ?? ToolType.Pan;
    const tracking = isTracking.value;
    untrack(() => {
      const target = timelineAddInViewTarget.value;
      const next = nextArming(target, { type: "tool", toolType, tracking });
      if (next !== target) timelineAddInViewTarget.value = next;
    });
  });
  let wasSaving = false;
  $effect(() => {
    const saving = newShape.value.status === "saving";
    if (wasSaving && !saving) {
      untrack(() => {
        timelineAddInViewTarget.value = nextArming(timelineAddInViewTarget.value, {
          type: "save-closed",
          tracking: isTracking.value,
        });
      });
    }
    wasSaving = saving;
  });
  $effect(() => {
    const ids = new Set(entities.value.map((entity) => entity.id));
    untrack(() => {
      const target = timelineAddInViewTarget.value;
      const next = nextArming(target, { type: "entities", ids });
      if (next !== target) timelineAddInViewTarget.value = next;
    });
  });
});
