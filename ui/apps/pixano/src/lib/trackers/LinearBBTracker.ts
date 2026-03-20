/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseTracker, type InterpolationResult, type TrackerKeyframe } from "./BaseTracker";

export interface BBoxKeyframe extends TrackerKeyframe {
  readonly frameIndex: number;
  readonly coords: readonly [number, number, number, number]; // normalized [x, y, w, h]
}

export class LinearBBTracker extends BaseTracker<BBoxKeyframe> {
  interpolateAt(frameIndex: number): InterpolationResult<BBoxKeyframe> | null {
    if (this.keyframes.size === 0) return null;

    // Exact keyframe match
    const exact = this.keyframes.get(frameIndex);
    if (exact) {
      return { frameIndex, isKeyframe: true, data: exact };
    }

    const sorted = this.sortedKeyframes;

    // Single keyframe — not the exact frame (already checked above) → outside range
    if (sorted.length < 2) {
      return null;
    }

    // Outside range (only applies with 2+ keyframes)
    if (frameIndex < sorted[0].frameIndex || frameIndex > sorted[sorted.length - 1].frameIndex) {
      return null;
    }

    // Find bracketing keyframes
    let startKf: BBoxKeyframe | undefined;
    let endKf: BBoxKeyframe | undefined;
    for (let i = 0; i < sorted.length - 1; i++) {
      if (sorted[i].frameIndex <= frameIndex && sorted[i + 1].frameIndex >= frameIndex) {
        startKf = sorted[i];
        endKf = sorted[i + 1];
        break;
      }
    }

    if (!startKf || !endKf) return null;

    const span = endKf.frameIndex - startKf.frameIndex;
    if (span === 0) return { frameIndex, isKeyframe: true, data: startKf };

    const t = (frameIndex - startKf.frameIndex) / span;
    const coords: [number, number, number, number] = [
      startKf.coords[0] + t * (endKf.coords[0] - startKf.coords[0]),
      startKf.coords[1] + t * (endKf.coords[1] - startKf.coords[1]),
      startKf.coords[2] + t * (endKf.coords[2] - startKf.coords[2]),
      startKf.coords[3] + t * (endKf.coords[3] - startKf.coords[3]),
    ];

    return {
      frameIndex,
      isKeyframe: false,
      data: { frameIndex, coords },
    };
  }
}
