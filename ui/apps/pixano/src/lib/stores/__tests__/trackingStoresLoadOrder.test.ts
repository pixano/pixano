/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

// The two tracking stores import each other: each session resets the other. The tracking-by-
// detection store is imported first here, as `workspaceStores.svelte` does, so that the prompted
// tracking store is evaluated while the other one is not yet. A value it read from the other
// store at load time was then undefined, and loading the workspace stores threw.
describe("tracking stores", () => {
  it("load whichever of the two is imported first", async () => {
    const byDetection = await import("../trackingByDetectionStore.svelte");
    const prompted = await import("../trackingStore.svelte");
    const timeline = await import("../activeTrackingTimeline.svelte");

    expect(byDetection.trackingByDetectionTimelineState.value).toBeNull();
    expect(prompted.trackingTimelineState.value).toBeNull();
    expect(timeline.activeTrackingTimelineState.value).toBeNull();
  });
});
