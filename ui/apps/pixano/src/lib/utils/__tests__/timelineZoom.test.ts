/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { nextTimelineZoom, timelineZoomMax } from "$lib/utils/timelineZoom";

describe("timelineZoomMax", () => {
  it("scales with the clip length and never drops below 200", () => {
    expect(timelineZoomMax(undefined)).toBe(200);
    expect(timelineZoomMax(19)).toBe(200);
    expect(timelineZoomMax(500)).toBe(1500);
  });
});

describe("nextTimelineZoom", () => {
  it("steps by a quarter in either direction", () => {
    expect(nextTimelineZoom(100, 1, 1500)).toBe(125);
    expect(nextTimelineZoom(125, -1, 1500)).toBe(100);
  });

  it("clamps to the slider range", () => {
    expect(nextTimelineZoom(100, -1, 1500)).toBe(100);
    expect(nextTimelineZoom(1450, 1, 1500)).toBe(1500);
    expect(nextTimelineZoom(1500, 1, 1500)).toBe(1500);
  });
});
