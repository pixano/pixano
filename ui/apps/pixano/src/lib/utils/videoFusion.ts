/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { annotations, entities, merges } from "$lib/stores/workspaceStores.svelte";
import { BaseSchema, type Annotation, type Entity, type Tracklet } from "$lib/types/dataset";
import { getTopEntity } from "$lib/utils/entityLookupUtils";
import { highlightAnnotationIds } from "$lib/utils/highlightOperations";

/**
 * Build combined tracklet frame ranges for each view of the given entities.
 * Returns a record keyed by view name, each containing merged [start, end] ranges.
 */
export function mergeFusionRangesByView(toFuse: Entity[]): Record<string, [number, number][]> {
  const tracksByView: Record<string, Tracklet[]> = {};
  toFuse
    .flatMap((ent) =>
      ent.ui.childs
        ? (ent.ui.childs.filter((ann) => ann.is_type(BaseSchema.Tracklet)) as Tracklet[])
        : [],
    )
    .forEach((trk) => {
      if (!(trk.data.view_name in tracksByView)) tracksByView[trk.data.view_name] = [];
      tracksByView[trk.data.view_name].push(trk);
    });

  const mergedByView: Record<string, [number, number][]> = {};
  Object.entries(tracksByView).forEach(([view, viewTracks]) => {
    mergedByView[view] = [];
    if (viewTracks.length > 0) {
      viewTracks.sort((a, b) => a.data.start_frame - b.data.start_frame);
      let currentTrack = { ...viewTracks[0] };
      for (let i = 1; i < viewTracks.length; i++) {
        const trk = viewTracks[i];
        if (trk.data.start_frame <= currentTrack.data.end_frame) {
          currentTrack.data.end_frame = Math.max(currentTrack.data.end_frame, trk.data.end_frame);
        } else {
          mergedByView[view].push([currentTrack.data.start_frame, currentTrack.data.end_frame]);
          currentTrack = { ...trk };
        }
      }
      mergedByView[view].push([currentTrack.data.start_frame, currentTrack.data.end_frame]);
    }
  });
  return mergedByView;
}

/**
 * Check whether two sets of per-view frame ranges can be merged without
 * temporal overlap within any single view.
 */
export function canMergeRangesByView(
  record1: Record<string, [number, number][]>,
  record2: Record<string, [number, number][]>,
): boolean {
  const allViews = new Set([...Object.keys(record1), ...Object.keys(record2)]);

  for (const view of allViews) {
    const ranges1 = record1[view] || [];
    const ranges2 = record2[view] || [];

    const allRanges = [...ranges1, ...ranges2].sort((a, b) =>
      a[0] === b[0] ? a[1] - b[1] : a[0] - b[0],
    );
    for (let i = 1; i < allRanges.length; i++) {
      const prev = allRanges[i - 1];
      const curr = allRanges[i];
      if (prev[1] >= curr[0]) {
        return false;
      }
    }
  }
  return true;
}

/**
 * Recompute which entities are forbidden from merging with the current
 * fusion selection, and update highlight state accordingly.
 */
export function checkMergeForbids(toFuse: Entity[]): void {
  const forbids: Entity[] = merges.value.forbids;
  const toFuseRanges = mergeFusionRangesByView(toFuse);
  const others = entities.value.filter((ent) => !toFuse.includes(ent) && ent.data.parent_id === "");
  others.forEach((ent) => {
    const ranges = mergeFusionRangesByView([ent]);
    if (canMergeRangesByView(ranges, toFuseRanges)) {
      if (forbids.includes(ent)) {
        const removeIndex = forbids.indexOf(ent, 0);
        forbids.splice(removeIndex, 1);
      }
    } else {
      if (!forbids.includes(ent)) {
        forbids.push(ent);
      }
    }
  });

  const forbidIds = new Set(forbids.map((ent) => ent.id));
  const fuseIds = new Set(toFuse.map((ent) => ent.id));
  annotations.update((anns) =>
    anns.map((ann) => {
      const topEntId = getTopEntity(ann).id;
      if (forbidIds.has(topEntId)) ann.ui.displayControl.highlighted = "none";
      else if (!fuseIds.has(topEntId)) ann.ui.displayControl.highlighted = "all";
      return ann;
    }),
  );
}

/**
 * Toggle an entity into/out of the fusion selection and update highlights.
 * Called when clicking an annotation while the Fusion tool is active.
 */
export function toggleFusionEntity(clickedAnn: Annotation): void {
  const topEntity = getTopEntity(clickedAnn);
  if (merges.value.forbids.includes(topEntity)) return;

  const entityChildIds = new Set((topEntity.ui.childs ?? []).map((ann) => ann.id));

  if (!merges.value.to_fuse.includes(topEntity)) {
    merges.update((assoc) => ({
      to_fuse: [...assoc.to_fuse, topEntity],
      forbids: assoc.forbids,
    }));
    highlightAnnotationIds(entityChildIds, false);
  } else {
    merges.update((assoc) => {
      const removeIndex = assoc.to_fuse.indexOf(topEntity, 0);
      assoc.to_fuse.splice(removeIndex, 1);
      return assoc;
    });
    highlightAnnotationIds(entityChildIds, false, "all");
  }
  checkMergeForbids(merges.value.to_fuse);
}
