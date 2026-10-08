/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  ImageTask,
  supportsPromptedTracking,
  supportsTrackingByDetection,
  VideoTask,
  type InferenceModel,
} from "../inference";

const model = (overrides: Partial<InferenceModel>): InferenceModel => ({
  name: "model",
  provider_name: "pixano-inference",
  task: VideoTask.TRACKING,
  ...overrides,
});

describe("tracking model capabilities", () => {
  it("treats a tracking model without an interface as prompted only", () => {
    // A prompted model run without prompts fails on the server: unknown is not offered for detection.
    const unknown = model({ interface: null });
    expect(supportsPromptedTracking(unknown)).toBe(true);
    expect(supportsTrackingByDetection(unknown)).toBe(false);
    expect(supportsPromptedTracking(model({ interface: undefined }))).toBe(true);
    expect(supportsTrackingByDetection(model({ interface: undefined }))).toBe(false);
  });

  it("reads prompts and prompt_free from the interface", () => {
    const sam2 = model({
      interface: { capability: "tracking", prompts: ["points", "box", "mask"], prompt_free: false },
    });
    const bytetrack = model({
      interface: {
        capability: "tracking",
        prompts: [],
        prompt_free: true,
        class_names: ["person"],
      },
    });
    expect(supportsPromptedTracking(sam2)).toBe(true);
    expect(supportsTrackingByDetection(sam2)).toBe(false);
    expect(supportsPromptedTracking(bytetrack)).toBe(false);
    expect(supportsTrackingByDetection(bytetrack)).toBe(true);
  });

  it("never qualifies a model of another task", () => {
    const segmentation = model({ task: ImageTask.SEGMENTATION, interface: null });
    expect(supportsPromptedTracking(segmentation)).toBe(false);
    expect(supportsTrackingByDetection(segmentation)).toBe(false);
  });
});
