/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * The tracking session the timeline shows: prompted boxes, VOS masks, or tracking by detection.
 *
 * It lives apart from both tracking stores because it reads a value of each. The two stores
 * import each other, and whichever is evaluated second sees the first one not evaluated yet: a
 * value read from it at load time is undefined.
 */

import { reactiveDerived } from "./reactiveStore.svelte";
import { trackingByDetectionTimelineState } from "./trackingByDetectionStore.svelte";
import { trackingTimelineState, vosTimelineState } from "./trackingStore.svelte";
import type { TrackingTimelineState } from "$lib/trackingTimeline";

export const activeTrackingTimelineState = reactiveDerived<TrackingTimelineState | null>(() => {
  return (
    trackingTimelineState.value ?? vosTimelineState.value ?? trackingByDetectionTimelineState.value
  );
});
