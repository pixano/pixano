/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { sourcesStore } from "$lib/stores/appStores.svelte";
import { currentFrameIndex, lastFrameIndex } from "$lib/stores/videoStores.svelte";
import {
  annotations,
  entities,
} from "$lib/stores/workspaceStores.svelte";
import {
  Annotation,
  BaseSchema,
  BBox,
  Entity,
  isVideoEntity,
  Keypoints,
  Tracklet,
  type SequenceFrame,
  type View,
} from "$lib/types/dataset";
import type { KeypointAnnotation } from "$lib/types/shapeTypes";
import { getPixanoSourceId } from "$lib/utils/entityLookupUtils";
import { appendAnnotationsSorted } from "$lib/utils/entityOperations";
import { saveTo } from "$lib/utils/saveItemUtils";
import { sortByFrameIndex } from "$lib/utils/videoUtils";
import { splitTrackInTwo } from "$lib/utils/videoOperations";

type MView = Record<string, View | View[]>;

/**
 * Add a keyframe at the current frame position within a tracklet.
 * Materialises the interpolated bbox/keypoints into real annotations.
 *
 * Returns `true` if new annotations were added, `false` otherwise.
 */
export function addKeyItemToTracklet(
  tracklet: Tracklet,
  entity: Entity,
  views: MView,
  bboxes: BBox[],
  keypoints: KeypointAnnotation[],
): boolean {
  let newItemBBox: BBox | undefined = undefined;
  let newItemKpt: Keypoints | undefined = undefined;
  const sourceId = getPixanoSourceId(sourcesStore);

  // Find interpolated bbox for the current frame
  const interpolatedBox = bboxes.find(
    (box) =>
      box.ui.frame_index === currentFrameIndex.value &&
      tracklet.ui.childs.some((ann) => ann.id === box.ui?.startRef?.id),
  );
  if (interpolatedBox) {
    newItemBBox = BBox.cloneForFrame(interpolatedBox, {
      source_id: sourceId,
    });
    // Coords are denormalized: normalize them
    const currentSf = (views[newItemBBox.data.view_name] as SequenceFrame[])[
      newItemBBox.ui.frame_index
    ];
    const [x, y, w, h] = newItemBBox.data.coords;
    newItemBBox.data.coords = [
      x / currentSf.data.width,
      y / currentSf.data.height,
      w / currentSf.data.width,
      h / currentSf.data.height,
    ];
    saveTo("add", newItemBBox);
  }

  // Find interpolated keypoints for the current frame
  const interpolatedKpt = keypoints.find(
    (kpt) =>
      kpt.ui?.frame_index === currentFrameIndex.value &&
      tracklet.ui.childs.some((ann) => ann.id === kpt.ui?.startRef?.id),
  );
  if (interpolatedKpt && interpolatedKpt.ui?.startRef) {
    const keypointsRef = annotations.value.find(
      (ann) => ann.id === interpolatedKpt.ui?.startRef?.id && ann.is_type(BaseSchema.Keypoints),
    ) as Keypoints;
    if (keypointsRef) {
      const currentSf = (views[keypointsRef.data.view_name] as SequenceFrame[])[
        interpolatedKpt.ui.frame_index
      ];
      const coords: number[] = [];
      const states: string[] = [];
      for (let vi = 0; vi <interpolatedKpt.graph.vertices.length; vi++) {
        const vertex = interpolatedKpt.graph.vertices[vi];
        coords.push(vertex.x / currentSf.data.width);
        coords.push(vertex.y / currentSf.data.height);
        const meta = interpolatedKpt.vertexMetadata[vi];
        states.push(meta?.state ? meta.state : "visible");
      }
      newItemKpt = Keypoints.cloneForFrame(keypointsRef, {
        id: interpolatedKpt.id,
        coords,
        states,
        view_name: interpolatedKpt.viewRef.name,
        frame_id: interpolatedKpt.viewRef.id,
        frame_index: interpolatedKpt.ui.frame_index,
        source_id: sourceId,
        displayControl: interpolatedKpt.ui.displayControl,
      });
      saveTo("add", newItemKpt);
    }
  }

  if (!newItemBBox && !newItemKpt) return false;
  const newTrackChildren: Annotation[] = [];
  if (newItemBBox) newTrackChildren.push(newItemBBox);
  if (newItemKpt) newTrackChildren.push(newItemKpt);

  annotations.update((objects) => {
    objects.map((obj) => {
      if (obj.is_type(BaseSchema.Tracklet) && obj.id === tracklet.id) {
        const objTrack = obj as Tracklet;
        objTrack.ui.childs = appendAnnotationsSorted(
          objTrack.ui.childs,
          newTrackChildren,
          sortByFrameIndex,
        );
      }
      return obj;
    });
    return appendAnnotationsSorted(objects, newTrackChildren, sortByFrameIndex);
  });
  entities.update((objects) =>
    objects.map((ent) => {
      if (ent.id === tracklet.data.entity_id) {
        ent.ui.childs = appendAnnotationsSorted(ent.ui.childs, newTrackChildren, sortByFrameIndex);
      }
      return ent;
    }),
  );
  return true;
}

/**
 * Binary search within a tracklet's children to find the frame indices of
 * the previous and next annotations relative to the current frame cursor.
 */
export function findPreviousAndNextFrames(tracklet: Tracklet): [number, number] {
  let low = 0;
  let high = tracklet.ui.childs.length - 1;
  let mid = 0;
  let previousItem: Annotation | null = null;
  let nextItem: Annotation | null = null;

  while (low <= high) {
    mid = Math.floor((low + high) / 2);
    if (tracklet.ui.childs[mid].ui.frame_index <= currentFrameIndex.value) {
      previousItem = tracklet.ui.childs[mid];
      low = mid + 1;
    } else {
      nextItem = tracklet.ui.childs[mid];
      high = mid - 1;
    }
  }
  return [
    previousItem ? previousItem.ui.frame_index : currentFrameIndex.value,
    nextItem ? nextItem.ui.frame_index : currentFrameIndex.value + 1,
  ];
}

/**
 * Split a tracklet at the current frame position into two tracklets.
 * The left tracklet retains the original ID; a new right tracklet is created.
 */
export function splitTracklet(
  tracklet: Tracklet,
  entityId: string,
): void {
  const [prev, next] = findPreviousAndNextFrames(tracklet);
  const newOnRight = splitTrackInTwo(tracklet, prev, next);
  entities.update((objects) =>
    objects.map((ent) => {
      if (isVideoEntity(ent) && ent.id === entityId) {
        ent.ui.childs = appendAnnotationsSorted(ent.ui.childs, [newOnRight], sortByFrameIndex);
      }
      return ent;
    }),
  );
  annotations.update((objects) => objects.concat(newOnRight));
}

/**
 * Find the frame indices of the nearest neighbor annotations (across all
 * tracklets in the same view) that bracket the given frame index.
 */
export function findNeighborFrameIndices(
  tracklet: Tracklet,
  frameIndex: number,
  allTracklets: Tracklet[],
): [number, number] {
  let previous: number = 0;
  let next: number = lastFrameIndex.value ?? 0;
  for (const subtrack of allTracklets) {
    if (subtrack.data.view_name === tracklet.data.view_name) {
      for (const child of subtrack.ui.childs) {
        if (child.ui.frame_index <frameIndex && child.ui.frame_index > previous) {
          previous = child.ui.frame_index!;
        } else if (child.ui.frame_index > frameIndex && child.ui.frame_index <next) {
          next = child.ui.frame_index!;
        }
      }
    }
  }
  return [previous, next];
}
